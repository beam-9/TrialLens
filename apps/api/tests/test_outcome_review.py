"""Whole-outcome packet review strategy: ownership, numeric scope and call sequence."""
import json
import sys
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
sys.path.insert(0, str(EVALUATION))

from claim_review import ClaimDraft
from outcome_review import (candidate_outcome_review, render_outcome_review,
                            support_index)
from test_outcome_checks import strategy_payload
from triallens import cloudflare


def test_support_index_contains_atomic_packets_and_catalog_has_no_source_bodies():
    payload = strategy_payload()
    index = support_index(payload)
    assert index["S0O0"]["text"] == payload["evidence"][0]["matched_passages"][0]
    assert index["S0O1"]["text"] == payload["evidence"][0]["matched_passages"][1]
    assert "312" in index["S0O0"]["text"]
    assert "p value=<0.001" in index["S0O1"]["text"]
    from outcome_review import _catalog
    catalog = _catalog(index)
    assert all("text" not in item and "312" not in json.dumps(item) for item in catalog)


def test_catalog_uses_linked_passage_index_not_link_ordinal():
    payload = strategy_payload()
    record = payload["evidence"][0]
    record["outcome_links"] = [{**record["outcome_links"][1], "matched_passage_index": 0}]
    index = support_index(payload)
    from outcome_review import _catalog
    assert index["S0O0"]["text"] == record["matched_passages"][0]
    assert _catalog(index)[1]["matched_passage_index"] == 0


def test_first_call_allows_only_citations_with_valid_linked_outcomes(monkeypatch):
    calls = []
    monkeypatch.setattr(cloudflare, "completion", lambda *args: calls.append(args))
    payload = {"evidence": [{"citation": "PubMed:no-outcome", "text": "context",
                             "matched_passages": [], "outcome_links": []}]}
    with candidate_outcome_review():
        with pytest.raises(ValueError, match="linked outcome"):
            cloudflare.completion([{"role": "system", "content": "sys"},
                {"role": "user", "content": json.dumps(payload)}], {})
    assert calls == []


def test_selected_packet_owns_claim_and_rejects_numbers_from_other_outcome():
    payload = strategy_payload()
    draft = ClaimDraft.model_validate({"claims": [{"text": "Asthma control counts were reported.",
        "citation": "ClinicalTrials.gov:NCT00545844", "paragraph": 0}]})
    index = support_index(payload)
    wrong_endpoint = json.dumps({"reviews": [{"index": 0, "verdict": "revised",
        "text": "The asthma control outcome was statistically significant at p<0.001.",
        "support_id": "S0O0"}]})
    with pytest.raises(ValueError, match="No outcome claims"):
        render_outcome_review(draft, wrong_endpoint, payload, index)

    wrong_citation = {"S0O0": {**index["S0O0"], "citation": "ClinicalTrials.gov:NCT00000000"}}
    text = "At baseline, 312 of 313 were uncontrolled; at week 8, 72 of 301 were uncontrolled."
    response = json.dumps({"reviews": [{"index": 0, "verdict": "revised", "text": text,
                                         "support_id": "S0O0"}]})
    with pytest.raises(ValueError, match="No outcome claims"):
        render_outcome_review(draft, response, payload, wrong_citation)


def test_missing_required_count_is_rejected_after_claim_review():
    payload = strategy_payload()
    draft = ClaimDraft.model_validate({"claims": [{"text": "Counts were reported.",
        "citation": "ClinicalTrials.gov:NCT00545844", "paragraph": 0}]})
    response = json.dumps({"reviews": [{"index": 0, "verdict": "revised",
        "text": "At baseline, 312 of 313 were uncontrolled; at week 8, 71 of 301 were uncontrolled.",
        "support_id": "S0O0"}]})
    with pytest.raises(ValueError, match="No outcome claims"):
        render_outcome_review(draft, response, payload, support_index(payload))


