"""Deterministic tests for the evaluation-only verified quote strategy."""
import json
import sys
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
sys.path.insert(0, str(EVALUATION))
import evidence_plan


def payload():
    return {
        "question": "What did the study report?",
        "evidence": [
            {
                "citation": "PubMed:one",
                "text": "A sufficiently long exact sentence from the first submitted source record.",
                "matched_passages": ["The second matched passage is also long enough to qualify as a quote."],
            },
            {
                "citation": "PubMed:two",
                "text": "A separate record contains a different sufficiently long exact sentence here.",
                "matched_passages": [],
            },
        ],
    }


def quote(citation="PubMed:one", text=None):
    return {
        "citation": citation,
        "quote": text or "A sufficiently long exact sentence from the first submitted source record.",
        "use": "finding",
    }


@pytest.mark.parametrize("item", [
    quote(text="The second matched passage is also long enough to qualify as a quote."),
    quote(citation="PubMed:two", text="A separate record contains a different sufficiently long exact sentence here."),
])
def test_validate_plan_accepts_exact_quote_from_its_record(item):
    plan = evidence_plan.validate_plan(json.dumps({"quotes": [item]}), payload())
    assert plan.quotes[0].citation == item["citation"]
    assert plan.quotes[0].quote == item["quote"]


@pytest.mark.parametrize("item", [
    quote(citation="PubMed:unknown"),
    quote(citation="PubMed:two"),  # exact quote exists, but only in record one
    quote(text="A sufficiently long exact sentence from the first submitted source record, plus invented words."),
    quote(text="A sufficiently long exact sentence from the first record."),  # spliced/shortened
    {**quote(), "extra": "forbidden"},
    {**quote(), "use": "background"},
    {**quote(), "quote": "too short"},
])
def test_validate_plan_rejects_untrusted_or_malformed_quotes(item):
    with pytest.raises((ValueError, TypeError)):
        evidence_plan.validate_plan(json.dumps({"quotes": [item]}), payload())


def test_validate_plan_rejects_malformed_schema_and_allows_empty_plan():
    with pytest.raises((ValueError, TypeError)):
        evidence_plan.validate_plan('{"quotes": [], "unexpected": true}', payload())
    with pytest.raises((ValueError, TypeError)):
        evidence_plan.validate_plan('{"quotes": "none"}', payload())
    assert evidence_plan.validate_plan('{"quotes": []}', payload()).quotes == []


def request_messages(context=None):
    return [
        {"role": "system", "content": "Original answer and safety instructions."},
        {"role": "user", "content": json.dumps(context or payload())},
    ]


def test_strategy_makes_two_calls_and_preserves_original_evidence_context(monkeypatch):
    requests = []
    outputs = iter([
        json.dumps({"quotes": [quote()]}),
        '{"paragraphs":["The study reported this finding [PubMed:one]."],'
        '"cited_sources":["PubMed:one"],"uncertainty":[]}',
    ])

    def fake_completion(messages, schema):
        requests.append((messages, schema))
        return next(outputs)

    monkeypatch.setattr(evidence_plan.cloudflare, "completion", fake_completion)
    original = evidence_plan.cloudflare.completion
    source_messages = request_messages()
    original_context = source_messages[1]["content"]
    with evidence_plan.candidate_strategy("verified-quotes"):
        first_result = evidence_plan.cloudflare.completion(source_messages, {"type": "final-schema"})
        assert json.loads(first_result)["quotes"][0]["quote"] == quote()["quote"]
        final_messages = [*source_messages, {"role": "assistant", "content": first_result},
                          {"role": "user", "content": "Normal final revision instructions."}]
        final_result = evidence_plan.cloudflare.completion(final_messages, {"type": "final-schema"})

    assert len(requests) == 2
    assert requests[0][0][0]["content"] == evidence_plan.SELECT
    assert requests[0][0][1]["content"] == original_context
    assert requests[0][1] == evidence_plan.EvidencePlan.model_json_schema()
    assert requests[1][0][1]["content"] == original_context
    assert requests[1][0][2]["content"] == first_result
    assert requests[1][0][3]["content"] == evidence_plan.WRITE + payload()["question"]
    assert requests[1][1] == {"type": "final-schema"}
    assert "PubMed:one" in final_result
    assert evidence_plan.cloudflare.completion is original


def test_strategy_rejects_bad_plan_without_second_call(monkeypatch):
    calls = []

    def fake_completion(messages, schema):
        calls.append((messages, schema))
        return json.dumps({"quotes": [quote(citation="PubMed:unknown")]})

    monkeypatch.setattr(evidence_plan.cloudflare, "completion", fake_completion)
    original = evidence_plan.cloudflare.completion
    with evidence_plan.candidate_strategy("verified-quotes"):
        with pytest.raises(ValueError, match="No selected evidence quote"):
            evidence_plan.cloudflare.completion(request_messages(), {})
    assert len(calls) == 1
    assert evidence_plan.cloudflare.completion is original


def test_strategy_rejects_call_sequence_or_context_mismatch(monkeypatch):
    calls = []
    outputs = iter([json.dumps({"quotes": [quote()]}), "unused"])

    def fake_completion(messages, schema):
        calls.append(messages)
        return next(outputs)

    monkeypatch.setattr(evidence_plan.cloudflare, "completion", fake_completion)
    original = evidence_plan.cloudflare.completion
    with evidence_plan.candidate_strategy("verified-quotes"):
        first = request_messages()
        plan = evidence_plan.cloudflare.completion(first, {})
        changed_context = request_messages({**payload(), "question": "A different question"})
        final = [*changed_context, {"role": "assistant", "content": plan},
                 {"role": "user", "content": "revision"}]
        with pytest.raises(ValueError, match="sequence/context mismatch"):
            evidence_plan.cloudflare.completion(final, {})
    assert len(calls) == 1
    assert evidence_plan.cloudflare.completion is original


def test_strategy_restores_completion_after_exception(monkeypatch):
    def broken_completion(messages, schema):
        raise RuntimeError("mock provider failure")

    monkeypatch.setattr(evidence_plan.cloudflare, "completion", broken_completion)
    original = evidence_plan.cloudflare.completion
    with pytest.raises(RuntimeError, match="mock provider failure"):
        with evidence_plan.candidate_strategy("verified-quotes"):
            evidence_plan.cloudflare.completion(request_messages(), {})
    assert evidence_plan.cloudflare.completion is original



def test_subset_discards_modified_quote_without_repairing_it():
    selected = evidence_plan.verified_subset(json.dumps({"quotes": [
        quote(), quote(citation="PubMed:two"),
    ]}), payload())
    assert selected["quotes"] == [quote()]
    assert selected["discarded_unverifiable_quotes"] == 1
    with pytest.raises(ValueError, match="No selected evidence quote"):
        evidence_plan.verified_subset(json.dumps({"quotes": [quote(citation="PubMed:two")]}), payload())
