"""
Text-based conversation simulator for the VAPI Accountability Coach.

Simulates the full conversation loop (system prompt + tool calls) using
the Anthropic Claude API so you can rapidly iterate on your prompt without
making real voice calls.

Usage:
    python simulate.py                  # mock mode (default) — uses fake tool data
    python simulate.py --live           # live mode — calls your real backend
    python simulate.py --scenario new   # simulate a brand-new caller
    python simulate.py --scenario returning  # simulate a returning caller with topics

Edit prompt.txt to change the system prompt, then re-run to test.
"""

import argparse
import json
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from app.config import settings

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROMPT_FILE = Path(__file__).parent / "prompt.txt"
ASSISTANT_ID = "69411b1f-a971-462b-a11a-61cf3b5ab715"
CALLER_PHONE = "+18005551234"

# ---------------------------------------------------------------------------
# Mock scenarios — edit these to test different conversation paths
# ---------------------------------------------------------------------------

SCENARIOS = {
    "new": {
        "description": "Brand-new caller, no existing topics",
        "lookupPersonAndTopics": {
            "success": True,
            "personName": None,
            "topics": [],
        },
        "startTopicSession": {
            "success": True,
            "topicId": "topic_abc123def456",
            "topicName": "",  # will be filled from args
            "conversationId": "conv_2026-02-10T12:00:00",
            "mode": "",  # will be filled from args
            "coachingTemplateCode": None,
            "summarySoFar": "",
        },
    },
    "returning": {
        "description": "Returning caller with existing topics and history",
        "lookupPersonAndTopics": {
            "success": True,
            "personName": "Alex",
            "topics": [
                {
                    "topicId": "topic_001",
                    "topicName": "Launch my podcast",
                    "lastSummarySnippet": "Committed to recording episode 1 by Friday. Outline is done.",
                    "updatedAt": "2026-02-08T15:30:00Z",
                },
                {
                    "topicId": "topic_002",
                    "topicName": "Morning exercise routine",
                    "lastSummarySnippet": "Doing 15-min walks 3x/week. Goal: add strength training.",
                    "updatedAt": "2026-02-06T10:00:00Z",
                },
            ],
        },
        "startTopicSession": {
            "success": True,
            "topicId": "topic_001",
            "topicName": "Launch my podcast",
            "conversationId": "conv_2026-02-10T12:00:00",
            "mode": "accountability",
            "coachingTemplateCode": None,
            "summarySoFar": (
                "--- Session 1 ---\n"
                "Alex wants to launch a podcast about indie game development.\n"
                "Decided on a weekly format, 20-30 minutes per episode.\n"
                "Committed to writing an outline for episode 1 by Wednesday.\n\n"
                "--- Session 2 ---\n"
                "Outline is done. Bought a Blue Yeti microphone.\n"
                "Committed to recording episode 1 by Friday Feb 14.\n"
                "Still needs to pick a hosting platform — considering Buzzsprout or Anchor.\n"
                "Open item: choose hosting platform before recording."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Tool definitions (matching what VAPI provides to the model)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "lookupPersonAndTopics",
        "description": (
            "Look up an existing person by their phone number and return their "
            "name and list of coaching topics. Call this once at the start of "
            "every conversation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "assistantId": {
                    "type": "string",
                    "description": "The assistant ID",
                },
                "callerPhone": {
                    "type": "string",
                    "description": "The caller's phone number",
                },
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
                "topicId": {
                    "type": "string",
                    "description": "ID of an existing topic (omit if creating new)",
                },
                "newTopicName": {
                    "type": "string",
                    "description": "Name for a new topic (omit if using existing)",
                },
                "callerPhone": {
                    "type": "string",
                    "description": "The caller's phone number",
                },
                "mode": {
                    "type": "string",
                    "enum": ["accountability", "brainstorming", "mix"],
                    "description": "Coaching mode for this session",
                },
            },
            "required": ["callerPhone", "mode"],
        },
    },
]

# ---------------------------------------------------------------------------
# Live mode — call your real backend
# ---------------------------------------------------------------------------

