import logging
from datetime import datetime, timezone
from typing import Any

from app.database import get_db
from app.models.memory import RecordKind, TopicInfo

logger = logging.getLogger(__name__)

COLLECTION = "agentMemoryRecords"
SESSIONS_COLLECTION = "conversationSessions"


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

async def create_record(
    agentId: str,
    personKeyType: str,
    personKey: str,
    topicId: str,
    topicName: str,
    recordKind: RecordKind,
    conversationId: str | None = None,
    sequence: int | None = None,
    text: str | None = None,
    data: dict[str, Any] | None = None,
    personName: str | None = None,
    personId: str | None = None,
    coachingTemplateCode: str | None = None,
) -> str:
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "agentId": agentId,
        "personKeyType": personKeyType,
        "personKey": personKey,
        "personName": personName,
        "personId": personId,
        "topicId": topicId,
        "topicName": topicName,
        "coachingTemplateCode": coachingTemplateCode,
        "recordKind": recordKind.value,
        "conversationId": conversationId,
        "sequence": sequence,
        "text": text,
        "data": data,
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db[COLLECTION].insert_one(doc)
    return str(result.inserted_id)


async def get_topics_for_person(
    agentId: str,
    personKeyType: str,
    personKey: str,
    max_topics: int = 20,
) -> list[TopicInfo]:
    db = get_db()
    pipeline = [
        {
            "$match": {
                "agentId": agentId,
                "personKeyType": personKeyType,
                "personKey": personKey,
                "topicId": {"$not": {"$regex": "^_"}},
                "topicName": {"$not": {"$regex": "^_"}},
            }
        },
        {
            "$group": {
                "_id": "$topicId",
                "topicName": {"$last": "$topicName"},
                "lastUpdatedAt": {"$max": "$updatedAt"},
            }
        },
        {"$sort": {"lastUpdatedAt": -1}},
        {"$limit": max_topics},
    ]
    topics: list[TopicInfo] = []
    async for doc in db[COLLECTION].aggregate(pipeline):
        topic_id = doc["_id"]
        # Fetch the latest summary snippet for this topic
        latest_summary = await db[COLLECTION].find_one(
            {
                "agentId": agentId,
                "personKeyType": personKeyType,
                "personKey": personKey,
                "topicId": topic_id,
                "recordKind": RecordKind.summary.value,
            },
            sort=[("sequence", -1), ("createdAt", -1)],
            projection={"text": 1},
        )
        snippet = None
        if latest_summary and latest_summary.get("text"):
            snippet = latest_summary["text"][:200]

        topics.append(
            TopicInfo(
                topicId=topic_id,
                topicName=doc["topicName"],
                lastSummarySnippet=snippet,
                lastUpdatedAt=doc["lastUpdatedAt"],
            )
        )
    return topics


async def get_records_for_topic(
    agentId: str,
    personKeyType: str,
    personKey: str,
    topicId: str,
    recordKind: RecordKind,
    limit: int = 20,
    sort_order: str = "asc",
) -> list[dict[str, Any]]:
    db = get_db()
    direction = 1 if sort_order == "asc" else -1
    cursor = (
        db[COLLECTION]
        .find(
            {
                "agentId": agentId,
                "personKeyType": personKeyType,
                "personKey": personKey,
                "topicId": topicId,
                "recordKind": recordKind.value,
            },
            projection={
                "_id": 1,
                "sequence": 1,
                "text": 1,
                "data": 1,
                "createdAt": 1,
            },
        )
        .sort([("sequence", direction), ("createdAt", direction)])
        .limit(limit)
    )
    records = []
    async for doc in cursor:
        records.append(
            {
                "recordId": str(doc["_id"]),
                "sequence": doc.get("sequence"),
                "text": doc.get("text"),
                "data": doc.get("data"),
                "createdAt": doc.get("createdAt"),
            }
        )
    return records


async def get_next_sequence(
    agentId: str,
    personKeyType: str,
    personKey: str,
    topicId: str,
) -> int:
    db = get_db()
    doc = await db[COLLECTION].find_one(
        {
            "agentId": agentId,
            "personKeyType": personKeyType,
            "personKey": personKey,
            "topicId": topicId,
        },
        sort=[("sequence", -1)],
        projection={"sequence": 1},
    )
    if doc and doc.get("sequence") is not None:
        return doc["sequence"] + 1
    return 1


