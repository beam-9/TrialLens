import json
from pathlib import Path

from evaluation.ci_coverage import includes_requirement, requirement


def test_detects_interval_dropped_by_revision_in_recorded_holdout():
    path = Path(__file__).parents[1] / "evaluation/answer_coverage/results/label-scope-numeric-holdout-2026-11-01.json"
    run = json.loads(path.read_text())[0]
    required = requirement(run["generation_context"])
    assert required is not None
    assert not includes_requirement({"paragraphs": [run["answer"]["direct_answer"]]}, required)
    assert includes_requirement(
        {"paragraphs": ["The 95% confidence interval was 0.2–0.8 percentage points lower [PubMed:EVAL-NUMBERS]."]},
        required,
    )


def test_skips_multiple_intervals_and_requires_attribution():
    record = {"citation": "PubMed:1", "text": "95% CI −2 to −1", "matched_passages": []}
    payload = {"question": "Give the confidence interval", "evidence": [record]}
    required = requirement(payload)
    assert required is not None
    assert not includes_requirement({"paragraphs": ["95% CI -2 to -1 [PubMed:2]"]}, required)
    record["matched_passages"] = ["95% CI 2 to 3"]
    assert requirement(payload) is None


def test_followup_preserves_requested_interval_when_keeping_numbers():
    record = {"citation": "PubMed:1", "text": "95% CI 0.2 to 0.8", "matched_passages": []}
    payload = {
        "question": "Can you explain that more simply without changing the numbers?",
        "history": [{"question": "Explain the measured result and its uncertainty."}],
        "evidence": [record],
    }
    assert requirement(payload) is not None
    assert requirement({**payload, "question": "What about mortality?"}) is None


def test_randomized_total_coverage_catches_omission_in_prior_answer():
    from evaluation.ci_coverage import includes_randomized_total, reported_randomized_total

    path = Path(__file__).parents[1] / "evaluation/answer_coverage/results/ci-coverage-v4-2026-11-03.json"
    run = json.loads(path.read_text())[0]
    record = run["generation_context"]["evidence"][0]
    total = reported_randomized_total(record)
    assert total == 240
    assert not includes_randomized_total(
        {"paragraphs": [run["answer"]["direct_answer"]]}, record["citation"], total
    )
    assert includes_randomized_total(
        {"paragraphs": [f"240 adults were randomly assigned to either group [{record['citation']}]."]},
        record["citation"],
        total,
    )


def test_randomized_total_requires_explicit_assignment_and_unique_total():
    from evaluation.ci_coverage import reported_randomized_total

    record = {"text": "240 adults were enrolled.", "matched_passages": []}
    assert reported_randomized_total(record) is None
    record["text"] = "240 adults were randomized to treatment or placebo."
    record["matched_passages"] = ["120 patients were randomly assigned to either group."]
    assert reported_randomized_total(record) is None


def test_single_arm_assignment_cannot_be_used_as_trial_total():
    from evaluation.ci_coverage import includes_randomized_total, reported_randomized_total

    record = {"text": "120 adults were randomized to treatment.", "matched_passages": []}
    assert reported_randomized_total(record) is None
    assert not includes_randomized_total(
        {"paragraphs": ["The trial randomized 240 adults per arm [PubMed:1]."]},
        "PubMed:1",
        240,
    )
