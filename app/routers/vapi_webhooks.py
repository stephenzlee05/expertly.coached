import logging

from fastapi import APIRouter, BackgroundTasks, Request

from app.models.memory import RecordKind, SaveConversationResponse
from app.services import memory_service, summary_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vapi", tags=["vapi-webhooks"])


@router.post("/webhooks")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle VAPI server events (webhooks).

    We specifically handle the 'end-of-call-report' event type to save
    the conversation transcript and generate a summary.
    """
    body = await request.json()
    message = body.get("message", {})
    msg_type = message.get("type", "")

    if msg_type != "end-of-call-report":
        # Acknowledge other event types without processing
        return {"status": "ok"}

    # Extract data from the end-of-call-report
    artifact = message.get("artifact", {})
    call = message.get("call", {})

    # Transcript can be a string or a list of utterance objects
    transcript_raw = artifact.get("transcript", "")
    if isinstance(transcript_raw, list):
        # Convert list of utterance objects to text
        lines = []
        for entry in transcript_raw:
            role = entry.get("role", "unknown")
            content = entry.get("message", entry.get("content", ""))
            lines.append(f"{role}: {content}")
        transcript = "\n".join(lines)
    else:
        transcript = str(transcript_raw)

    assistant_id = call.get("assistantId", "")
    customer = call.get("customer", {})
    caller_phone = customer.get("number", "")

    if not transcript or not assistant_id:
        logger.warning("end-of-call-report missing transcript or assistantId")
        return SaveConversationResponse(
            success=False,
            error="Missing transcript or assistantId",
        ).model_dump()

    # Try to find the conversation session to get topicId
    # Look for the most recent session for this agent + phone
    from app.database import get_db
    db = get_db()
    session = await db["conversationSessions"].find_one(
        {
            "agentId": assistant_id,
            "personKey": caller_phone,
        },
        sort=[("createdAt", -1)],
    )

    if not session:
        logger.warning(
            "No conversation session found for agent=%s phone=%s",
            assistant_id,
            caller_phone,
        )
        return SaveConversationResponse(
            success=False,
            error="No active conversation session found for this call",
        ).model_dump()

    conversation_id = session["conversationId"]
    topic_id = session["topicId"]
    topic_name = session["topicName"]
    coaching_template_code = session.get("coachingTemplateCode")

    # Schedule the heavy work in the background
    background_tasks.add_task(
        _save_and_summarize,
        agent_id=assistant_id,
        caller_phone=caller_phone,
        conversation_id=conversation_id,
        topic_id=topic_id,
        topic_name=topic_name,
        coaching_template_code=coaching_template_code,
        transcript=transcript,
    )

    return {"status": "ok"}


async def _save_and_summarize(
    agent_id: str,
    caller_phone: str,
    conversation_id: str,
    topic_id: str,
    topic_name: str,
    coaching_template_code: str | None,
    transcript: str,
) -> None:
    """Background task: store transcript, generate summary, store summary."""
    try:
        # 1. Store the transcript
        transcript_record_id = await memory_service.create_record(
            agentId=agent_id,
            personKeyType="phone",
            personKey=caller_phone,
            topicId=topic_id,
            topicName=topic_name,
            recordKind=RecordKind.transcript,
            conversationId=conversation_id,
            coachingTemplateCode=coaching_template_code,
            text=transcript,
        )
        logger.info("Saved transcript record: %s", transcript_record_id)

        # 2. Fetch existing summaries for context
        summary_records = await memory_service.get_records_for_topic(
            agentId=agent_id,
            personKeyType="phone",
            personKey=caller_phone,
            topicId=topic_id,
            recordKind=RecordKind.summary,
            limit=50,
            sort_order="asc",
        )
        past_summaries = [r["text"] for r in summary_records if r.get("text")]

        # 3. Generate new summary via Claude
        new_summary = await summary_service.generate_summary(
            past_summaries=past_summaries,
            transcript=transcript,
        )

        # 4. Store the new summary
        next_seq = await memory_service.get_next_sequence(
            agentId=agent_id,
            personKeyType="phone",
            personKey=caller_phone,
            topicId=topic_id,
        )
        summary_record_id = await memory_service.create_record(
            agentId=agent_id,
            personKeyType="phone",
            personKey=caller_phone,
            topicId=topic_id,
            topicName=topic_name,
            recordKind=RecordKind.summary,
            conversationId=conversation_id,
            sequence=next_seq,
            coachingTemplateCode=coaching_template_code,
            text=new_summary,
        )
        logger.info("Saved summary record: %s (sequence=%d)", summary_record_id, next_seq)

    except Exception:
        logger.exception(
            "Failed to save/summarize conversation %s for topic %s",
            conversation_id,
            topic_id,
        )