async def get_person_name(
    agentId: str,
    personKeyType: str,
    personKey: str,
) -> str | None:
    db = get_db()
    doc = await db[COLLECTION].find_one(
        {
            "agentId": agentId,
            "personKeyType": personKeyType,
            "personKey": personKey,
            "personName": {"$ne": None},
        },
        projection={"personName": 1},
    )
    if doc:
        return doc.get("personName")
    return None


# ---------------------------------------------------------------------------
# Conversation session mapping (MongoDB-backed)
# ---------------------------------------------------------------------------

async def save_conversation_session(
    conversationId: str,
    agentId: str,
    personKeyType: str,
    personKey: str,
    topicId: str,
    topicName: str,
    mode: str,
    coachingTemplateCode: str | None = None,
) -> None:
    db = get_db()
    await db[SESSIONS_COLLECTION].insert_one(
        {
            "conversationId": conversationId,
            "agentId": agentId,
            "personKeyType": personKeyType,
            "personKey": personKey,
            "topicId": topicId,
            "topicName": topicName,
            "mode": mode,
            "coachingTemplateCode": coachingTemplateCode,
            "createdAt": datetime.now(timezone.utc),
        }
    )


async def get_conversation_session(conversationId: str) -> dict[str, Any] | None:
    db = get_db()
    return await db[SESSIONS_COLLECTION].find_one({"conversationId": conversationId})


async def count_summaries(
    agentId: str,
    personKeyType: str,
    personKey: str,
    topicId: str,
) -> int:
    """Count the total number of summary records for a topic."""
    db = get_db()
    return await db[COLLECTION].count_documents(
        {
            "agentId": agentId,
            "personKeyType": personKeyType,
            "personKey": personKey,
            "topicId": topicId,
            "recordKind": RecordKind.summary.value,
        }
    )


async def consolidate_oldest_summaries(
    agentId: str,
    personKeyType: str,
    personKey: str,
    topicId: str,
    topicName: str,
    coachingTemplateCode: str | None,
    consolidated_text: str,
    records_to_remove: list[str],
) -> str:
    """Replace multiple old summary records with a single consolidated one.

    1. Insert the consolidated summary with sequence=1.
    2. Delete the original records.
    3. Re-sequence remaining summaries so sequences are contiguous.

    Returns the new consolidated record's ID.
    """
    from bson import ObjectId

    db = get_db()
    now = datetime.now(timezone.utc)

    # 1. Insert consolidated summary (sequence=1, it replaces the oldest batch)
    consolidated_doc = {
        "agentId": agentId,
        "personKeyType": personKeyType,
        "personKey": personKey,
        "personName": None,
        "personId": None,
        "topicId": topicId,
        "topicName": topicName,
        "coachingTemplateCode": coachingTemplateCode,
        "recordKind": RecordKind.summary.value,
        "conversationId": None,
        "sequence": 1,
        "text": consolidated_text,
        "data": {"consolidated": True, "replaced_count": len(records_to_remove)},
        "createdAt": now,
        "updatedAt": now,
    }
    result = await db[COLLECTION].insert_one(consolidated_doc)
    consolidated_id = str(result.inserted_id)

    # 2. Delete the original records that were consolidated
    ids_to_delete = [ObjectId(rid) for rid in records_to_remove]
    delete_result = await db[COLLECTION].delete_many(
        {"_id": {"$in": ids_to_delete}}
    )
    logger.info(
        "Consolidation: deleted %d old summary records, inserted consolidated %s",
        delete_result.deleted_count,
        consolidated_id,
    )

    # 3. Re-sequence remaining summaries so they are contiguous starting from 1
    remaining = (
        db[COLLECTION]
        .find(
            {
                "agentId": agentId,
                "personKeyType": personKeyType,
                "personKey": personKey,
                "topicId": topicId,
                "recordKind": RecordKind.summary.value,
            },
            projection={"_id": 1},
        )
        .sort([("sequence", 1), ("createdAt", 1)])
    )
    seq = 1
    async for doc in remaining:
        await db[COLLECTION].update_one(
            {"_id": doc["_id"]},
            {"$set": {"sequence": seq}},
        )
        seq += 1

    logger.info("Re-sequenced %d summary records for topic %s", seq - 1, topicId)
    return consolidated_id
