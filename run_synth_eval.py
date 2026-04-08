"""
Synthetic Evaluation Framework for Coaching Assistants.

Runs simulated coaching sessions with diverse personas, evaluates quality
with an LLM-based rubric, versions everything, and suggests improvements.

Usage:
    python run_synth_eval.py                        # full run, all coaches, all personas
    python run_synth_eval.py --coach accountability_partner  # single coach
    python run_synth_eval.py --cycles 3             # run 3 improvement cycles
    python run_synth_eval.py --list-versions        # show past runs
    python run_synth_eval.py --compare v001 v002    # compare two versions
    python run_synth_eval.py --verbose               # show full transcripts
    python run_synth_eval.py --no-apply-prompts      # eval only; do not write prompt_*.txt
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from synth_eval.discovery import discover_assistants
from synth_eval.personas import get_personas_for_coach
from synth_eval.simulator import run_full_persona
from synth_eval.evaluator import evaluate_session
from synth_eval.improver import (
    apply_improvements_to_assistants,
    suggest_improvements,
)
from synth_eval.versioning import (
    get_next_version,
    create_version_snapshot,
    list_versions,
    compare_versions,
)
from synth_eval.report import generate_summary, format_transcript


def run_evaluation(
    coaches: dict,
    verbose: bool = False,
) -> dict:
    """Run full evaluation across all coaches and personas.

    Returns the complete report dict.
    """
    all_assistant_results = []
    total_sessions = 0

    for slug, assistant in coaches.items():
        print(f"\n{'='*60}")
        print(f"  Evaluating: {assistant['label']}")
        print(f"{'='*60}")

        personas = get_personas_for_coach(slug)
        if not personas:
            print(f"  No personas configured for {slug}, skipping.")
            continue

        session_results = []

        for persona in personas:
            print(f"\n  Persona: {persona['name']} ({persona['id']})")
            print(f"  Background: {persona['background']}")
            print(f"  Sessions: {len(persona['sessions'])}")

            try:
                # Run all sessions for this persona
                sim_results = run_full_persona(
                    system_prompt=assistant["prompt_text"],
                    persona=persona,
                    assistant_id=assistant["id"],
                )
            except Exception as e:
                print(f"    ERROR simulating persona {persona['name']}: {e}")
                continue

            for sim_result in sim_results:
                session_num = sim_result["session_num"]
                session_config = persona["sessions"][session_num - 1]
                total_sessions += 1

                print(f"    Session {session_num}: {sim_result['turn_count']} turns, "
                      f"{len(sim_result['protocol_flags'])} protocol flags")

                if verbose:
                    print(f"\n{format_transcript(sim_result['transcript'])}\n")

                if sim_result["protocol_flags"]:
                    for flag in sim_result["protocol_flags"]:
                        print(f"      [!] {flag}")

                # Evaluate the session
                try:
                    print(f"    Evaluating session {session_num}...")
                    evaluation = evaluate_session(
                        transcript=sim_result["transcript"],
                        persona=persona,
                        session_config=session_config,
                        coach_label=assistant["label"],
                    )
                except Exception as e:
                    print(f"    ERROR evaluating session: {e}")
                    evaluation = {
                        "scores": {},
                        "explanations": {},
                        "overall_score": 0,
                        "strengths": [],
                        "improvements": [],
                        "summary": f"Evaluation failed: {e}",
                    }

                overall = evaluation.get("overall_score", 0)
                print(f"    Score: {overall:.2f}/5.00")

                # Print key scores inline
                scores = evaluation.get("scores", {})
                for key in ["excitement", "actionable_plan", "accountability_followup", "empathy"]:
                    val = scores.get(key)
                    if val is not None:
                        print(f"      {key}: {val}/5")

                session_results.append({
                    "persona_id": persona["id"],
                    "persona_name": persona["name"],
                    "session_num": session_num,
                    "turn_count": sim_result["turn_count"],
                    "transcript": sim_result["transcript"],
                    "tool_calls": sim_result["tool_calls"],
                    "protocol_flags": sim_result["protocol_flags"],
                    "evaluation": evaluation,
                })

                time.sleep(2)  # rate limiting

        # Calculate average score for this assistant
        eval_scores = [
            sr["evaluation"].get("overall_score", 0)
            for sr in session_results
            if sr["evaluation"].get("overall_score", 0) > 0
        ]
        avg_score = sum(eval_scores) / len(eval_scores) if eval_scores else 0

        print(f"\n  {assistant['label']} average: {avg_score:.2f}/5.00")

        # Generate improvement suggestions
        print(f"  Generating improvement suggestions...")
        try:
            improvements = suggest_improvements(
                coach_label=assistant["label"],
                current_prompt=assistant["prompt_text"],
                evaluation_results=[sr["evaluation"] for sr in session_results],
            )
        except Exception as e:
            print(f"  ERROR generating improvements: {e}")
            improvements = {"analysis": str(e), "suggested_changes": [], "priority": "unknown"}

        if improvements.get("suggested_changes"):
            print(f"  Priority: {improvements.get('priority', '?')}")
            print(f"  {improvements.get('analysis', '')[:150]}")

        all_assistant_results.append({
            "assistant_key": slug,
            "assistant_label": assistant["label"],
            "session_results": session_results,
            "average_score": round(avg_score, 2),
            "improvement_suggestions": improvements,
        })

    # Overall score
    all_avgs = [ar["average_score"] for ar in all_assistant_results if ar["average_score"] > 0]
    overall_score = sum(all_avgs) / len(all_avgs) if all_avgs else 0

    report = {
        "timestamp": datetime.now().isoformat(),
        "coaches_tested": len(coaches),
        "total_sessions": total_sessions,
        "overall_score": round(overall_score, 2),
        "assistant_results": all_assistant_results,
    }

    return report


def run_improvement_cycle(
    coaches: dict,
    num_cycles: int = 1,
    verbose: bool = False,
    apply_prompts: bool = True,
):
    """Run multiple evaluation-improvement cycles.

    After each cycle, snapshots are saved with the prompts that were *evaluated*.
    If ``apply_prompts`` is True, suggested improvements are applied to ``prompt_*.txt``
    so the next cycle (or your working tree) uses the updated prompts.
    """

    for cycle in range(1, num_cycles + 1):
        print(f"\n{'#'*60}")
        print(f"  CYCLE {cycle} of {num_cycles}")
        print(f"{'#'*60}")

        # Get version
        version = get_next_version()

        # Run evaluation
        report = run_evaluation(coaches, verbose=verbose)
        report["version"] = version
        report["cycle"] = cycle

        # Generate summary
        summary = generate_summary(report)

        # Save version
        version_dir = create_version_snapshot(
            version=version,
            assistants=coaches,
            full_report=report,
            summary_text=summary,
        )

        print(f"\n{'='*60}")
        print(summary)
        print(f"\n  Saved to: {version_dir}")

        if apply_prompts:
            print(f"\n  --- Applying prompt updates ---")
            logs = apply_improvements_to_assistants(coaches, report)
            if not logs:
                print("  (No assistant results to apply.)")
            for slug, lines in logs.items():
                print(f"  {slug}:")
                for line in lines:
                    print(f"    {line}")
        elif cycle < num_cycles:
            print(
                "\n  Note: --no-apply-prompts set; next cycle will use the same prompt files."
            )


def main():
    parser = argparse.ArgumentParser(
        description="Synthetic evaluation framework for coaching assistants",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--coach",
        help="Run only this coach (by slug, e.g. 'accountability_partner')",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="Number of evaluation cycles to run (default: 1)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full transcripts during evaluation",
    )
    parser.add_argument(
        "--no-apply-prompts",
        action="store_true",
        help="Do not write suggested changes to prompt_*.txt after each cycle",
    )
    parser.add_argument(
        "--list-versions",
        action="store_true",
        help="List all past evaluation versions",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("V1", "V2"),
        help="Compare two versions (e.g. --compare v001 v002)",
    )
    parser.add_argument(
        "--show-version",
        help="Show the summary for a specific version",
    )

    args = parser.parse_args()

    # Handle list-versions
    if args.list_versions:
        versions = list_versions()
        if not versions:
            print("No evaluation versions found.")
            return
        print(f"\n{'='*60}")
        print("  EVALUATION VERSIONS")
        print(f"{'='*60}")
        for v in versions:
            score = v.get("overall_score", "?")
            ts = v.get("timestamp", "?")
            coaches = ", ".join(v.get("assistants_tested", []))
            print(f"  {v['version']:6s}  score={score}  {ts}  [{coaches}]")
        print(f"{'='*60}")
        return

    # Handle compare
    if args.compare:
        result = compare_versions(args.compare[0], args.compare[1])
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        print(f"\n  {result['v1']}: {result['v1_overall']:.2f}")
        print(f"  {result['v2']}: {result['v2_overall']:.2f}")
        delta = result["delta"]
        direction = "improved" if delta > 0 else "regressed" if delta < 0 else "unchanged"
        print(f"  Delta: {delta:+.2f} ({direction})")
        return

    # Handle show-version
    if args.show_version:
        from synth_eval.versioning import get_versions_dir
        summary_file = get_versions_dir() / args.show_version / "summary.txt"
        if not summary_file.exists():
            print(f"Version {args.show_version} not found.")
            return
        print(summary_file.read_text(encoding="utf-8"))
        return

    # Discover assistants
    coaches = discover_assistants()
    if not coaches:
        print("No coaching prompts found (prompt_*.txt). Check your working directory.")
        sys.exit(1)

    # Filter to single coach if specified
    if args.coach:
        if args.coach not in coaches:
            print(f"Coach '{args.coach}' not found. Available: {', '.join(coaches.keys())}")
            sys.exit(1)
        coaches = {args.coach: coaches[args.coach]}

    print(f"\n  Discovered {len(coaches)} coaching assistant(s):")
    for slug, assistant in coaches.items():
        print(f"    - {slug}: {assistant['label']}")
    print()

    # Run evaluation cycles
    run_improvement_cycle(
        coaches=coaches,
        num_cycles=args.cycles,
        verbose=args.verbose,
        apply_prompts=not args.no_apply_prompts,
    )


if __name__ == "__main__":
    main()
