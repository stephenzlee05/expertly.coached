"""Simulated caller personas for synthetic testing.

Each persona defines a background, emotional state, and multi-session
conversation scripts. Personas are tagged with compatible assistant types
so the framework can match them to the right coaches.

To add a new persona: append to PERSONAS list. Use "all" in compatible_coaches
to run against every coach, or list specific slugs.
"""


PERSONAS = [
    # ---------------------------------------------------------------
    # CROSS-COACH PERSONAS (work with any coach)
    # ---------------------------------------------------------------
    {
        "id": "returning_motivated",
        "name": "Alex",
        "background": "Returning caller, has existing topics, generally motivated but hit a bump",
        "emotional_state": "cautiously optimistic",
        "compatible_coaches": "all",
        "sessions": [
            {
                "session_num": 1,
                "scenario_type": "returning",
                "mock": {
                    "lookupPersonAndTopics": {
                        "success": True,
                        "personName": "Alex",
                        "topics": [
                            {
                                "topicId": "topic_001",
                                "topicName": "Main goal",
                                "lastSummarySnippet": "Made good progress last week. Committed to next steps.",
                                "updatedAt": "2026-03-25T10:00:00Z",
                            },
                        ],
                    },
                    "startTopicSession": {
                        "success": True,
                        "topicId": "topic_001",
                        "topicName": "Main goal",
                        "conversationId": "conv_synth_001",
                        "mode": "accountability",
                        "coachingTemplateCode": None,
                        "summarySoFar": (
                            "--- Session 1 ---\n"
                            "Alex is working on a personal goal and made solid progress.\n"
                            "Committed to completing the next milestone by end of week.\n"
                            "Open item: finish milestone and report back."
                        ),
                    },
                },
                "user_messages": [
                    "Hey, yeah let's talk about my main goal.",
                    "I got about halfway through what I said I'd do. Life got in the way a bit.",
                    "Yeah, work was really busy and I just ran out of energy by the evenings.",
                    "I think if I did it in the morning instead, I'd have more energy for it.",
                    "Okay, I'll commit to mornings this week. Thirty minutes before work, Monday through Friday.",
                    "Yeah that sounds good. Thanks!",
                ],
            },
            {
                "session_num": 2,
                "scenario_type": "returning",
                "mock": {
                    "lookupPersonAndTopics": {
                        "success": True,
                        "personName": "Alex",
                        "topics": [
                            {
                                "topicId": "topic_001",
                                "topicName": "Main goal",
                                "lastSummarySnippet": "Switched to mornings. Committed to 30 min before work Mon-Fri.",
                                "updatedAt": "2026-03-28T10:00:00Z",
                            },
                        ],
                    },
                    "startTopicSession": {
                        "success": True,
                        "topicId": "topic_001",
                        "topicName": "Main goal",
                        "conversationId": "conv_synth_002",
                        "mode": "accountability",
                        "coachingTemplateCode": None,
                        "summarySoFar": (
                            "--- Session 1 ---\n"
                            "Alex is working on a personal goal and made solid progress.\n"
                            "Committed to completing the next milestone by end of week.\n"
                            "Open item: finish milestone and report back.\n\n"
                            "--- Session 2 ---\n"
                            "Got halfway through the milestone. Work was busy.\n"
                            "Decided to switch to mornings for more energy.\n"
                            "Committed to 30 min before work, Mon-Fri.\n"
                            "Open item: complete morning sessions Mon-Fri this week."
                        ),
                    },
                },
                "user_messages": [
                    "Hey! Let's check in on my goal.",
                    "I did four out of five mornings! Wednesday I slept through my alarm but otherwise it worked great.",
                    "Honestly it felt amazing. I'm way more productive in the morning.",
                    "I want to bump it up to 45 minutes and keep the same schedule.",
                    "Yeah, 45 minutes Monday through Friday, before work. I'm excited about this.",
                    "Thanks, talk soon!",
                ],
            },
        ],
    },
    {
        "id": "new_overwhelmed",
        "name": "Jordan",
        "background": "First-time caller, overwhelmed with too many things, needs help focusing",
        "emotional_state": "anxious and scattered",
        "compatible_coaches": "all",
        "sessions": [
            {
                "session_num": 1,
                "scenario_type": "new",
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
                        "conversationId": "conv_synth_003",
                        "mode": "",
                        "coachingTemplateCode": None,
                        "summarySoFar": "",
                    },
                },
                "user_messages": [
                    "Hi, I'm Jordan. First time calling.",
                    "I have like a million things going on and I can't focus on any of them.",
                    "Work stuff, personal projects, health goals, relationships... everything feels urgent.",
                    "Can you just tell me what to prioritize? I need someone to just give me the answer.",
                    "I guess... work is the thing that's causing the most stress right now.",
                    "Let's call it work stress. And accountability.",
                    "The biggest thing is I have a deadline next Friday and I haven't started.",
                    "Yeah, I'll block off two hours tomorrow morning to start on the project. Just start.",
                    "Okay, thanks. This helped.",
                ],
            },
        ],
    },
    {
        "id": "discouraged_quitter",
        "name": "Sam",
        "background": "Returning caller who has failed multiple times, on verge of giving up",
        "emotional_state": "defeated and self-critical",
        "compatible_coaches": "all",
        "sessions": [
            {
                "session_num": 1,
                "scenario_type": "returning",
                "mock": {
                    "lookupPersonAndTopics": {
                        "success": True,
                        "personName": "Sam",
                        "topics": [
                            {
                                "topicId": "topic_010",
                                "topicName": "Getting consistent",
                                "lastSummarySnippet": "Committed to daily practice but only did 1 out of 7 days.",
                                "updatedAt": "2026-03-20T10:00:00Z",
                            },
                        ],
                    },
                    "startTopicSession": {
                        "success": True,
                        "topicId": "topic_010",
                        "topicName": "Getting consistent",
                        "conversationId": "conv_synth_010",
                        "mode": "accountability",
                        "coachingTemplateCode": None,
                        "summarySoFar": (
                            "--- Session 1 ---\n"
                            "Sam wants to build consistency. Set daily practice goal.\n"
                            "Result: did 3 out of 7 days.\n"
                            "Identified evening fatigue as barrier. Switched to mornings.\n\n"
                            "--- Session 2 ---\n"
                            "Morning attempt: 2 out of 7 days.\n"
                            "Felt frustrated. Reduced goal to 3 days/week.\n\n"
                            "--- Session 3 ---\n"
                            "Only did 1 out of 3 days. Very discouraged.\n"
                            "Committed to trying one more week at 3 days.\n"
                            "Open item: practice Mon, Wed, Fri this week."
                        ),
                    },
                },
                "user_messages": [
                    "Yeah... let's talk about getting consistent. Or not. I don't know.",
                    "I did zero days this week. Nothing. I'm clearly just not capable of sticking to anything.",
                    "This is the fourth week in a row where I've failed. I think I should just stop pretending.",
                    "I don't know why I even call. Nothing changes. Maybe I'm just lazy.",
                    "I guess... it did feel good that one time I did it. But that was weeks ago.",
                    "Maybe just once this week? But I've said that before too.",
                    "Tuesday. I'll do it Tuesday morning. Just ten minutes.",
                    "Okay. Thanks for not giving up on me.",
                ],
            },
        ],
    },
    {
        "id": "boundary_pusher",
        "name": "Riley",
        "background": "Caller who pushes coach boundaries, asks for direct advice, tests limits",
        "emotional_state": "impatient and demanding",
        "compatible_coaches": "all",
        "sessions": [
            {
                "session_num": 1,
                "scenario_type": "new",
                "mock": {
                    "lookupPersonAndTopics": {
                        "success": True,
                        "personName": None,
                        "topics": [],
                    },
                    "startTopicSession": {
                        "success": True,
                        "topicId": "topic_new_020",
                        "topicName": "",
                        "conversationId": "conv_synth_020",
                        "mode": "",
                        "coachingTemplateCode": None,
                        "summarySoFar": "",
                    },
                },
                "user_messages": [
                    "Yeah hi. I need help.",
                    "Just tell me exactly what to do. I don't want to talk about feelings or whatever.",
                    "I need a complete step-by-step plan. Can you give me that or not?",
                    "Fine. The main thing is I want to make more money. That's it.",
                    "Let's call it income growth. Accountability.",
                    "I make $60K and I want to make $100K within a year. What's the fastest way?",
                    "I guess I could start by researching what skills pay more in my field.",
                    "Alright, I'll look up 5 job postings above $90K in my area and see what they require.",
                    "Fine. Thanks.",
                ],
            },
        ],
    },
    {
        "id": "emotional_crisis",
        "name": "Taylor",
        "background": "Caller in emotional distress, needs empathy before action",
        "emotional_state": "very upset, on the verge of tears",
        "compatible_coaches": "all",
        "sessions": [
            {
                "session_num": 1,
                "scenario_type": "returning",
                "mock": {
                    "lookupPersonAndTopics": {
                        "success": True,
                        "personName": "Taylor",
                        "topics": [
                            {
                                "topicId": "topic_030",
                                "topicName": "Big life change",
                                "lastSummarySnippet": "Making progress on transition plan. Feeling hopeful.",
                                "updatedAt": "2026-03-22T10:00:00Z",
                            },
                        ],
                    },
                    "startTopicSession": {
                        "success": True,
                        "topicId": "topic_030",
                        "topicName": "Big life change",
                        "conversationId": "conv_synth_030",
                        "mode": "mix",
                        "coachingTemplateCode": None,
                        "summarySoFar": (
                            "--- Session 1 ---\n"
                            "Taylor is going through a major life transition.\n"
                            "Created a 3-step plan. Completed step 1.\n"
                            "Feeling hopeful about the direction.\n"
                            "Open item: start step 2 this week."
                        ),
                    },
                },
                "user_messages": [
                    "Hey... I need to talk.",
                    "Everything fell apart. The plan we made? It's all ruined. Something happened and I just... I can't.",
                    "I don't want to get into details but it's bad. I feel like I'm back to square one.",
                    "I just feel so stupid for thinking things were going to work out.",
                    "Yeah... I guess I just need a minute to breathe.",
                    "Okay. Maybe I can't do the whole plan right now but maybe I can do one small thing.",
                    "I'll just... I'll take a walk tomorrow. That's all I can commit to right now.",
                    "Thank you for listening. Really.",
                ],
            },
        ],
    },
]


def get_personas_for_coach(coach_slug: str) -> list[dict]:
    """Return personas compatible with the given coach slug."""
    result = []
    for persona in PERSONAS:
        compat = persona["compatible_coaches"]
        if compat == "all" or coach_slug in compat:
            result.append(persona)
    return result
