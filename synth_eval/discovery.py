"""Auto-discover coaching assistants from prompt files."""

from pathlib import Path

# Map of known assistant keys to their VAPI IDs and labels.
# New prompts are discovered automatically; add entries here for metadata.
KNOWN_ASSISTANTS = {
    "accountability_partner": {
        "id": "69411b1f-a971-462b-a11a-61cf3b5ab715",
        "label": "Accountability Partner",
    },
    "student_success": {
        "id": "c1995689-523c-4de3-ae49-53ffb911be69",
        "label": "Student Success Coach",
    },
    "personal_performance": {
        "id": "54819721-5422-4a90-a4b9-47dc843016d0",
        "label": "Personal Performance Coach",
    },
    "founder_execution": {
        "id": "dc2284ca-a57a-4379-b981-bd65af9f9b22",
        "label": "Founder Execution Coach",
    },
    "health_weight_loss": {
        "id": "9c8b6724-7c77-46b2-86cf-6204e3dc630d",
        "label": "Weight Loss & Health Coach",
    },
    "job_search_coach": {
        "id": "3a60adef-471f-40e2-84b9-d6d4dad7cffb",
        "label": "Job Search Coach",
    },
    "sales_coach": {
        "id": "7332a873-5518-4248-b3ef-069498d2b259",
        "label": "Sales & Prospecting Coach",
    },
}


def discover_assistants(project_root: Path | None = None) -> dict[str, dict]:
    """Scan for prompt_*.txt files and return assistant configs.

    Returns dict keyed by assistant slug, e.g.:
        {
            "accountability_partner": {
                "key": "accountability_partner",
                "label": "Accountability Partner",
                "id": "69411b1f-...",
                "prompt_file": Path("prompt_accountability_partner.txt"),
                "prompt_text": "...",
            },
            ...
        }
    Any new prompt_*.txt file is automatically picked up.
    """
    root = project_root or Path(__file__).resolve().parent.parent
    assistants = {}

    for prompt_file in sorted(root.glob("prompt_*.txt")):
        # Derive slug: prompt_accountability_partner.txt -> accountability_partner
        slug = prompt_file.stem.replace("prompt_", "", 1)
        known = KNOWN_ASSISTANTS.get(slug, {})

        assistants[slug] = {
            "key": slug,
            "label": known.get("label", slug.replace("_", " ").title()),
            "id": known.get("id", f"auto_{slug}"),
            "prompt_file": prompt_file,
            "prompt_text": prompt_file.read_text(encoding="utf-8").strip(),
        }

    return assistants
