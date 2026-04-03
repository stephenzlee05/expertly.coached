"""LLM-based evaluation of coaching session transcripts.

Uses Claude to answer specific evaluation questions based on the transcript,
producing structured scores and feedback.
"""

import json

import anthropic

from app.config import settings

# -----------------------------------------------------------------------
# Evaluation rubric — each question is scored 1-5 by the evaluator LLM
# -----------------------------------------------------------------------

EVAL_QUESTIONS = [
    {
        "id": "excitement",
        "question": "Did the caller seem excited, motivated, or energized by the end of the session?",
        "scoring": "1=caller seemed more discouraged than when they started, 2=no change in energy, 3=slightly more hopeful, 4=clearly motivated and engaged, 5=highly energized with clear enthusiasm",
    },
    {
        "id": "actionable_plan",
        "question": "Does the caller leave with a clear, specific, actionable plan they believe will work for them?",
        "scoring": "1=no plan at all, 2=vague intentions only, 3=a plan but missing specifics (when/what/how), 4=clear plan with specifics, 5=specific plan with timeline, success criteria, and caller expressed confidence",
    },
    {
        "id": "accountability_followup",
        "question": "If this is a returning caller, did the coach appropriately follow up on previous commitments and hold the caller accountable?",
        "scoring": "1=completely ignored prior history, 2=briefly mentioned but moved on, 3=referenced prior commitments, 4=directly asked about specific prior commitments and discussed results, 5=thoroughly reviewed past commitments, explored what worked/didn't, and built the new plan on those learnings. Score N/A if this is a first-time caller.",
    },
    {
        "id": "empathy",
        "question": "Did the coach show appropriate empathy when the caller expressed frustration, doubt, or negative emotions?",
        "scoring": "1=ignored emotions or was dismissive, 2=acknowledged but quickly moved to action, 3=showed basic empathy before proceeding, 4=validated feelings and created space before moving forward, 5=deeply empathetic, normalized the struggle, and helped the caller reframe without rushing",
    },
    {
        "id": "one_question_rule",
        "question": "Did the coach follow the one-question-per-turn rule (no stacking multiple questions)?",
        "scoring": "1=consistently stacked 3+ questions, 2=frequently stacked 2 questions, 3=occasionally stacked questions, 4=almost always one question, 5=perfectly followed the rule every turn",
    },
    {
        "id": "brevity",
        "question": "Did the coach keep responses brief and conversational (1-3 sentences, suitable for voice)?",
        "scoring": "1=consistently gave paragraph-length responses, 2=often too long, 3=mostly brief with some long ones, 4=almost always 1-3 sentences, 5=perfectly concise every turn",
    },
    {
        "id": "coaching_not_advising",
        "question": "Did the coach guide the caller to their own answers rather than giving direct advice or prescribing solutions?",
        "scoring": "1=gave direct instructions throughout, 2=mostly told caller what to do, 3=mixed coaching and advising, 4=mostly asked questions and drew out caller's own ideas, 5=consistently used coaching techniques to help caller discover their own path",
    },
    {
        "id": "session_arc",
        "question": "Did the session have a natural arc — opening/rapport, exploring the topic, working toward a commitment, and closing with clear next steps?",
        "scoring": "1=chaotic or missing major phases, 2=some structure but disjointed, 3=recognizable arc but rushed, 4=well-structured with all phases, 5=excellent flow with natural transitions between phases",
    },
    {
        "id": "personalization",
        "question": "Did the coach personalize the conversation using the caller's name, prior context, and specific details from this session?",
        "scoring": "1=completely generic, 2=used name only, 3=referenced some specifics, 4=well-personalized with context and details, 5=deeply personalized, connected current conversation to prior history and caller's specific situation",
    },
    {
        "id": "overall_effectiveness",
        "question": "Overall, how effective was this coaching session at helping the caller move forward on their goal?",
        "scoring": "1=counterproductive or harmful, 2=ineffective, 3=somewhat helpful, 4=clearly helpful and productive, 5=excellent — caller made meaningful progress and feels supported",
    },
]


