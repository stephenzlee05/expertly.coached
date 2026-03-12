"""
Automated stress-test for ALL five coaching assistants.

Runs targeted scenarios through each assistant designed to expose prompt weaknesses:
- Edge cases (caller is confused, emotional, or combative)
- Protocol compliance (tool calls, voice rules, markdown avoidance)
- Domain-specific coaching quality

Usage:
    python test_all_assistants.py
    python test_all_assistants.py --assistant accountability   # run just one
    python test_all_assistants.py --verbose                    # show full tool calls
"""

import argparse
import json
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from app.config import settings

load_dotenv()

# ---------------------------------------------------------------------------
# Assistant configurations
# ---------------------------------------------------------------------------

ASSISTANTS = {
    "accountability": {
        "id": "69411b1f-a971-462b-a11a-61cf3b5ab715",
        "prompt_file": "prompt_accountability_partner.txt",
        "label": "Accountability Partner",
    },
    "student": {
        "id": "c1995689-523c-4de3-ae49-53ffb911be69",
        "prompt_file": "prompt_student_success.txt",
        "label": "Student Success Coach",
    },
    "performance": {
        "id": "54819721-5422-4a90-a4b9-47dc843016d0",
        "prompt_file": "prompt_personal_performance.txt",
        "label": "Personal Performance Coach",
    },
    "founder": {
        "id": "dc2284ca-a57a-4379-b981-bd65af9f9b22",
        "prompt_file": "prompt_founder_execution.txt",
        "label": "Founder Execution Coach",
    },
    "health": {
        "id": "9c8b6724-7c77-46b2-86cf-6204e3dc630d",
        "prompt_file": "prompt_health_weight_loss.txt",
        "label": "Weight Loss & Health Coach",
    },
}

# ---------------------------------------------------------------------------
# Tool definitions (same as VAPI provides)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Scenarios per assistant (mock data + scripted user messages)
# ---------------------------------------------------------------------------

