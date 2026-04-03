"""Version prompts and evaluation results.

Each evaluation run creates a versioned snapshot:
    synth_eval/versions/v001/
        prompts/                  # copy of all prompt files at time of eval
        results/                  # JSON results per assistant
        report.json               # full evaluation report
        summary.txt               # human-readable summary
"""

import json
import shutil
from datetime import datetime
from pathlib import Path


def get_versions_dir() -> Path:
    return Path(__file__).resolve().parent / "versions"


def get_next_version() -> str:
    """Return the next version string like 'v001', 'v002', etc."""
    versions_dir = get_versions_dir()
    if not versions_dir.exists():
        versions_dir.mkdir(parents=True, exist_ok=True)
        return "v001"

    existing = sorted([
        d.name for d in versions_dir.iterdir()
        if d.is_dir() and d.name.startswith("v") and d.name[1:].isdigit()
    ])

    if not existing:
        return "v001"

    last_num = int(existing[-1][1:])
    return f"v{last_num + 1:03d}"


def create_version_snapshot(
    version: str,
    assistants: dict,
    full_report: dict,
    summary_text: str,
) -> Path:
    """Create a versioned snapshot of prompts and results.

    Args:
        version: Version string like 'v001'.
        assistants: Dict of discovered assistants (contains prompt_text).
        full_report: Complete evaluation report dict.
        summary_text: Human-readable summary text.

    Returns:
        Path to the version directory.
    """
    version_dir = get_versions_dir() / version
    prompts_dir = version_dir / "prompts"
    results_dir = version_dir / "results"

    prompts_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    # Save prompt snapshots
    for slug, assistant in assistants.items():
        prompt_file = prompts_dir / f"{slug}.txt"
        prompt_file.write_text(assistant["prompt_text"], encoding="utf-8")

    # Save per-assistant results
    for assistant_result in full_report.get("assistant_results", []):
        slug = assistant_result["assistant_key"]
        result_file = results_dir / f"{slug}.json"
        result_file.write_text(
            json.dumps(assistant_result, indent=2, default=str),
            encoding="utf-8",
        )

    # Save full report
    report_file = version_dir / "report.json"
    report_file.write_text(
        json.dumps(full_report, indent=2, default=str),
        encoding="utf-8",
    )

    # Save human-readable summary
    summary_file = version_dir / "summary.txt"
    summary_file.write_text(summary_text, encoding="utf-8")

    # Save metadata
    meta = {
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "assistants_tested": list(assistants.keys()),
        "overall_score": full_report.get("overall_score", 0),
    }
    meta_file = version_dir / "metadata.json"
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return version_dir


def list_versions() -> list[dict]:
    """List all versions with their metadata."""
    versions_dir = get_versions_dir()
    if not versions_dir.exists():
        return []

    versions = []
    for d in sorted(versions_dir.iterdir()):
        if not d.is_dir() or not d.name.startswith("v"):
            continue
        meta_file = d / "metadata.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            versions.append(meta)
        else:
            versions.append({"version": d.name, "timestamp": "unknown"})

    return versions


def compare_versions(v1: str, v2: str) -> dict:
    """Compare scores between two versions."""
    versions_dir = get_versions_dir()
    r1_path = versions_dir / v1 / "report.json"
    r2_path = versions_dir / v2 / "report.json"

    if not r1_path.exists() or not r2_path.exists():
        return {"error": f"One or both versions not found: {v1}, {v2}"}

    r1 = json.loads(r1_path.read_text(encoding="utf-8"))
    r2 = json.loads(r2_path.read_text(encoding="utf-8"))

    return {
        "v1": v1,
        "v2": v2,
        "v1_overall": r1.get("overall_score", 0),
        "v2_overall": r2.get("overall_score", 0),
        "delta": round(r2.get("overall_score", 0) - r1.get("overall_score", 0), 2),
    }
