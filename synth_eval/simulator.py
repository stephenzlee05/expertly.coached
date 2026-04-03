"""Run multi-turn roleplay conversations between a simulated caller and coach.

Produces a structured transcript suitable for evaluation.
"""

import json
import os
import time

import anthropic

from app.config import settings

# Allow overriding model for simulation (to manage rate limits)
SIM_MODEL = os.environ.get("SYNTH_EVAL_MODEL", settings.CLAUDE_MODEL)
# Delay between API calls in seconds (helps with rate limits)
CALL_DELAY = int(os.environ.get("SYNTH_EVAL_DELAY", "5"))

# Tool definitions matching VAPI
TOOLS = [
    {
        "name": "lookupPersonAndTopics",
        "description": (
            "Look up an existing person by their phone number and return their "
            "name and list of coaching topics."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "assistantId": {"type": "string"},
                "callerPhone": {"type": "string"},
            },
            "required": ["assistantId", "callerPhone"],
        },
    },
    {
        "name": "startTopicSession",
        "description": (
            "Start or resume a coaching session for a specific topic. "
            "Returns the topic's conversation history summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topicId": {"type": "string"},
                "newTopicName": {"type": "string"},
                "callerPhone": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["accountability", "brainstorming", "mix"],
                },
            },
            "required": ["callerPhone", "mode"],
        },
    },
]


def _mock_tool(tool_name: str, tool_input: dict, mock_data: dict) -> dict:
    """Return mock tool responses."""
    data = mock_data.get(tool_name, {})
    if tool_name == "startTopicSession":
        result = dict(data)
        if tool_input.get("newTopicName"):
            result["topicName"] = tool_input["newTopicName"]
        if tool_input.get("topicId"):
            result["topicId"] = tool_input["topicId"]
        if tool_input.get("mode"):
            result["mode"] = tool_input["mode"]
        return result
    return data


def simulate_session(
    system_prompt: str,
    session_config: dict,
    assistant_id: str = "test_assistant",
) -> dict:
    """Run a single coaching session and return structured results.

    Args:
        system_prompt: The coach's system prompt text.
        session_config: A session dict from a persona (has mock data + user_messages).
        assistant_id: The assistant ID for tool calls.

    Returns:
        {
            "transcript": [{"role": "caller"|"coach"|"tool", "text": "..."}],
            "turn_count": int,
            "tool_calls": [{"name": str, "input": dict, "result": dict}],
            "protocol_flags": [str],  # automated protocol checks
        }
    """
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    model = SIM_MODEL

    mock_data = session_config["mock"]
    user_messages = list(session_config["user_messages"])

    messages = []
    transcript = []
    tool_calls_log = []
    protocol_flags = []

    # Start with "Hello?" to trigger the assistant
    messages.append({"role": "user", "content": "Hello?"})
    transcript.append({"role": "caller", "text": "Hello?"})

    user_msg_idx = 0
    max_turns = 40
    turn = 0

    while turn < max_turns:
        turn += 1

        # Delay between calls to respect rate limits
        if turn > 1:
            time.sleep(CALL_DELAY)

        # Retry with backoff for rate limits
        response = None
        for attempt in range(5):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages,
                )
                break
            except anthropic.RateLimitError as e:
                wait = 60 * (attempt + 1)
                print(f"      Rate limited, waiting {wait}s (attempt {attempt+1}/5)...")
                time.sleep(wait)
            except anthropic.APIError as e:
                protocol_flags.append(f"API_ERROR: {e}")
                break

        if response is None:
            protocol_flags.append("RATE_LIMIT_EXHAUSTED: Could not complete after retries")
            break

        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        full_text = " ".join(text_parts) if text_parts else ""

        if full_text:
            transcript.append({"role": "coach", "text": full_text})
            _check_protocol(full_text, protocol_flags)

        # Handle tool calls
        if response.stop_reason == "tool_use" and tool_uses:
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for tu in tool_uses:
                # Protocol checks on tool usage
                if tu.name == "lookupPersonAndTopics" and turn > 3:
                    protocol_flags.append("LATE_LOOKUP: lookupPersonAndTopics called after turn 3")
                if tu.name not in ("lookupPersonAndTopics", "startTopicSession"):
                    protocol_flags.append(f"INVENTED_TOOL: '{tu.name}'")

                result = _mock_tool(tu.name, tu.input, mock_data)
                tool_calls_log.append({
                    "name": tu.name,
                    "input": tu.input,
                    "result": result,
                })
                transcript.append({
                    "role": "tool",
                    "text": f"[{tu.name}] -> {json.dumps(result)[:200]}",
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})
            continue

        # Add assistant response
        if text_parts:
            messages.append({"role": "assistant", "content": full_text})

        # Feed next user message
        if user_msg_idx < len(user_messages):
            msg = user_messages[user_msg_idx]
            user_msg_idx += 1
            transcript.append({"role": "caller", "text": msg})
            messages.append({"role": "user", "content": msg})
        else:
            break

    return {
        "transcript": transcript,
        "turn_count": turn,
        "tool_calls": tool_calls_log,
        "protocol_flags": protocol_flags,
    }


def _check_protocol(text: str, flags: list):
    """Run automated protocol compliance checks on coach text."""
    # Markdown detection
    if any(c in text for c in ["**", "##", "- ", "* ", "1. "]):
        flags.append(f"MARKDOWN: '{text[:80]}...'")

    # Over-long response
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if len(sentences) > 5:
        flags.append(f"TOO_LONG ({len(sentences)} sentences)")

    # Stacked questions
    if text.count("?") > 1:
        flags.append(f"STACKED_QUESTIONS ({text.count('?')})")


def run_full_persona(
    system_prompt: str,
    persona: dict,
    assistant_id: str = "test_assistant",
) -> list[dict]:
    """Run all sessions for a persona, returning list of session results."""
    results = []
    for session in persona["sessions"]:
        result = simulate_session(system_prompt, session, assistant_id)
        result["session_num"] = session["session_num"]
        result["persona_id"] = persona["id"]
        result["persona_name"] = persona["name"]
        results.append(result)
        time.sleep(0.5)  # brief pause between sessions
    return results