SCENARIOS = {
    "accountability": [
        {
            "name": "Returning caller — missed commitments + emotional",
            "mock": {
                "lookupPersonAndTopics": {
                    "success": True,
                    "personName": "Jordan",
                    "topics": [
                        {
                            "topicId": "topic_001",
                            "topicName": "Write my novel",
                            "lastSummarySnippet": "Committed to writing 500 words/day for a week.",
                            "updatedAt": "2026-03-03T10:00:00Z",
                        },
                    ],
                },
                "startTopicSession": {
                    "success": True,
                    "topicId": "topic_001",
                    "topicName": "Write my novel",
                    "conversationId": "conv_test_001",
                    "mode": "accountability",
                    "coachingTemplateCode": None,
                    "summarySoFar": (
                        "--- Session 1 ---\n"
                        "Jordan wants to write a sci-fi novel. Has an outline for 12 chapters.\n"
                        "Committed to writing 500 words every day this week.\n"
                        "Open item: pick a writing time and stick to it.\n\n"
                        "--- Session 2 ---\n"
                        "Only wrote 2 out of 7 days. Felt frustrated.\n"
                        "Identified that evenings are bad — too tired after work.\n"
                        "Committed to trying mornings: wake up 30 min early, write before coffee.\n"
                        "Open item: write 500 words every morning Mon-Fri this week."
                    ),
                },
            },
            "user_messages": [
                "Hey... yeah let's talk about the novel.",
                "I didn't write at all this week. Not a single word. I'm honestly starting to think I'm just not a writer.",
                "I don't know, maybe I should just give up on this whole thing. It's been three weeks and I've barely done anything.",
                "I guess... but what's even the point if I can never stick to anything?",
                "Fine. Maybe just 100 words. But I've said stuff like this before and it never works.",
                "Tomorrow morning I guess. Before work.",
                "Okay. Thanks.",
            ],
        },
        {
            "name": "New caller — vague goals, tests boundaries",
            "mock": {
                "lookupPersonAndTopics": {
                    "success": True,
                    "personName": None,
                    "topics": [],
                },
                "startTopicSession": {
                    "success": True,
                    "topicId": "topic_new_001",
                    "topicName": "",
                    "conversationId": "conv_test_002",
                    "mode": "",
                    "coachingTemplateCode": None,
                    "summarySoFar": "",
                },
            },
            "user_messages": [
                "Hi, first time calling.",
                "I just want to be more productive in general. Like, get my life together.",
                "I don't know, everything? Work, health, relationships, finances...",
                "Can you just tell me what to do? Like give me a whole plan for my life?",
                "Okay fine. I guess work is the biggest one right now.",
                "Hmm, let's call it career improvement. And accountability I think.",
                "I want to get promoted within six months but I don't really know what I need to do differently.",
                "Yeah that makes sense. I'll talk to my manager this week about what they expect.",
                "Bye!",
            ],
        },
    ],
    "student": [
        {
            "name": "Panicking student — exam tomorrow, unprepared",
            "mock": {
                "lookupPersonAndTopics": {
                    "success": True,
                    "personName": "Sam",
                    "topics": [
                        {
                            "topicId": "topic_chem",
                            "topicName": "Organic Chemistry",
                            "lastSummarySnippet": "Planned to review chapters 5-8 over the weekend.",
                            "updatedAt": "2026-03-07T14:00:00Z",
                        },
                    ],
                },
                "startTopicSession": {
                    "success": True,
                    "topicId": "topic_chem",
                    "topicName": "Organic Chemistry",
                    "conversationId": "conv_test_003",
                    "mode": "accountability",
                    "coachingTemplateCode": None,
                    "summarySoFar": (
                        "--- Session 1 ---\n"
                        "Sam has an organic chem midterm next Tuesday (March 10).\n"
                        "Planned to review chapters 5-8 over the weekend.\n"
                        "Said they'd do practice problems from each chapter.\n"
                        "Open item: complete practice problems ch 5-8 by Monday."
                    ),
                },
            },
            "user_messages": [
                "Oh my god, my exam is TOMORROW and I barely studied.",
                "I only got through chapter 5. I didn't touch 6, 7, or 8. I'm so screwed.",
                "It's multiple choice and short answer. About 40 questions.",
                "I have tonight, that's it. Maybe like 5 or 6 hours if I really push.",
                "Yeah I guess focusing on the big concepts makes sense. I'll skim 6 and 7 and do practice problems.",
                "Okay yeah. I'll start with the practice exam and work backwards from what I don't know.",
                "Thanks, I needed that. Talk later.",
            ],
        },
        {
            "name": "Student wants to discuss non-academic topic",
            "mock": {
                "lookupPersonAndTopics": {
                    "success": True,
                    "personName": "Taylor",
                    "topics": [],
                },
                "startTopicSession": {
                    "success": True,
                    "topicId": "topic_new_002",
                    "topicName": "",
                    "conversationId": "conv_test_004",
                    "mode": "",
                    "coachingTemplateCode": None,
                    "summarySoFar": "",
                },
            },
            "user_messages": [
                "Hey, so I'm having relationship problems and it's affecting my grades.",
                "My partner and I keep fighting and I can't concentrate on anything.",
                "I guess... my grades are slipping in all my classes. I went from a 3.8 to like a 3.2 this semester.",
                "Yeah, I think if I could just get a study routine going it might help me feel more in control.",
                "Let's call it getting back on track. And accountability.",
                "I have a paper due Friday and two quizzes next week.",
                "The paper is for English lit. It's a 5-page analysis. I haven't started.",
                "Yeah I can do the outline tonight and write tomorrow and Thursday. That works.",
                "Thanks, that actually helps.",
            ],
        },
    ],
    "performance": [
        {
            "name": "Overcommitter — says yes to everything",
            "mock": {
                "lookupPersonAndTopics": {
                    "success": True,
                    "personName": "Casey",
                    "topics": [
                        {
                            "topicId": "topic_focus",
                            "topicName": "Deep work routine",
                            "lastSummarySnippet": "Committed to 2 hours of deep work before email each morning.",
                            "updatedAt": "2026-03-05T09:00:00Z",
                        },
                        {
                            "topicId": "topic_side",
                            "topicName": "Side project app",
                            "lastSummarySnippet": "Wants to build a habit tracker app. Hasn't started.",
                            "updatedAt": "2026-03-01T11:00:00Z",
                        },
                    ],
                },
                "startTopicSession": {
                    "success": True,
                    "topicId": "topic_focus",
                    "topicName": "Deep work routine",
                    "conversationId": "conv_test_005",
                    "mode": "accountability",
                    "coachingTemplateCode": None,
                    "summarySoFar": (
                        "--- Session 1 ---\n"
                        "Casey feels scattered — too many meetings, can't focus.\n"
                        "Committed to 2 hours of deep work before checking email each morning.\n"
                        "Also wants to: start a side project, read 2 books/month, learn Spanish, run a half marathon.\n"
                        "Open item: 2 hours deep work every morning this week."
                    ),
                },
            },
            "user_messages": [
                "Let's talk about the deep work thing.",
                "I did it twice. Monday and Tuesday. Then I had an urgent meeting Wednesday morning and it all fell apart.",
                "Yeah and now I also signed up for a leadership workshop, a book club, and I told my friend I'd help them move this weekend.",
                "I know, I know. I just hate saying no to people.",
                "Okay yeah, the deep work is the most important one. Everything else can wait.",
                "Three days this week. Monday, Wednesday, Friday. 7 to 9 AM, phone on airplane mode.",
                "Deal. And I'll say no to one thing this week as practice.",
                "Thanks, this was good.",
            ],
        },
    ],
    "founder": [
        {
            "name": "Founder juggling too many projects, nothing shipping",
            "mock": {
                "lookupPersonAndTopics": {
                    "success": True,
                    "personName": "Morgan",
                    "topics": [
                        {
                            "topicId": "topic_launch",
                            "topicName": "MVP launch",
                            "lastSummarySnippet": "Landing page done, need to set up Stripe integration.",
                            "updatedAt": "2026-03-06T16:00:00Z",
                        },
                        {
                            "topicId": "topic_hire",
                            "topicName": "First engineering hire",
                            "lastSummarySnippet": "Posted job on 3 boards. 2 good candidates to screen.",
                            "updatedAt": "2026-03-04T10:00:00Z",
                        },
                        {
                            "topicId": "topic_funding",
                            "topicName": "Seed round",
                            "lastSummarySnippet": "Deck is 80% done. Need to finalize financial projections.",
                            "updatedAt": "2026-02-28T12:00:00Z",
                        },
                    ],
                },
                "startTopicSession": {
                    "success": True,
                    "topicId": "topic_launch",
                    "topicName": "MVP launch",
                    "conversationId": "conv_test_006",
                    "mode": "accountability",
                    "coachingTemplateCode": None,
                    "summarySoFar": (
                        "--- Session 1 ---\n"
                        "Morgan is building a B2B SaaS for restaurant inventory management.\n"
                        "Landing page is live. Stripe integration needed for billing.\n"
                        "Committed to finishing Stripe setup by end of this week.\n"
                        "Also needs: onboarding flow, email notifications, basic analytics.\n"
                        "Open item: Stripe integration by Friday March 7."
                    ),
                },
            },
            "user_messages": [
                "Let's do MVP launch.",
                "So I didn't get to Stripe. I got pulled into investor meetings and then I started working on the analytics dashboard instead.",
                "Yeah I know, I keep context-switching. But the investors wanted to see traction metrics so I thought analytics was important.",
                "You're right. Stripe first, because without billing I literally can't charge anyone.",
                "I can get it done by Wednesday if I block off tomorrow and Tuesday for just that.",
                "No dependencies. It's all on me. I just need to sit down and do it.",
                "Wednesday end of day. Stripe live and tested. Then I'll circle back on the hire stuff.",
                "Thanks. Talk soon.",
            ],
        },
        {
            "name": "Founder asking for strategic advice beyond coaching scope",
            "mock": {
                "lookupPersonAndTopics": {
                    "success": True,
                    "personName": "Riley",
                    "topics": [],
                },
                "startTopicSession": {
                    "success": True,
                    "topicId": "topic_new_003",
                    "topicName": "",
                    "conversationId": "conv_test_007",
                    "mode": "",
                    "coachingTemplateCode": None,
                    "summarySoFar": "",
                },
            },
            "user_messages": [
                "Hey, first time calling. I'm building an AI startup.",
                "I need help figuring out my entire go-to-market strategy. Like pricing, channels, positioning, the whole thing.",
                "Let's call it go-to-market strategy. Mix of both.",
                "I'm building an AI writing tool for legal professionals. We have a working prototype but zero customers.",
                "What pricing model should I use? Subscription? Per-seat? Usage-based? What do you think is best for legal SaaS?",
                "Okay yeah, I guess the first step is just getting some people to try it. I know three lawyers who said they'd beta test.",
                "I'll email all three today with access links and ask them to try it this week.",
                "Cool, thanks.",
            ],
        },
    ],
    "health": [
        {
            "name": "Emotional eater having a bad week",
            "mock": {
                "lookupPersonAndTopics": {
                    "success": True,
                    "personName": "Jamie",
                    "topics": [
                        {
                            "topicId": "topic_eating",
                            "topicName": "Nighttime snacking",
                            "lastSummarySnippet": "Replaced chips with fruit 4 out of 7 nights. Going well.",
                            "updatedAt": "2026-03-05T20:00:00Z",
                        },
                    ],
                },
                "startTopicSession": {
                    "success": True,
                    "topicId": "topic_eating",
                    "topicName": "Nighttime snacking",
                    "conversationId": "conv_test_008",
                    "mode": "accountability",
                    "coachingTemplateCode": None,
                    "summarySoFar": (
                        "--- Session 1 ---\n"
                        "Jamie struggles with nighttime snacking, especially chips and cookies.\n"
                        "Trigger: stress from work and boredom after dinner.\n"
                        "Experiment: replace chips with cut fruit, keep it prepped in fridge.\n"
                        "Result: 4 out of 7 nights chose fruit instead. Felt good about it.\n\n"
                        "--- Session 2 ---\n"
                        "Continued fruit swap, 5 out of 7 nights. Good progress.\n"
                        "New experiment: go for a 10-min walk after dinner to break the snacking trigger.\n"
                        "Open item: try evening walk at least 4 nights this week."
                    ),
                },
            },
            "user_messages": [
                "Yeah let's talk about the snacking thing.",
                "This week was terrible. I ate an entire bag of chips Monday, cookies Tuesday, and I just stopped trying after that.",
                "Work has been insane. My boss put me on a new project with an impossible deadline and I'm stress eating everything in sight.",
                "I know I should be doing the walks but I just come home so exhausted I collapse on the couch.",
                "I guess... maybe I could at least keep the fruit prepped even if I don't walk. That was working before.",
                "Yeah, and maybe I won't buy chips this week. If they're not in the house I can't eat them.",
                "Okay. Prep fruit Sunday night, no chips in the house, and try for two walks instead of four.",
                "Thanks. I needed to hear that it's not all ruined.",
            ],
        },
        {
            "name": "Caller asking for medical/diet advice",
            "mock": {
                "lookupPersonAndTopics": {
                    "success": True,
                    "personName": "Alex",
                    "topics": [],
                },
                "startTopicSession": {
                    "success": True,
                    "topicId": "topic_new_004",
                    "topicName": "",
                    "conversationId": "conv_test_009",
                    "mode": "",
                    "coachingTemplateCode": None,
                    "summarySoFar": "",
                },
            },
            "user_messages": [
                "Hey, I want to lose 50 pounds. What diet should I go on?",
                "What about keto? Is that good? Or should I do intermittent fasting?",
                "Come on, you're a health coach, just tell me what to eat.",
                "Fine. I guess the biggest thing is I skip breakfast, eat fast food for lunch, and then eat a huge dinner.",
                "Let's call it healthier eating habits. Accountability.",
                "Yeah I could do that. Bring lunch to work instead of going out.",
                "I'll pack a lunch tomorrow. Something simple, like a sandwich and an apple.",
                "Okay thanks.",
            ],
        },
    ],
}

