"""
Automated conversation test — runs scripted scenarios through the simulator
and prints the full exchange so we can evaluate the AI's tone and behavior.
"""

import json
import anthropic
from dotenv import load_dotenv
from pathlib import Path

from app.config import settings
from simulate import TOOLS, SCENARIOS, call_mock_tool, load_prompt

load_dotenv()


def run_scripted_conversation(scenario_name: str, user_messages: list[str], label: str):
    """Run a scripted conversation and print the full exchange."""
    scenario = SCENARIOS[scenario_name]
    system_prompt = load_prompt()
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    model = settings.CLAUDE_MODEL

    print("\n" + "=" * 70)
    print(f"  TEST: {label}")
    print(f"  Scenario: {scenario_name}")
    print(f"  Model: {model}")
    print("=" * 70 + "\n")

    messages = []
    user_msg_index = 0

    # Start with "Hello?" to trigger the assistant
    current_user_msg = "Hello?"
    messages.append({"role": "user", "content": current_user_msg})
    print(f"  Caller: {current_user_msg}")

    max_turns = 30  # safety limit
    turn = 0

    while turn < max_turns:
        turn += 1

        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        # Collect text and tool uses
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        if text_parts:
            full_text = " ".join(text_parts)
            print(f"\n  Coach: {full_text}")

        # Handle tool calls
        if response.stop_reason == "tool_use" and tool_uses:
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tu in tool_uses:
                print(f"\n  [Tool: {tu.name}({json.dumps(tu.input)})]")
                result = call_mock_tool(tu.name, tu.input, scenario)
                result_str = json.dumps(result)
                print(f"  [Result: {result_str[:300]}]")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": result_str,
                })

            messages.append({"role": "user", "content": tool_results})
            continue

        # Add assistant text to messages
        if text_parts:
            messages.append({"role": "assistant", "content": " ".join(text_parts)})

        # Feed next scripted user message
        if user_msg_index < len(user_messages):
            current_user_msg = user_messages[user_msg_index]
            user_msg_index += 1
            print(f"\n  Caller: {current_user_msg}")
            messages.append({"role": "user", "content": current_user_msg})
        else:
            print("\n  [End of scripted messages]")
            break

    print("\n" + "-" * 70 + "\n")


def main():
    # Test 1: Returning caller — picks existing topic
    run_scripted_conversation(
        scenario_name="returning",
        label="Returning caller picks existing topic",
        user_messages=[
            "Hey, yeah let's talk about the podcast.",
            "I actually did record the first episode! But I haven't edited it yet.",
            "Hmm maybe like two or three days? I've never used editing software before though.",
            "Yeah I think I'll try Descript, a friend recommended it.",
            "Ok sounds good. I'll have it edited by Thursday and I'll pick Buzzsprout for hosting.",
            "Yep that's it, thanks!",
        ],
    )

    # Test 2: New caller — starting fresh
    run_scripted_conversation(
        scenario_name="new",
        label="Brand new caller, no history",
        user_messages=[
            "Hi, yeah this is my first time calling.",
            "I want to work on getting better at public speaking.",
            "Let's call it public speaking practice.",
            "Mostly accountability I think. I need someone to keep me on track.",
            "Well I have a presentation at work in three weeks and I'm really nervous about it.",
            "That makes sense. I could practice in front of my mirror this week I guess.",
            "Maybe three times this week? Like Monday, Wednesday, Friday.",
            "Ok yeah let's do that. Three mirror practice sessions, five minutes each.",
            "Alright, talk to you later!",
        ],
    )

    # Test 3: Returning caller — starts a NEW topic
    run_scripted_conversation(
        scenario_name="returning",
        label="Returning caller starts a new topic",
        user_messages=[
            "Actually I want to start something new today.",
            "I want to learn Spanish.",
            "Let's call it Spanish learning.",
            "A mix of both I think — brainstorming and accountability.",
            "I want to be conversational in six months. I'm going to Mexico City in August.",
            "No, total beginner. I know like ten words.",
            "Duolingo sounds good, I could do that every morning.",
            "Fifteen minutes a day, every morning with my coffee. I'll start tomorrow.",
            "Great, thanks! Talk soon.",
        ],
    )


if __name__ == "__main__":
    main()
