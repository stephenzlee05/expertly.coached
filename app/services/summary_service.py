import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


SUMMARY_SYSTEM_PROMPT = (
    "You are helping an accountability coach remember a series of calls "
    "with the same person about a single topic.\n\n"
    "Write ONE new short summary entry that:\n"
    "- Mentions any important background needed next time.\n"
    "- Lists key decisions, commitments, and deadlines.\n"
    "- Notes any unfinished items still to follow up on.\n"
    "- Uses simple bullet-like sentences, but as plain text.\n\n"
    "The output should stand alone as a summary of THIS call only, "
    "but assume the coach can also see earlier summaries."
)

CONSOLIDATION_SYSTEM_PROMPT = (
    "You are helping an accountability coach condense multiple session "
    "summaries into a single consolidated summary.\n\n"
    "The summaries below are from consecutive coaching sessions on the "
    "same topic with the same person. Your job is to merge them into ONE "
    "concise summary that preserves:\n"
    "- Key background and context the coach needs.\n"
    "- All commitments, decisions, and deadlines that are still relevant.\n"
    "- Important progress milestones and completed items (briefly).\n"
    "- Any open/unfinished items that need follow-up.\n\n"
    "Drop anything that is clearly outdated or superseded by later sessions. "
    "Use simple bullet-like sentences, plain text. "
    "The result should be shorter than the combined input."
)


async def generate_summary(
    past_summaries: list[str],
    transcript: str,
) -> str:
    summaries_text = ""
    if past_summaries:
        numbered = [
            f"--- Session {i + 1} ---\n{s}" for i, s in enumerate(past_summaries)
        ]
        summaries_text = "\n\n".join(numbered)

    user_content = ""
    if summaries_text:
        user_content += f"Previous summaries (in order):\n\n{summaries_text}\n\n"
    user_content += f"Full transcript of the latest call:\n\n{transcript}"

    try:
        client = _get_client()
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text
    except Exception:
        logger.exception("Failed to generate summary via Claude API")
        return "[Summary generation failed - see transcript]"


async def consolidate_summaries(summaries: list[str]) -> str:
    """Merge multiple session summaries into a single consolidated summary.

    Used when the number of summaries for a topic exceeds the cap.
    The oldest summaries are consolidated into one, keeping the total
    number of summary records manageable.
    """
    if not summaries:
        return ""

    numbered = [f"--- Session {i + 1} ---\n{s}" for i, s in enumerate(summaries)]
    user_content = (
        "Consolidate these session summaries into a single summary:\n\n"
        + "\n\n".join(numbered)
    )

    try:
        client = _get_client()
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=2048,
            system=CONSOLIDATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text
    except Exception:
        logger.exception("Failed to consolidate summaries via Claude API")
        # Fallback: just keep the last summary from the batch
        return summaries[-1]
