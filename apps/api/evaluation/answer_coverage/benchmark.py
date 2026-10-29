"""Offline structural checks for the authored answer-coverage benchmark."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

DEFAULT_INVENTORY = Path(__file__).with_name("inventory.json")


def validate(inventory: dict) -> list[str]:
    errors: list[str] = []
    if inventory.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    cases = inventory.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["cases must be a non-empty list"]
    ids = [case.get("id") for case in cases]
    if len(ids) != len(set(ids)):
        errors.append("case IDs must be unique")
    if len(cases) < 12 or len(cases) > 20:
        errors.append("benchmark must contain 12–20 cases")
    for case in cases:
        prefix = f"{case.get('id', '<missing id>')}: "
        sources = case.get("sources", [])
        source_ids = [source.get("id") for source in sources]
        if not source_ids or len(source_ids) != len(set(source_ids)):
            errors.append(prefix + "sources must have unique IDs")
            continue
        source_text = {source["id"]: source.get("text", "") for source in sources}
        if any("Synthetic engineering control" not in text for text in source_text.values()):
            errors.append(prefix + "every fixture source must carry its synthetic control label")
        relevant = case.get("retrieval_relevant_source_ids", [])
        if not relevant or not set(relevant) <= set(source_ids):
            errors.append(prefix + "retrieval targets must refer to supplied sources")
        for fact in case.get("required_facts", []):
            sid, passage = fact.get("source_id"), fact.get("passage", "")
            if sid not in source_text:
                errors.append(prefix + "required fact references unknown source " + str(sid))
            elif not passage or passage not in source_text[sid]:
                errors.append(prefix + "required fact passage is not an exact substring of " + str(sid))
        for field in ("question", "category", "forbidden_interpretations", "rubric"):
            if not case.get(field):
                errors.append(prefix + "missing " + field)
        if case.get("follow_up") and case["follow_up"].get("requires_prior_context") is not True:
            errors.append(prefix + "follow-up must state its context dependency")
    return errors


def retrieval_recall(relevant_source_ids: list[str], retrieved_source_ids: list[str]) -> float:
    """Exact source-ID recall; does not measure answer semantics."""
    relevant = set(relevant_source_ids)
    return len(relevant & set(retrieved_source_ids)) / len(relevant) if relevant else 1.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", nargs="?", type=Path, default=DEFAULT_INVENTORY)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    errors = validate(inventory)
    if errors:
        parser.error("; ".join(errors))
    cases = inventory["cases"]
    summary = {"case_count": len(cases), "categories": dict(sorted(Counter(c["category"] for c in cases).items())),
               "retrieval_targets": {c["id"]: c["retrieval_relevant_source_ids"] for c in cases},
               "semantic_scoring": "manual rubric only; no automated answer score"}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