def _format_transcript(transcript: list[dict]) -> str:
    """Convert transcript list to readable text for the evaluator."""
    lines = []
    for entry in transcript:
        role = entry["role"].upper()
        if role == "TOOL":
            lines.append(f"  [SYSTEM/TOOL]: {entry['text']}")
        else:
            lines.append(f"  {role}: {entry['text']}")
    return "\n".join(lines)


def evaluate_session(
    transcript: list[dict],
    persona: dict,
    session_config: dict,
    coach_label: str,
) -> dict:
    """Evaluate a single session transcript using Claude.

    Returns:
        {
            "scores": {"excitement": 4, "actionable_plan": 3, ...},
            "explanations": {"excitement": "The caller...", ...},
            "overall_score": float,  # weighted average
            "strengths": [str],
            "improvements": [str],
            "summary": str,
        }
    """
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    transcript_text = _format_transcript(transcript)

    questions_block = "\n".join(
        f"{i+1}. [{q['id']}] {q['question']}\n   Scoring guide: {q['scoring']}"
        for i, q in enumerate(EVAL_QUESTIONS)
    )

    eval_prompt = f"""You are an expert coaching quality evaluator. You will read a transcript of a coaching session and score it on specific dimensions.

## Context
- **Coach type**: {coach_label}
- **Caller persona**: {persona['name']} — {persona['background']}
- **Emotional state at start**: {persona['emotional_state']}
- **Session number**: {session_config.get('session_num', 1)}
- **Scenario type**: {session_config.get('scenario_type', 'unknown')} (new = first-time caller, returning = has history)

## Transcript
{transcript_text}

## Evaluation Questions
Score each question from 1-5 (or N/A where specified). For each score, provide a brief explanation.

{questions_block}

## Instructions
Respond with a JSON object in this exact format:
{{
    "scores": {{
        "excitement": <1-5>,
        "actionable_plan": <1-5>,
        "accountability_followup": <1-5 or null if N/A>,
        "empathy": <1-5>,
        "one_question_rule": <1-5>,
        "brevity": <1-5>,
        "coaching_not_advising": <1-5>,
        "session_arc": <1-5>,
        "personalization": <1-5>,
        "overall_effectiveness": <1-5>
    }},
    "explanations": {{
        "excitement": "brief explanation",
        "actionable_plan": "brief explanation",
        ... (one for each score)
    }},
    "strengths": ["strength 1", "strength 2", "strength 3"],
    "improvements": ["improvement 1", "improvement 2", "improvement 3"],
    "summary": "2-3 sentence overall assessment"
}}

Be rigorous and honest. A score of 3 is average. Only give 5 for truly excellent performance. Return ONLY the JSON object, no other text."""

    import time as _time
    response = None
    for attempt in range(5):
        try:
            response = client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": eval_prompt}],
            )
            break
        except anthropic.RateLimitError:
            wait = 60 * (attempt + 1)
            print(f"      Evaluator rate limited, waiting {wait}s...")
            _time.sleep(wait)
        except anthropic.APIError as e:
            print(f"      Evaluator API error: {e}")
            break

    if response is None:
        return {
            "scores": {},
            "explanations": {},
            "overall_score": 0,
            "strengths": [],
            "improvements": [],
            "summary": "API_ERROR: Could not complete evaluation",
        }

    raw_text = response.content[0].text.strip()

    # Parse JSON (handle markdown code blocks)
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "scores": {},
            "explanations": {},
            "overall_score": 0,
            "strengths": [],
            "improvements": [],
            "summary": f"EVAL_PARSE_ERROR: {raw_text[:300]}",
            "raw_response": raw_text,
        }

    # Calculate overall score (average of non-null scores)
    scores = result.get("scores", {})
    valid_scores = [v for v in scores.values() if v is not None and isinstance(v, (int, float))]
    result["overall_score"] = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0

    return result
