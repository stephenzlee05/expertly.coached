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
