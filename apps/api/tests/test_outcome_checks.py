"""Evaluation-only ownership and coverage checks against posted fixture outcomes."""
import json
import itertools
import sys
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
sys.path.insert(0, str(EVALUATION))

from claim_review import RepairedReview
from evidence_plan import ClaimDraft
from outcome_checks import answer_requirements, coverage_issues, review_issues, tag_outcome_support
from evidence_plan import candidate_strategy
from claim_review import cloudflare
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


def strategy_payload():
    context = payload()
    first, second = context["evidence"]
    context["evidence"] = [{
        "citation": first["citation"],
        "title": "Singulair(R) In Asthma And Allergic Rhinitis",
        "text": "Intervention: montelukast sodium, 10 mg, one tablet once a day for 8 weeks as add on therapy to usual current asthma controller treatment. "
                "Study design: NON_RANDOMIZED; SINGLE_GROUP.",
        "matched_passages": [first["matched_passages"][0], second["matched_passages"][0]],
        "outcome_links": [
            {**first["outcome_links"][0], "matched_passage_index": 0},
            {**second["outcome_links"][0], "matched_passage_index": 1},
        ],
        "registry_design": first["registry_design"],
    }]
    context["question"] = "For NCT00545844, give the Asthma Control counts and denominators at baseline and week 8, and explain what comparison can tell us."
    return context


def run_outcome_strategy(monkeypatch, *, variant="valid"):
    """Call the wrapper directly with deterministic draft/review completions."""
    import evidence_plan

    context = strategy_payload()
    citation = "ClinicalTrials.gov:NCT00545844"
    first = "At week 0, 312 of 313 were uncontrolled, 0 controlled, and 1 missing; at week 8, 72 of 301 were uncontrolled, 229 controlled, and none were missing."
    second = "The study tested montelukast as add-on therapy; its nonrandomized single-group before-and-after comparison cannot establish that montelukast caused the change."
    claims = [
        {"text": first, "citation": citation, "paragraph": 0},
        {"text": second, "citation": citation, "paragraph": 0},
    ]
    if variant == "omit_72":
        claims[0]["text"] = claims[0]["text"].replace("72", "71")
    if variant == "significance":
        claims.append({"text": "The primary asthma control outcome was statistically significant.",
                       "citation": citation, "paragraph": 0})
    payload_text = json.dumps(context)
    initial_messages = [{"role": "system", "content": "outcome-claims test"},
                        {"role": "user", "content": payload_text}]
    calls = []

    def choose_ids(passage_index, required, limit=3):
        items = list(passage_index.items())
        for size in range(1, limit + 1):
            for selected in itertools.combinations(items, size):
                joined = "\n".join(value["text"] for _, value in selected)
                if all(token.lower() in joined.lower() for token in required):
                    return [key for key, _ in selected]
        return []

    def fake_completion(messages, schema):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps({"claims": claims})
        task = json.loads(messages[-1]["content"])
        index = task["passage_index"]
        primary_ids = choose_ids(index, ["312", "313", "72", "301", "229"])
        comparison_ids = choose_ids(index, ["montelukast", "NON_RANDOMIZED", "SINGLE_GROUP"])
        acq_ids = [key for key, value in index.items() if "p value=<0.001" in value.get("text", "")]
        reviews = []
        for i, claim in enumerate(claims):
            ids = primary_ids if i == 0 or variant == "significance" and i == 2 else comparison_ids
            text = claim["text"]
            if variant == "cross_outcome" and i == 0:
                ids = list(dict.fromkeys([*ids, *acq_ids[:1]]))
            if variant == "unknown_id" and i == 0:
                ids = ["S0P999"]
            if variant == "omit_comparison" and i == 1:
                text = "The study tested montelukast as add-on therapy; the outcome changed over eight weeks."
            reviews.append({"index": i, "verdict": "revised", "text": text, "quotes": ids})
        return json.dumps({"reviews": reviews})

    original = cloudflare.completion
    monkeypatch.setattr(cloudflare, "completion", fake_completion)
    with candidate_strategy("outcome-claims"):
        draft_json = cloudflare.completion(initial_messages, {})
        second_messages = [initial_messages[0], initial_messages[1],
                           {"role": "assistant", "content": draft_json},
                           {"role": "user", "content": "complete review"}]
        output = cloudflare.completion(second_messages, {})
    assert cloudflare.completion is fake_completion
    monkeypatch.setattr(cloudflare, "completion", original)
    return json.loads(output), calls


def test_outcome_strategy_renders_valid_two_claim_answer_in_exactly_two_calls(monkeypatch):
    answer, calls = run_outcome_strategy(monkeypatch)
    assert len(calls) == 2
    assert len(answer["paragraphs"]) == 1
    assert len(answer["paragraphs"][0].split(" [ClinicalTrials.gov:NCT00545844]")) == 3
    assert "312" in answer["paragraphs"][0] and "72" in answer["paragraphs"][0]
    assert "cannot establish" in answer["paragraphs"][0]


@pytest.mark.parametrize("variant", ["omit_72", "omit_comparison", "cross_outcome", "unknown_id"])
def test_outcome_strategy_rejects_coverage_ownership_and_unknown_id_failures(monkeypatch, variant):
    with pytest.raises(ValueError):
        run_outcome_strategy(monkeypatch, variant=variant)


def test_outcome_strategy_drops_primary_significance_without_analysis(monkeypatch):
    answer, calls = run_outcome_strategy(monkeypatch, variant="significance")
    assert len(calls) == 2
    assert "statistically significant" not in " ".join(answer["paragraphs"])
