"""Evaluation-only ownership and coverage checks against posted fixture outcomes."""
import json
import sys
from pathlib import Path

EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
sys.path.insert(0, str(EVALUATION))

from claim_review import RepairedReview
from evidence_plan import ClaimDraft
from outcome_checks import answer_requirements, coverage_issues, review_issues, tag_outcome_support
from triallens.trial_design import parse_registry_design
from triallens.trial_results import parse_outcome_measures

FIXTURE = EVALUATION / "answer_coverage/fixtures/ctgov-NCT00545844-2026-10-31.json"


def payload():
    study = json.loads(FIXTURE.read_text())
    sections, _ = parse_outcome_measures(study["resultsSection"])
    design = parse_registry_design(study["protocolSection"]["designModule"])
    evidence = []
    for section, index, has_analysis in [
        ("Results outcome 001", 0, False),
        ("Results outcome 003", 1, True),
    ]:
        evidence.append({
            "citation": "ClinicalTrials.gov:NCT00545844",
            "matched_passages": [sections[section]],
            "outcome_links": [{"id": section, "matched_passage_index": 0,
                               "title": next(line[9:] for line in sections[section].splitlines()
                                             if line.startswith("Outcome: ")),
                               "has_reported_analysis": has_analysis}],
            "registry_design": design,
        })
    return {"question": "For NCT00545844, give the Asthma Control counts and denominators at baseline and week 8.",
            "evidence": evidence}


def test_tagging_and_review_rejects_cross_outcomes_and_unreported_significance():
    context = payload()
    primary = context["evidence"][0]["matched_passages"][0]
    acq = context["evidence"][1]["matched_passages"][0]
    index = tag_outcome_support({
        "primary": {"citation": "ClinicalTrials.gov:NCT00545844", "text": primary},
        "acq": {"citation": "ClinicalTrials.gov:NCT00545844", "text": acq},
    }, context)
    assert index["primary"]["outcome_ids"] == ["Results outcome 001"]
    assert index["acq"]["outcome_ids"] == ["Results outcome 003"]

    draft = ClaimDraft.model_validate({"claims": [
        {"text": "The primary counts and ACQ analysis both show statistically significant improvement.",
         "citation": "ClinicalTrials.gov:NCT00545844", "paragraph": 0}
    ]})
    mixed = RepairedReview.model_validate({"reviews": [{"index": 0, "verdict": "supported",
        "text": draft.claims[0].text, "quotes": ["primary", "acq"]}]})
    assert 0 in review_issues(mixed, draft, index)

    primary_sig = RepairedReview.model_validate({"reviews": [{"index": 0, "verdict": "supported",
        "text": "Asthma control improved and was statistically significant.", "quotes": ["primary"]}]})
    assert 0 in review_issues(primary_sig, draft, index)


def test_review_permits_analyzed_acq_claim_and_negated_primary_significance():
    context = payload()
    primary, acq = [record["matched_passages"][0] for record in context["evidence"]]
    index = tag_outcome_support({
        "primary": {"citation": "ClinicalTrials.gov:NCT00545844", "text": primary},
        "acq": {"citation": "ClinicalTrials.gov:NCT00545844", "text": acq},
    }, context)
    draft = ClaimDraft.model_validate({"claims": [
        {"text": "The ACQ outcome reported a statistically significant result at week 8.",
         "citation": "ClinicalTrials.gov:NCT00545844", "paragraph": 0}
    ]})
    analyzed = RepairedReview.model_validate({"reviews": [{"index": 0, "verdict": "supported",
        "text": draft.claims[0].text, "quotes": ["acq"]}]})
    assert review_issues(analyzed, draft, index) == {}

    negated = RepairedReview.model_validate({"reviews": [{"index": 0, "verdict": "supported",
        "text": "The primary outcome was not statistically significant.", "quotes": ["primary"]}]})
    assert review_issues(negated, draft, index) == {}


def test_answer_requirements_select_primary_counts_including_followup_history():
    context = payload()
    context["question"] = "Simplify this and give counts and denominators."
    context["history"] = [{"question": "For NCT00545844, what were the Asthma Control counts and denominators at baseline and week 8?"}]
    requirement = answer_requirements(context)
    assert requirement["outcome_id"] == "Results outcome 001"
    assert requirement["required_reported_values"] == ["0", "1", "72", "229", "301", "312", "313"]
    assert "2.03" not in requirement["required_reported_values"]
    assert "0.92" not in requirement["required_reported_values"]
    assert requirement["require_comparison_limit"] is True


def test_answer_requirements_skip_ambiguous_or_unavailable_outcome_targets():
    context = payload()
    context["question"] = "What were the counts and denominators?"
    assert answer_requirements(context) == {}
    context["question"] = "For NCT99999999, what were the Asthma Control counts and denominators?"
    assert answer_requirements(context) == {}


def test_coverage_requires_reported_counts_and_comparison_boundary_without_inventing_fields():
    requirement = answer_requirements(payload())
    base = {"cited_sources": ["ClinicalTrials.gov:NCT00545844"], "paragraphs": [
        "At baseline, 312 of 313 were uncontrolled and 1 was missing; at week 8, 72 of 301 were uncontrolled, 229 were controlled, and none were missing. The nonrandomized single-group before and after comparison cannot isolate the effect of montelukast."]}
    assert coverage_issues(base, requirement) == []
    missing_week8 = {**base, "paragraphs": [base["paragraphs"][0].replace("72 of 301", "71 of 301")]}
    assert any("72" in issue for issue in coverage_issues(missing_week8, requirement))
    missing_limit = {**base, "paragraphs": ["At baseline, 312 of 313 were uncontrolled and 1 was missing; at week 8, 72 of 301 were uncontrolled, 229 were controlled, and none were missing."]}
    assert any("limitation" in issue for issue in coverage_issues(missing_limit, requirement))
    assert requirement["required_reported_values"] == ["0", "1", "72", "229", "301", "312", "313"]
