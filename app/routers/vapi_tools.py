import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Request

from app.models.memory import LookupPersonResponse, RecordKind, StartTopicSessionResponse, TopicInfo
from app.services import memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vapi", tags=["vapi-tools"])


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

@router.post("/tools")
async def handle_tool_calls(request: Request):
    """Handle VAPI tool-calls server event.

    VAPI sends a POST with message.type == "tool-calls" containing a
    toolCallList. We dispatch each tool call by function name and return
    results in the format VAPI expects.
    """
    body = await request.json()
    message = body.get("message", {})

    if message.get("type") != "tool-calls":
        return {"results": []}

    tool_calls = message.get("toolCallList", [])
    results = []

    for tc in tool_calls:
        tc_id = tc.get("id", "")
        func = tc.get("function", {})
        name = func.get("name", "")
        args = func.get("arguments", {})

        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}

        if name == "lookupPersonAndTopics":
            result = await _lookup_person_and_topics(args)
        elif name == "startTopicSession":
            result = await _start_topic_session(args)
        else:
            result = json.dumps({"success": False, "error": f"Unknown tool: {name}"})

        results.append({"toolCallId": tc_id, "result": result})

    return {"results": results}


# ---------------------------------------------------------------------------
# lookupPersonAndTopics
# ---------------------------------------------------------------------------

async def _lookup_person_and_topics(args: dict) -> str:
    assistant_id = args.get("assistantId", "")
    caller_phone = args.get("callerPhone", "")

    if not assistant_id or not caller_phone:
        return json.dumps({"success": False, "error": "assistantId and callerPhone are required"})

    agent_id = assistant_id

    topics = await memory_service.get_topics_for_person(
        agentId=agent_id,
        personKeyType="phone",
        personKey=caller_phone,
    )

    person_name = await memory_service.get_person_name(
        agentId=agent_id,
        personKeyType="phone",
        personKey=caller_phone,
    )

    response = LookupPersonResponse(
        success=True,
        personName=person_name,
        topics=topics,
    )
    return response.model_dump_json()


# ---------------------------------------------------------------------------
# startTopicSession
# ---------------------------------------------------------------------------

async def _start_topic_session(args: dict) -> str:
    assistant_id = args.get("assistantId", "")
    caller_phone = args.get("callerPhone", "")
    topic_id = args.get("topicId")
    new_topic_name = args.get("newTopicName")
    mode = args.get("mode", "accountability")
    coaching_template_code = args.get("coachingTemplateCode")

    if not assistant_id or not caller_phone:
        return json.dumps({"success": False, "error": "assistantId and callerPhone are required"})

    if not topic_id and not new_topic_name:
        return json.dumps({"success": False, "error": "Either topicId or newTopicName is required"})

    agent_id = assistant_id
    topic_name = new_topic_name or ""

    # Resolve existing topic or create new one
    if topic_id:
        # Look up topic name from existing records
        records = await memory_service.get_records_for_topic(
            agentId=agent_id,
            personKeyType="phone",
            personKey=caller_phone,
            topicId=topic_id,
            recordKind=RecordKind.summary,
            limit=1,
        )
        if records:
            # We don't store topicName in the query result, so look it up
            from app.database import get_db
            db = get_db()
            existing = await db["agentMemoryRecords"].find_one(
                {"agentId": agent_id, "topicId": topic_id},
                projection={"topicName": 1, "coachingTemplateCode": 1},
            )
            if existing:
                topic_name = existing.get("topicName", topic_name)
                if not coaching_template_code:
                    coaching_template_code = existing.get("coachingTemplateCode")
    else:
        topic_id = f"topic_{uuid4().hex[:12]}"

    # Fetch recent summaries
    summary_records = await memory_service.get_records_for_topic(
        agentId=agent_id,
        personKeyType="phone",
        personKey=caller_phone,
        topicId=topic_id,
        recordKind=RecordKind.summary,
        limit=50,
        sort_order="asc",
    )

    # Build summarySoFar by concatenation
    summary_so_far = ""
    if summary_records:
        parts = []
        for i, rec in enumerate(summary_records):
            seq = rec.get("sequence") or (i + 1)
            parts.append(f"--- Session {seq} ---\n{rec.get('text', '')}")
        summary_so_far = "\n\n".join(parts)

    # Generate conversationId
    conversation_id = f"conv_{datetime.now(timezone.utc).isoformat()}"

    # Store conversation session mapping in MongoDB
    await memory_service.save_conversation_session(
        conversationId=conversation_id,
        agentId=agent_id,
        personKeyType="phone",
        personKey=caller_phone,
        topicId=topic_id,
        topicName=topic_name,
        mode=mode,
        coachingTemplateCode=coaching_template_code,
    )

    response = StartTopicSessionResponse(
        success=True,
        topicId=topic_id,
        topicName=topic_name,
        conversationId=conversation_id,
        mode=mode,
        coachingTemplateCode=coaching_template_code,
        summarySoFar=summary_so_far,
    )
    return response.model_dump_json()
