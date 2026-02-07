import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.config import settings
from app.dependencies import verify_vapi_secret
from app.models.memory import RecordKind, SaveConversationResponse
from app.routers.vapi_tools import normalize_phone
from app.services import memory_service, summary_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vapi", tags=["vapi-webhooks"], dependencies=[Depends(verify_vapi_secret)])


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
    caller_phone = normalize_phone(customer.get("number", ""))

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
            "No conversation session found for agent=%s phone=%s. "
            "Saving transcript to _unmatched topic.",
            assistant_id,
            caller_phone,
        )
        # Save to _unmatched so the transcript is never lost
        background_tasks.add_task(
            _save_and_summarize,
            agent_id=assistant_id,
            caller_phone=caller_phone,
            conversation_id=f"conv_unmatched_{datetime.now(timezone.utc).isoformat()}",
            topic_id="_unmatched",
            topic_name="_unmatched",
            coaching_template_code=None,
            transcript=transcript,
        )
        return {"status": "ok"}

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
    """Background task: store transcript, then generate and store summary.

    Transcript storage and summary generation are in separate try/except
    blocks so that a summary failure never causes transcript loss.
    """
    # 1. Store the transcript (MUST succeed — this is the critical data)
    transcript_record_id = None
    try:
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
    except Exception:
        logger.exception(
            "CRITICAL: Failed to save transcript for conversation %s",
            conversation_id,
        )
        return  # Cannot proceed without saving the transcript

    # 2. Generate and store summary (best-effort — failure is non-critical)
    try:
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

        new_summary = await summary_service.generate_summary(
            past_summaries=past_summaries,
            transcript=transcript,
        )

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
            "Failed to generate/save summary for conversation %s "
            "(transcript was saved as %s)",
            conversation_id,
            transcript_record_id,
        )
        return  # Skip consolidation if summary generation failed

    # 3. Consolidate old summaries if over the cap (best-effort)
    try:
        cap = settings.SUMMARY_CAP
        total = await memory_service.count_summaries(
            agentId=agent_id,
            personKeyType="phone",
            personKey=caller_phone,
            topicId=topic_id,
        )

        if total > cap:
            # Fetch all summaries in chronological order
            all_summaries = await memory_service.get_records_for_topic(
                agentId=agent_id,
                personKeyType="phone",
                personKey=caller_phone,
                topicId=topic_id,
                recordKind=RecordKind.summary,
                limit=total,
                sort_order="asc",
            )

            # Consolidate the oldest ones, keeping the newest (cap - 1) intact
            # This leaves room: 1 consolidated + (cap - 1) recent = cap total
            num_to_consolidate = total - (cap - 1)
            to_consolidate = all_summaries[:num_to_consolidate]
            texts_to_consolidate = [r["text"] for r in to_consolidate if r.get("text")]
            ids_to_remove = [r["recordId"] for r in to_consolidate]

            logger.info(
                "Summary cap reached for topic %s: %d summaries (cap=%d). "
                "Consolidating oldest %d into 1.",
                topic_id, total, cap, num_to_consolidate,
            )

            consolidated_text = await summary_service.consolidate_summaries(
                texts_to_consolidate
            )

            await memory_service.consolidate_oldest_summaries(
                agentId=agent_id,
                personKeyType="phone",
                personKey=caller_phone,
                topicId=topic_id,
                topicName=topic_name,
                coachingTemplateCode=coaching_template_code,
                consolidated_text=consolidated_text,
                records_to_remove=ids_to_remove,
            )
            logger.info("Consolidation complete for topic %s", topic_id)

    except Exception:
        logger.exception(
            "Failed to consolidate summaries for topic %s "
            "(transcript and new summary were saved successfully)",
            topic_id,
        )
