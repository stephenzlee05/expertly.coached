"""Generate human-readable reports from evaluation results."""

from datetime import datetime


def generate_summary(full_report: dict) -> str:
    """Generate a human-readable summary of the full evaluation report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  SYNTHETIC EVALUATION REPORT")
    lines.append(f"  Version: {full_report.get('version', '?')}")
    lines.append(f"  Date: {full_report.get('timestamp', datetime.now().isoformat())}")
    lines.append(f"  Coaches tested: {full_report.get('coaches_tested', 0)}")
    lines.append(f"  Total sessions: {full_report.get('total_sessions', 0)}")
    lines.append(f"  Overall score: {full_report.get('overall_score', 0):.2f} / 5.00")
    lines.append("=" * 70)
    lines.append("")

    # Per-assistant breakdown
    for ar in full_report.get("assistant_results", []):
        lines.append("-" * 70)
        lines.append(f"  {ar['assistant_label']}")
        lines.append(f"  Average score: {ar.get('average_score', 0):.2f} / 5.00")
        lines.append("-" * 70)

        # Per-session results
        for sr in ar.get("session_results", []):
            persona = sr.get("persona_name", "?")
            session_num = sr.get("session_num", "?")
            overall = sr.get("evaluation", {}).get("overall_score", 0)
            lines.append(f"")
            lines.append(f"  Persona: {persona} (Session {session_num})")
            lines.append(f"  Score: {overall:.2f} / 5.00")

            # Individual scores
            scores = sr.get("evaluation", {}).get("scores", {})
            if scores:
                lines.append(f"  Scores:")
                for key, val in scores.items():
                    val_str = f"{val}" if val is not None else "N/A"
                    bar = _score_bar(val) if val is not None else "  N/A"
                    lines.append(f"    {key:30s} {val_str:>3s}  {bar}")

            # Protocol flags
            flags = sr.get("protocol_flags", [])
            if flags:
                lines.append(f"  Protocol issues:")
                for f in flags:
                    lines.append(f"    [!] {f}")

            # Strengths & improvements
            strengths = sr.get("evaluation", {}).get("strengths", [])
            improvements = sr.get("evaluation", {}).get("improvements", [])
            if strengths:
                lines.append(f"  Strengths:")
                for s in strengths:
                    lines.append(f"    + {s}")
            if improvements:
                lines.append(f"  Improvements:")
                for imp in improvements:
                    lines.append(f"    - {imp}")

            lines.append("")

        # Improvement suggestions
        improvement_suggestions = ar.get("improvement_suggestions", {})
        if improvement_suggestions and improvement_suggestions.get("suggested_changes"):
            lines.append(f"  === SUGGESTED PROMPT IMPROVEMENTS ===")
            lines.append(f"  Priority: {improvement_suggestions.get('priority', '?')}")
            lines.append(f"  Analysis: {improvement_suggestions.get('analysis', '?')}")
            for change in improvement_suggestions.get("suggested_changes", []):
                lines.append(f"")
                lines.append(f"  Section: {change.get('section', '?')}")
                lines.append(f"  Reason:  {change.get('reason', '?')}")
                lines.append(f"  Change:  {change.get('suggested', '?')[:200]}")
            lines.append("")

    # Overall summary
    lines.append("=" * 70)
    lines.append("  SCORE LEADERBOARD")
    lines.append("=" * 70)

    sorted_assistants = sorted(
        full_report.get("assistant_results", []),
        key=lambda x: x.get("average_score", 0),
        reverse=True,
    )
    for i, ar in enumerate(sorted_assistants, 1):
        score = ar.get("average_score", 0)
        bar = _score_bar(score)
        lines.append(f"  {i}. {ar['assistant_label']:35s} {score:.2f}  {bar}")

    lines.append("")
    lines.append(f"  Overall: {full_report.get('overall_score', 0):.2f} / 5.00")
    lines.append("=" * 70)

    return "\n".join(lines)


def _score_bar(score, max_score=5, width=20) -> str:
    """Create a visual score bar."""
    if score is None or not isinstance(score, (int, float)):
        return ""
    filled = int((score / max_score) * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def format_transcript(transcript: list[dict]) -> str:
    """Format a transcript for display."""
    lines = []
    for entry in transcript:
        role = entry["role"]
        if role == "caller":
            lines.append(f"  Caller: {entry['text']}")
        elif role == "coach":
            lines.append(f"  Coach:  {entry['text']}")
        elif role == "tool":
            lines.append(f"  [Tool]: {entry['text'][:150]}")
    return "\n".join(lines)