def call_live_backend(tool_name: str, tool_input: dict, caller_phone: str) -> dict:
    """Call the real backend tool endpoint."""
    import httpx

    server_url = "https://web-production-b0d30.up.railway.app/vapi/tools"

    # Build the VAPI-style request body
    body = {
        "message": {
            "type": "tool-calls",
            "call": {
                "assistantId": ASSISTANT_ID,
                "customer": {"number": caller_phone},
            },
            "toolCallList": [
                {
                    "id": "sim_call_001",
                    "function": {
                        "name": tool_name,
                        "arguments": tool_input,
                    },
                }
            ],
        }
    }

    headers = {"Content-Type": "application/json"}
    if settings.VAPI_SERVER_SECRET:
        headers["X-Vapi-Secret"] = settings.VAPI_SERVER_SECRET

    resp = httpx.post(server_url, json=body, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    if results:
        result_str = results[0].get("result", "{}")
        return json.loads(result_str) if isinstance(result_str, str) else result_str
    return {"error": "No result from backend"}


# ---------------------------------------------------------------------------
# Mock mode — return canned responses
# ---------------------------------------------------------------------------

def call_mock_tool(tool_name: str, tool_input: dict, scenario: dict) -> dict:
    """Return mock tool responses based on the selected scenario."""
    mock_data = scenario.get(tool_name, {})

    if tool_name == "startTopicSession":
        # Fill in dynamic fields from the tool call arguments
        result = dict(mock_data)
        if tool_input.get("newTopicName"):
            result["topicName"] = tool_input["newTopicName"]
        if tool_input.get("topicId"):
            result["topicId"] = tool_input["topicId"]
        if tool_input.get("mode"):
            result["mode"] = tool_input["mode"]
        return result

    return mock_data


# ---------------------------------------------------------------------------
# Conversation loop
# ---------------------------------------------------------------------------

def load_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text(encoding="utf-8").strip()
    print(f"Warning: {PROMPT_FILE} not found, using built-in prompt.")
    return "You are an accountability coach."


def run_conversation(live: bool, scenario_name: str, caller_phone: str):
    scenario = SCENARIOS.get(scenario_name, SCENARIOS["returning"])
    system_prompt = load_prompt()

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    model = settings.CLAUDE_MODEL

    messages = []

    mode_label = "LIVE (hitting real backend)" if live else f"MOCK (scenario: {scenario_name})"

    print("=" * 60)
    print(f"  Accountability Coach Simulator")
    print(f"  Mode: {mode_label}")
    print(f"  Model: {model}")
    print(f"  Prompt: {PROMPT_FILE}")
    print(f"  Phone: {caller_phone}")
    print("=" * 60)
    print()
    print("  Type your messages as the caller.")
    print("  Commands:  /quit  /reset  /prompt  /transcript")
    print()

    # The assistant speaks first in the real flow (firstMessage),
    # so we simulate the user saying "hello" to trigger the tool call.
    print("  [Call connected — the assistant will speak first]")
    print()

    # Add initial user message to trigger the assistant
    messages.append({"role": "user", "content": "Hello?"})
    print(f"  You: Hello?")

    while True:
        # Call Claude
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.APIError as e:
            print(f"\n  [API Error: {e}]\n")
            break

        # Process response
        assistant_text_parts = []
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                assistant_text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # Show any text the assistant said
        if assistant_text_parts:
            full_text = " ".join(assistant_text_parts)
            print(f"\n  Coach: {full_text}")

        # Handle tool calls
        if response.stop_reason == "tool_use" and tool_uses:
            # Add assistant message with all content blocks
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tu in tool_uses:
                tool_name = tu.name
                tool_input = tu.input
                print(f"\n  [Tool call: {tool_name}({json.dumps(tool_input, indent=2)})]")

                if live:
                    result = call_live_backend(tool_name, tool_input, caller_phone)
                else:
                    result = call_mock_tool(tool_name, tool_input, scenario)

                print(f"  [Tool result: {json.dumps(result, indent=2)[:500]}]")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})
            # Loop back to get the assistant's response to the tool result
            continue

        # Add assistant response to history
        if assistant_text_parts:
            messages.append({"role": "assistant", "content": " ".join(assistant_text_parts)})

        # Get user input
        print()
        try:
            user_input = input("  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  [Call ended]")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.lower() == "/quit":
            print("\n  [Call ended]")
            break
        elif user_input.lower() == "/reset":
            print("\n  [Resetting conversation...]\n")
            messages.clear()
            messages.append({"role": "user", "content": "Hello?"})
            print(f"  You: Hello?")
            continue
        elif user_input.lower() == "/prompt":
            print(f"\n  [Current prompt ({len(system_prompt)} chars):]")
            print(f"  {system_prompt[:500]}...")
            print()
            continue
        elif user_input.lower() == "/transcript":
            print("\n  [Conversation transcript:]")
            for msg in messages:
                role = msg["role"]
                content = msg.get("content", "")
                if isinstance(content, str):
                    print(f"    {role}: {content[:200]}")
                elif isinstance(content, list):
                    for item in content:
                        if hasattr(item, "text"):
                            print(f"    {role}: {item.text[:200]}")
                        elif isinstance(item, dict) and item.get("type") == "tool_result":
                            print(f"    {role}: [tool_result]")
            print()
            continue

        messages.append({"role": "user", "content": user_input})

    # Print final transcript
    print("\n" + "=" * 60)
    print("  Full transcript:")
    print("=" * 60)
    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            label = "You" if role == "user" else "Coach"
            print(f"  {label}: {content}")
        elif isinstance(content, list):
            for item in content:
                if hasattr(item, "text") and item.text:
                    print(f"  Coach: {item.text}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Simulate conversations with your VAPI coach")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call the real backend instead of using mock data",
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="returning",
        help="Mock scenario to use (default: returning)",
    )
    parser.add_argument(
        "--phone",
        default=CALLER_PHONE,
        help="Simulated caller phone number",
    )

    args = parser.parse_args()

    print()
    if not args.live:
        print(f"  Available scenarios:")
        for name, sc in SCENARIOS.items():
            print(f"    --scenario {name:12s}  {sc['description']}")
        print()

    run_conversation(live=args.live, scenario_name=args.scenario, caller_phone=args.phone)


if __name__ == "__main__":
    main()
