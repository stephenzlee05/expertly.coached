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


def _is_missing_current(current: str) -> bool:
    """True when the improver indicates new content rather than a verbatim replace."""
    if not current or not str(current).strip():
        return True
    c = str(current).strip().upper()
    if c.startswith("MISSING"):
        return True
    if c in ("N/A", "NONE", "NULL"):
        return True
    return False


def apply_improvements_to_prompt(
    current_prompt: str,
    improvement_dict: dict,
) -> tuple[str, list[str]]:
    """Apply suggested_changes from suggest_improvements() to a system prompt.

    - For MISSING / N/A / empty *current*, append *suggested* to the prompt.
    - Otherwise replace the first occurrence of *current* with *suggested*.

    Returns:
        (updated_prompt, log_lines)
    """
    notes: list[str] = []
    if not improvement_dict:
        return current_prompt, ["No improvement dict; prompt unchanged."]
    changes = improvement_dict.get("suggested_changes") or []
    if not changes:
        return current_prompt, ["No suggested_changes; prompt unchanged."]

    text = current_prompt
    for i, ch in enumerate(changes, 1):
        section = (ch.get("section") or "").strip()
        current = ch.get("current") or ""
        suggested = (ch.get("suggested") or "").strip()
        if not suggested:
            notes.append(f"Change {i}: skipped (empty suggested) [{section[:50]}]")
            continue

        if _is_missing_current(current):
            sep = "\n\n" if text.strip() else ""
            text = text.rstrip() + sep + suggested + "\n"
            notes.append(f"Change {i}: appended ({section[:60] or 'MISSING'})")
            continue

        cur = str(current).strip()
        if cur in text:
            text = text.replace(cur, suggested, 1)
            notes.append(f"Change {i}: replaced ({len(cur)} chars)")
            continue

        notes.append(
            f"Change {i}: SKIPPED — substring not found in prompt [{section[:50]}]"
        )

    return text, notes


def apply_improvements_to_assistants(coaches: dict, report: dict) -> dict[str, list[str]]:
    """Write improvement_suggestions from a run report to each coach's prompt file.

    Mutates ``coaches[slug]['prompt_text']`` when the text changes. Only assistants
    present in ``report['assistant_results']`` are updated.
    """
    out: dict[str, list[str]] = {}
    for ar in report.get("assistant_results", []):
        slug = ar.get("assistant_key")
        if not slug or slug not in coaches:
            continue
        imps = ar.get("improvement_suggestions") or {}
        old = coaches[slug]["prompt_text"]
        new_text, notes = apply_improvements_to_prompt(old, imps)
        if new_text != old:
            coaches[slug]["prompt_text"] = new_text
            coaches[slug]["prompt_file"].write_text(new_text, encoding="utf-8")
            notes.append(f"Wrote {coaches[slug]['prompt_file']}")
        out[slug] = notes
    return out