# ---------------------------------------------------------------------------
# Conversation runner
# ---------------------------------------------------------------------------

def run_scenario(
    assistant_key: str,
    scenario: dict,
    verbose: bool = False,
) -> dict:
    """Run one scenario and return the full transcript + analysis flags."""
    config = ASSISTANTS[assistant_key]
    prompt_path = Path(__file__).parent / config["prompt_file"]
    system_prompt = prompt_path.read_text(encoding="utf-8").strip()

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    model = settings.CLAUDE_MODEL

    messages = []
    transcript = []
    flags = []  # potential issues detected

    # Start with "Hello?"
    messages.append({"role": "user", "content": "Hello?"})
    transcript.append(("Caller", "Hello?"))

    user_msgs = list(scenario["user_messages"])
    user_msg_idx = 0
    max_turns = 40
    turn = 0

    while turn < max_turns:
        turn += 1
        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )
        except anthropic.APIError as e:
            flags.append(f"API_ERROR: {e}")
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
            transcript.append(("Coach", full_text))

            # --- Automated checks ---
            # Check for markdown
            if any(c in full_text for c in ["**", "##", "- ", "* ", "1. ", "1)"]):
                flags.append(f"MARKDOWN_DETECTED: '{full_text[:100]}...'")
            # Check for overly long response
            sentences = [s.strip() for s in full_text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
            if len(sentences) > 5:
                flags.append(f"TOO_LONG ({len(sentences)} sentences): '{full_text[:100]}...'")
            # Check for stacked questions
            question_marks = full_text.count("?")
            if question_marks > 1:
                flags.append(f"STACKED_QUESTIONS ({question_marks}): '{full_text[:120]}...'")
            # Check for excessive enthusiasm
            for phrase in ["That's fantastic", "I love that", "That's amazing", "That's wonderful", "That's great!", "Absolutely!"]:
                if phrase.lower() in full_text.lower():
                    flags.append(f"EXCESSIVE_ENTHUSIASM: '{phrase}' in '{full_text[:100]}...'")

        # Handle tool calls
        if response.stop_reason == "tool_use" and tool_uses:
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for tu in tool_uses:
                if verbose:
                    transcript.append(("Tool", f"{tu.name}({json.dumps(tu.input)})"))

                # Check tool call correctness
                if tu.name == "lookupPersonAndTopics":
                    if turn > 3:
                        flags.append("LATE_LOOKUP: lookupPersonAndTopics called after turn 3")
                elif tu.name == "startTopicSession":
                    if not tu.input.get("callerPhone"):
                        flags.append("MISSING_PHONE: startTopicSession called without callerPhone")
                    if not tu.input.get("mode"):
                        flags.append("MISSING_MODE: startTopicSession called without mode")
                elif tu.name not in ("lookupPersonAndTopics", "startTopicSession"):
                    flags.append(f"INVENTED_TOOL: Called non-existent tool '{tu.name}'")

                result = _mock_tool(tu.name, tu.input, scenario["mock"])
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
        if user_msg_idx < len(user_msgs):
            msg = user_msgs[user_msg_idx]
            user_msg_idx += 1
            transcript.append(("Caller", msg))
            messages.append({"role": "user", "content": msg})
        else:
            break

    return {
        "assistant": config["label"],
        "scenario": scenario["name"],
        "transcript": transcript,
        "flags": flags,
        "turns": turn,
    }


def _mock_tool(tool_name: str, tool_input: dict, mock_data: dict) -> dict:
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


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_result(result: dict):
    print()
    print("=" * 70)
    print(f"  {result['assistant']} — {result['scenario']}")
    print(f"  Turns: {result['turns']}")
    print("=" * 70)

    for role, text in result["transcript"]:
        prefix = "  Caller:" if role == "Caller" else "  Coach: " if role == "Coach" else "  [Tool]: "
        # Wrap long lines
        if len(text) > 100 and role == "Coach":
            print(f"\n{prefix} {text}\n")
        else:
            print(f"{prefix} {text}")

    if result["flags"]:
        print()
        print("  --- ISSUES DETECTED ---")
        for f in result["flags"]:
            print(f"  [!] {f}")
    else:
        print()
        print("  --- NO AUTOMATED ISSUES DETECTED ---")

    print("-" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Test all coaching assistants")
    parser.add_argument("--assistant", choices=list(ASSISTANTS.keys()), help="Run only this assistant")
    parser.add_argument("--verbose", action="store_true", help="Show tool call details")
    args = parser.parse_args()

    keys_to_run = [args.assistant] if args.assistant else list(ASSISTANTS.keys())
    all_results = []

    for key in keys_to_run:
        scenarios = SCENARIOS.get(key, [])
        for scenario in scenarios:
            print(f"\n>>> Running: {ASSISTANTS[key]['label']} — {scenario['name']}...")
            result = run_scenario(key, scenario, verbose=args.verbose)
            all_results.append(result)
            print_result(result)
            time.sleep(1)  # Brief pause between API calls

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY OF ALL ISSUES")
    print("=" * 70)
    total_flags = 0
    for r in all_results:
        if r["flags"]:
            print(f"\n  {r['assistant']} — {r['scenario']}:")
            for f in r["flags"]:
                print(f"    [!] {f}")
                total_flags += 1
    if total_flags == 0:
        print("  No automated issues detected across all tests.")
    else:
        print(f"\n  Total issues: {total_flags}")
    print("=" * 70)


if __name__ == "__main__":
    main()
