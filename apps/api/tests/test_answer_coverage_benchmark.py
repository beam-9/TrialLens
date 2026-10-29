import importlib.util
import json
from pathlib import Path


BENCHMARK = Path(__file__).resolve().parents[1] / "evaluation/answer_coverage/benchmark.py"
spec = importlib.util.spec_from_file_location("answer_coverage_benchmark", BENCHMARK)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)

CONTEXT_COMPARE = Path(__file__).resolve().parents[1] / "evaluation/answer_coverage/context_compare.py"
context_spec = importlib.util.spec_from_file_location("answer_coverage_context_compare", CONTEXT_COMPARE)
context_compare = importlib.util.module_from_spec(context_spec)
context_spec.loader.exec_module(context_compare)


def test_authored_inventory_has_valid_passage_backed_cases():
    inventory = json.loads(benchmark.DEFAULT_INVENTORY.read_text())
    assert benchmark.validate(inventory) == []
    assert 12 <= len(inventory["cases"]) <= 20
    categories = {case["category"] for case in inventory["cases"]}
    assert {"numbers_population_comparator_time_ci", "planned_vs_observed", "late_context_source",
            "broad_benefits_risks", "followup_simplification", "explanation",
            "comparison_distinct_studies", "unsupported_outcome", "qualitative_no_required_numbers"} <= categories


def test_retrieval_recall_is_separate_from_semantic_scoring():
    assert benchmark.retrieval_recall(["S1", "S2"], ["S2", "S3"]) == 0.5
    assert benchmark.retrieval_recall([], []) == 1.0


def test_splits_are_disjoint_and_late_source_case_is_holdout():
    inventory = json.loads(benchmark.DEFAULT_INVENTORY.read_text())
    splits = json.loads((benchmark.DEFAULT_INVENTORY.parent / "splits.json").read_text())
    all_ids = {case["id"] for case in inventory["cases"]}
    assert set(splits["development"]).isdisjoint(splits["holdout"])
    assert set(splits["development"]) | set(splits["holdout"]) == all_ids
    late = next(case for case in inventory["cases"] if case["id"] == "later_relevant_source")
    assert late["sources"][8]["id"] == "S9"
    assert late["retrieval_relevant_source_ids"] == ["S9"]
    assert "later_relevant_source" in splits["holdout"]


def test_validator_rejects_invented_passage_and_missing_synthetic_label():
    inventory = json.loads(benchmark.DEFAULT_INVENTORY.read_text())
    inventory["cases"][0]["required_facts"][0]["passage"] = "not in the source"
    inventory["cases"][1]["sources"][0]["text"] = "Real-looking unlabeled text"
    errors = benchmark.validate(inventory)
    assert any("not an exact substring" in error for error in errors)
    assert any("synthetic control label" in error for error in errors)


def test_passage_index_and_context_membership_are_scoped_to_exact_source_ids():
    case = {"id": "collision", "sources": [{"id": "S1"}, {"id": "S10"}],
            "required_facts": [
                {"source_id": "S1", "fact": "first source fact", "passage": "alpha passage"},
                {"source_id": "S10", "fact": "tenth source fact", "passage": "tenth passage"},
                {"source_id": "S10", "fact": "not indexed fact", "passage": "absent passage"}]}
    source_map = {"PubMed:DEMO-collision-S1": "S1", "PubMed:DEMO-collision-S10": "S10"}
    records = [{"citation": "PubMed:DEMO-collision-S1", "text": "alpha passage", "matched_passages": []},
               {"citation": "PubMed:DEMO-collision-S10", "text": "tenth passage", "matched_passages": []}]

    class Chunk:
        def __init__(self, source_id, text):
            self.source_id, self.text = source_id, text

    chunks = [Chunk("collision-S1", "alpha passage"), Chunk("collision-S10", "tenth passage")]
    result = context_compare.coverage(case, records, chunks, source_map)
    assert [fact["status"] for fact in result["facts"]] == ["covered_by_context", "covered_by_context", "not_indexed"]
    assert result["not_indexed"] == 1


def test_helper_context_budget_can_omit_indexed_long_tail_passage():
    import importlib

    conversation = importlib.import_module("triallens.conversation")
    models = importlib.import_module("triallens.models")
    source = models.EvidenceSource(id="long-S1", workspace_id="answer-coverage-fixture",
                                  source_type=models.SourceType.pubmed, external_id="DEMO-long-S1",
                                  title="Synthetic long fixture", abstract=("Synthetic engineering control: " + "x" * 11000 + " LATE_FACT."))
    records = conversation.build_evidence_records([source], [])
    assert len(records) == 1
    assert records[0]["content_truncated"] is True
    assert "LATE_FACT" not in records[0]["text"]
    case = {"id": "long", "sources": [{"id": "S1"}],
            "required_facts": [{"source_id": "S1", "fact": "late fact", "passage": "LATE_FACT"}]}
    class Chunk:
        source_id = "long-S1"
        text = source.abstract
    coverage = context_compare.coverage(case, records, [Chunk()], {"PubMed:DEMO-long-S1": "S1"})
    assert coverage["facts"][0]["indexed"] is True
    assert coverage["facts"][0]["status"] == "missing_from_selected_context"
