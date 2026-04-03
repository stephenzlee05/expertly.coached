"""Self-improvement cycle: analyze evaluation results and suggest prompt improvements."""

import json

import anthropic

from app.config import settings


def suggest_improvements(
    coach_label: str,
    current_prompt: str,
    evaluation_results: list[dict],
) -> dict:
    """Analyze evaluation results and suggest concrete prompt improvements.

    Args:
        coach_label: Name of the coaching assistant.
        current_prompt: Current system prompt text.
        evaluation_results: List of evaluation dicts from evaluator.evaluate_session().

    Returns:
        {
            "analysis": str,
            "suggested_changes": [
                {"section": str, "current": str, "suggested": str, "reason": str}
            ],
            "priority": str,  # "high", "medium", "low"
        }
    """
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Build scores summary
    scores_summary = []
    all_improvements = []
    all_strengths = []
    for ev in evaluation_results:
        scores = ev.get("scores", {})
        scores_summary.append(scores)
        all_improvements.extend(ev.get("improvements", []))
        all_strengths.extend(ev.get("strengths", []))

    # Average scores across sessions
    avg_scores = {}
    for key in scores_summary[0] if scores_summary else []:
        vals = [s.get(key) for s in scores_summary if s.get(key) is not None and isinstance(s.get(key), (int, float))]
        if vals:
            avg_scores[key] = round(sum(vals) / len(vals), 2)

    # Find weakest areas
    weak_areas = sorted(avg_scores.items(), key=lambda x: x[1])[:3]

    prompt = f"""You are an expert prompt engineer for coaching AI systems. Analyze the evaluation results and suggest specific improvements to the system prompt.

## Coach: {coach_label}

## Current System Prompt (first 2000 chars):
{current_prompt[:2000]}

## Average Scores Across All Test Sessions:
{json.dumps(avg_scores, indent=2)}

## Weakest Areas:
{json.dumps(weak_areas, indent=2)}

## Recurring Improvement Suggestions from Evaluator:
{json.dumps(all_improvements, indent=2)}

## Recurring Strengths:
{json.dumps(all_strengths, indent=2)}

## Instructions:
Analyze the weak spots and suggest 2-4 specific, targeted changes to the system prompt. For each change:
1. Identify the section of the prompt to modify
2. Explain what's currently there (or missing)
3. Suggest the specific new text to add or replace
4. Explain why this change will improve the weak score

Respond with JSON:
{{
    "analysis": "2-3 sentence analysis of the main issues",
    "suggested_changes": [
        {{
            "section": "which part of the prompt to modify",
            "current": "what's currently there (or 'MISSING')",
            "suggested": "the new text to add or replace",
            "reason": "why this helps"
        }}
    ],
    "priority": "high|medium|low"
}}

Return ONLY the JSON."""

    import time as _time
    response = None
    for attempt in range(5):
        try:
            response = client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            break
        except anthropic.RateLimitError:
            wait = 15 * (attempt + 1)
            print(f"      Improver rate limited, waiting {wait}s...")
            _time.sleep(wait)

    if response is None:
        return {
            "analysis": "Rate limit exhausted",
            "suggested_changes": [],
            "priority": "unknown",
        }

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "analysis": f"Failed to parse improvement suggestions: {raw[:300]}",
            "suggested_changes": [],
            "priority": "unknown",
        }
