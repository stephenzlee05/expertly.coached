import logging
from contextlib import asynccontextmanager

import pymongo
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    _db = _client[settings.MONGODB_DB_NAME]

    # Create indexes
    collection = _db["agentMemoryRecords"]
    await collection.create_index(
        [
            ("agentId", pymongo.ASCENDING),
            ("personKeyType", pymongo.ASCENDING),
            ("personKey", pymongo.ASCENDING),
            ("topicId", pymongo.ASCENDING),
            ("recordKind", pymongo.ASCENDING),
        ],
        name="agent_person_topic_kind",
    )
    await collection.create_index(
        [
            ("agentId", pymongo.ASCENDING),
            ("personKeyType", pymongo.ASCENDING),
            ("personKey", pymongo.ASCENDING),
        ],
        name="agent_person",
    )

    sessions = _db["conversationSessions"]
    await sessions.create_index("conversationId", unique=True)

    logger.info("Connected to MongoDB and ensured indexes.")


async def close_db() -> None:
    global _client, _db
    if _client:
        _client.close()
    _client = None
    _db = None
    logger.info("Disconnected from MongoDB.")


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db