def test_render_rejects_foreign_nct_identifier_even_when_numbers_match():
    payload = strategy_payload()
    draft = ClaimDraft.model_validate({"claims": [{"text": "Counts were reported.",
        "citation": "ClinicalTrials.gov:NCT00545844", "paragraph": 0}]})
    response = json.dumps({"reviews": [{"index": 0, "verdict": "revised",
        "text": "For NCT99999999, 312 of 313 were uncontrolled at baseline.",
        "support_id": "S0O0"}]})
    with pytest.raises(ValueError, match="No outcome claims"):
        render_outcome_review(draft, response, payload, support_index(payload))


@pytest.mark.parametrize("label,accepted", [("", False), ("This is synthetic demo data.", True)])
def test_demo_source_requires_explicit_label(label, accepted):
    payload = strategy_payload()
    payload["question"] = "Summarize the linked outcome."
    payload["evidence"][0]["demo"] = True
    draft = ClaimDraft.model_validate({"claims": [{"text": "Counts were reported.",
        "citation": "ClinicalTrials.gov:NCT00545844", "paragraph": 0}]})
    result_text = "At baseline, 312 of 313 were uncontrolled, 0 controlled, and 1 missing; at week 8, 72 of 301 were uncontrolled, 229 controlled, and none missing. " + label
    response = json.dumps({"reviews": [{"index": 0, "verdict": "revised", "text": result_text,
        "support_id": "S0O0"}]})
    if accepted:
        answer = render_outcome_review(draft, response, payload, support_index(payload))
        assert "synthetic" in answer["paragraphs"][0].lower()
    else:
        with pytest.raises(ValueError, match="demo evidence"):
            render_outcome_review(draft, response, payload, support_index(payload))


def test_candidate_runs_exactly_two_calls_preserves_original_context_and_restores(monkeypatch):
    payload = strategy_payload()
    citation = "ClinicalTrials.gov:NCT00545844"
    draft = {"claims": [
        {"text": "The question requests counts.", "citation": citation, "paragraph": 0},
        {"text": "The question asks about study design.", "citation": citation, "paragraph": 0},
    ]}
    final = "At baseline, 312 of 313 were uncontrolled, 0 controlled, and 1 missing; at week 8, 72 of 301 were uncontrolled, 229 controlled, and none missing."
    calls = []

    def fake(messages, schema):
        calls.append((messages, schema))
        if len(calls) == 1:
            return json.dumps(draft)
        task = json.loads(messages[-1]["content"])
        assert "312" not in json.dumps(task["passage_index"])
        assert all(set(item) == {"id", "citation", "title", "role", "matched_passage_index"}
                   for item in task["passage_index"])
        assert messages[1]["content"] == json.dumps(payload)
        return json.dumps({"reviews": [
            {"index": 0, "verdict": "revised", "text": final, "support_id": "S0O0"},
            {"index": 1, "verdict": "revised", "text": "The study used a nonrandomized single-group before-and-after design, so it cannot isolate the effect of montelukast.", "support_id": "S0O0"},
        ]})

    monkeypatch.setattr(cloudflare, "completion", fake)
    original = cloudflare.completion
    user_payload = json.dumps(payload)
    initial = [{"role": "system", "content": "normal"}, {"role": "user", "content": user_payload}]
    with candidate_outcome_review():
        draft_json = cloudflare.completion(initial, {})
        result = cloudflare.completion([initial[0], initial[1],
            {"role": "assistant", "content": draft_json}, {"role": "user", "content": "finish"}], {})
    assert len(calls) == 2
    assert cloudflare.completion is original
    assert citation in json.loads(result)["paragraphs"][0]


def test_candidate_restores_completion_when_review_raises(monkeypatch):
    def broken(*_args):
        raise RuntimeError("provider failure")
    monkeypatch.setattr(cloudflare, "completion", broken)
    original = cloudflare.completion
    payload = strategy_payload()
    with pytest.raises(RuntimeError, match="provider failure"):
        with candidate_outcome_review():
            cloudflare.completion([{"role": "system", "content": "sys"},
                {"role": "user", "content": json.dumps(payload)}], {})
    assert cloudflare.completion is original
