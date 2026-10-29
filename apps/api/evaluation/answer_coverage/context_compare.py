"""Offline comparison of first-eight source context with ranked evidence records.

No LLM/provider is invoked. Run only after `conversation.build_evidence_records`
has landed; this deliberately imports the production helper rather than copying it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_ROOT))

from triallens.models import EvidenceSource, SourceType, Workspace  # noqa: E402
from triallens.rag import Retriever, build_chunks, citation_for  # noqa: E402

INVENTORY = Path(__file__).with_name("inventory.json")
TYPE_MAP = {"synthetic_trial": SourceType.pubmed, "synthetic_registry": SourceType.clinical_trials,
            "synthetic_followup": SourceType.pubmed, "synthetic_safety_report": SourceType.pubmed,
            "synthetic_interview_study": SourceType.pubmed, "synthetic_review": SourceType.pubmed,
            "synthetic_safety_notice": SourceType.fda_adverse_event, "synthetic_methods_note": SourceType.pubmed}


def sources_for(case: dict) -> list[EvidenceSource]:
    return [EvidenceSource(id=f"{case['id']}-{item['id']}", workspace_id="answer-coverage-fixture",
                          source_type=TYPE_MAP[item["type"]], external_id=f"DEMO-{case['id']}-{item['id']}",
                          title=item["title"], abstract=item["text"], metadata={"demo": True})
            for item in case["sources"]]


def normalized(text: str) -> str:
    return " ".join(text.split())


def coverage(case: dict, records: list[dict], chunks: list, source_by_citation: dict[str, str]) -> dict:
    contexts: dict[str, list[str]] = {}
    for record in records:
        citation = record.get("citation", "")
        source_id = source_by_citation.get(citation)
        if source_id is None:
            continue
        contexts.setdefault(source_id, []).extend([record.get("text", ""), *record.get("matched_passages", [])])
    chunks_by_source: dict[str, list[str]] = {}
    for chunk in chunks:
        # Fixture source IDs are case-id + authored source ID; anchored exact lookup
        # avoids S1 matching S10 when checking indexing and context membership.
        source_id = next((sid for sid in source_by_citation.values()
                          if chunk.source_id == f"{case['id']}-{sid}"), None)
        if source_id is not None:
            chunks_by_source.setdefault(source_id, []).append(chunk.text)
    facts = []
    for item in case["required_facts"]:
        in_context = any(normalized(item["passage"]) in normalized(text)
                         for text in contexts.get(item["source_id"], []))
        indexed = any(normalized(item["passage"]) in normalized(text)
                      for text in chunks_by_source.get(item["source_id"], []))
        facts.append({"source_id": item["source_id"], "fact": item["fact"],
                      "indexed": indexed, "in_context": in_context,
                      "status": "covered_by_context" if in_context else "not_indexed" if not indexed else "missing_from_selected_context"})
    return {"required_passages": len(facts), "covered_passages": sum(f["in_context"] for f in facts),
            "not_indexed": sum(f["status"] == "not_indexed" for f in facts),
            "missing_from_selected_context": sum(f["status"] == "missing_from_selected_context" for f in facts),
            "facts": facts}


def run(inventory: dict) -> dict:
    # Late import gives a clear failure while helper implementation is in flight.
    from triallens.conversation import build_evidence_records

    retriever = Retriever()
    rows = []
    for case in inventory["cases"]:
        sources = sources_for(case)
        workspace = Workspace(id="answer-coverage-fixture", condition="synthetic study", intervention="Example",
                              source_types=list(SourceType))
        chunks = build_chunks(sources)
        retrieved = retriever.retrieve_conversation(workspace, case["question"], chunks, sources)
        # The frozen existing behavior passes the first eight eligible input records.
        baseline_sources = sources[:8]
        selected = build_evidence_records(sources, retrieved)
        # Reconstruct its first-eight eligible set with the same production helper,
        # which applies the historical per-source/aggregate budgets and matched
        # passage handling. This isolates source selection from context rendering.
        baseline_records = build_evidence_records(baseline_sources, retrieved)
        source_by_citation = {citation_for(source): authored["id"]
                              for source, authored in zip(sources, case["sources"])}
        baseline = coverage(case, baseline_records, chunks, source_by_citation)
        candidate = coverage(case, selected, chunks, source_by_citation)
        rows.append({"case_id": case["id"], "retrieved_source_ids": list(dict.fromkeys(
                         chunk.source_id.removeprefix(case["id"] + "-") for chunk in retrieved)),
                     "baseline_first8": baseline, "ranked_helper": candidate,
                     "delta_covered_passages": candidate["covered_passages"] - baseline["covered_passages"]})
    return {"schema_version": 1, "benchmark": "answer_coverage", "provider_calls": 0,
            "semantic_answer_scoring": "not performed; manual rubric required",
            "comparison_method": {"baseline": "first eight input sources passed through the same production evidence-record builder, preserving its source budgets, matched passages, and truncation behavior",
                                 "candidate": "all eligible input sources passed through the production evidence-record builder with ranked retrieved chunks",
                                 "passage_indexing": "exact required passage membership in chunks for that exact source ID",
                                 "context_membership": "exact required passage membership in that source record text or matched_passages"},
            "cases": rows,
            "summary": {"case_count": len(rows),
                        "baseline_covered_passages": sum(r["baseline_first8"]["covered_passages"] for r in rows),
                        "helper_covered_passages": sum(r["ranked_helper"]["covered_passages"] for r in rows),
                        "baseline_not_indexed": sum(r["baseline_first8"]["not_indexed"] for r in rows),
                        "helper_not_indexed": sum(r["ranked_helper"]["not_indexed"] for r in rows),
                        "baseline_missing_from_selected_context": sum(r["baseline_first8"]["missing_from_selected_context"] for r in rows),
                        "helper_missing_from_selected_context": sum(r["ranked_helper"]["missing_from_selected_context"] for r in rows)}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--split", choices=("all", "development", "holdout"), default="all")
    args = parser.parse_args()
    inventory = json.loads(INVENTORY.read_text())
    if args.split != "all":
        splits = json.loads((INVENTORY.parent / "splits.json").read_text())
        selected = set(splits[args.split])
        inventory["cases"] = [case for case in inventory["cases"] if case["id"] in selected]
        if {case["id"] for case in inventory["cases"]} != selected:
            parser.error("split manifest refers to unknown case IDs")
    result = run(inventory)
    result["split"] = args.split
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
