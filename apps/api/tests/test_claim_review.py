"""Deterministic coverage for the evaluation-only reviewed-claims strategy."""
import json
import sys
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
sys.path.insert(0, str(EVALUATION))
import evidence_plan


SOURCE_TEXT = "Adults receiving the study treatment had a lower score than the control group at week 12."


def payload():
    return {
        "question": "What happened in the study?",
        "history": [{"question": "Earlier question", "answer": "Earlier answer is not evidence."}],
        "evidence": [{
            "citation": "PubMed:study",
            "text": SOURCE_TEXT,
            "matched_passages": ["The study included 120 adults and followed them for 12 weeks."],
            "status": "Completed",
            "phase": "Phase 3",
        }],
    }


def claim(text="The treatment group had a lower score than control at week 12.",
          citation="PubMed:study", paragraph=0):
    return {"text": text, "citation": citation, "paragraph": paragraph}


def draft(*claims):
    return evidence_plan.ClaimDraft.model_validate({"claims": list(claims)})


def review(*items):
    return json.dumps({"reviews": list(items)})


def check(index=0, verdict="supported", quote=SOURCE_TEXT):
    return {"index": index, "verdict": verdict, "quote": quote}


def test_render_approves_only_original_draft_words_and_exact_citation():
    original = "The treatment group had a lower score than control at week 12."
    result = evidence_plan.render_reviewed(draft(claim(text=original)), review(check()), payload())
    assert result == {
        "paragraphs": [original + " [PubMed:study]"],
        "cited_sources": ["PubMed:study"],
        "uncertainty": [],
    }
    assert "review" not in result["paragraphs"][0].lower()


@pytest.mark.parametrize("review_json", [
    '{"reviews": []}',
    review(),
    review(check(index=1)),
    review(check(), check()),
    '{"reviews":[{"index":0,"verdict":"supported","quote":"' + SOURCE_TEXT + '","extra":1}]}',
])
def test_render_rejects_empty_missing_duplicate_out_of_range_or_malformed_reviews(review_json):
    with pytest.raises((ValueError, TypeError)):
        evidence_plan.render_reviewed(draft(claim()), review_json, payload())


@pytest.mark.parametrize("bad_review", [
    check(verdict="unsupported", quote=""),
    check(verdict="supported", quote=""),
    check(verdict="supported", quote="A quote that is not present in the cited source."),
    check(verdict="supported", quote="Adults receiving"),
])
def test_render_rejects_when_no_claim_has_valid_supporting_quote(bad_review):
    with pytest.raises(ValueError, match="No draft claims passed"):
        evidence_plan.render_reviewed(draft(claim()), review(bad_review), payload())


def test_render_rejects_quote_from_different_cited_record():
    other = {"evidence": [
        {"citation": "PubMed:study", "text": "A different source has its own sufficiently long passage here.", "matched_passages": []},
        {"citation": "PubMed:other", "text": SOURCE_TEXT, "matched_passages": []},
    ]}
    with pytest.raises(ValueError, match="No draft claims passed"):
        evidence_plan.render_reviewed(draft(claim()), review(check()), other)


def test_short_quote_is_not_enough_but_exact_status_or_phase_is_enough():
    short_source = {"evidence": [{"citation": "PubMed:study", "text": "Study text is not relevant to status.", "matched_passages": []} ]}
    status_claim = claim(text="The registry reports the study status as completed.")
    with pytest.raises(ValueError, match="No draft claims passed"):
        evidence_plan.render_reviewed(draft(status_claim), review(check(quote="Completed")), short_source)

    metadata_claim = claim(text="The registry lists the study status as Completed.")
    status_source = {"evidence": [{"citation": "PubMed:study", "text": "", "matched_passages": [], "status": "Completed"}]}
    result = evidence_plan.render_reviewed(draft(metadata_claim), review(check(quote="Completed")), status_source)
    assert result["paragraphs"] == [metadata_claim["text"] + " [PubMed:study]"]


def test_unknown_citation_cannot_be_approved():
    with pytest.raises(ValueError, match="No draft claims passed"):
        evidence_plan.render_reviewed(draft(claim(citation="PubMed:missing")), review(check()), payload())

    calls = []

    def fake_completion(messages, schema):
        calls.append(messages)
        return json.dumps({"claims": [claim(citation="PubMed:missing")]})

    original = evidence_plan.cloudflare.completion
    evidence_plan.cloudflare.completion = fake_completion
    try:
        messages = [{"role": "system", "content": "original"}, {"role": "user", "content": json.dumps(payload())}]
        with evidence_plan.candidate_strategy("reviewed-claims"):
            with pytest.raises(ValueError, match="Invalid draft claim attribution"):
                evidence_plan.cloudflare.completion(messages, {})
        assert len(calls) == 1
    finally:
        evidence_plan.cloudflare.completion = original


def test_strategy_uses_exactly_two_calls_with_original_context_and_restores_global(monkeypatch):
    calls = []
    draft_json = json.dumps({"claims": [claim()]})
    review_json = review(check())

    def fake_completion(messages, schema):
        calls.append((messages, schema))
        if messages[0]["content"] == evidence_plan.DRAFT:
            return draft_json
        assert messages[0]["content"] == evidence_plan.CHECK
        return review_json

    monkeypatch.setattr(evidence_plan.cloudflare, "completion", fake_completion)
    original = evidence_plan.cloudflare.completion
    context_text = json.dumps(payload())
    source_messages = [
        {"role": "system", "content": "Original evidence and safety instructions"},
        {"role": "user", "content": context_text},
    ]
    final_messages = [*source_messages,
                      {"role": "assistant", "content": "ordinary draft placeholder"},
                      {"role": "user", "content": "ordinary revision placeholder"}]

    with evidence_plan.candidate_strategy("reviewed-claims"):
        encoded_draft = evidence_plan.cloudflare.completion(source_messages, {"type": "answer-schema"})
        final = evidence_plan.cloudflare.completion(
            [*source_messages[:1], source_messages[1],
             {"role": "assistant", "content": encoded_draft}, final_messages[3]],
            {"type": "answer-schema"},
        )

    assert len(calls) == 2
    assert calls[0][0][0]["content"] == evidence_plan.DRAFT
    assert calls[0][0][1]["content"] == context_text
    expected_schema = evidence_plan.ClaimDraft.model_json_schema()
    expected_schema["$defs"]["DraftClaim"]["properties"]["citation"]["enum"] = ["PubMed:study"]
    assert calls[0][1] == expected_schema
    assert calls[1][0][0]["content"] == evidence_plan.CHECK
    assert calls[1][0][1]["content"] == context_text
    assert calls[1][0][2]["content"] == encoded_draft
    assert calls[1][1] == evidence_plan.ClaimReview.model_json_schema()
    assert json.loads(final)["paragraphs"] == [claim()["text"] + " [PubMed:study]"]
    assert evidence_plan.cloudflare.completion is original


def test_strategy_restores_global_after_provider_exception(monkeypatch):
    def fail(messages, schema):
        raise RuntimeError("mock inference failure")

    monkeypatch.setattr(evidence_plan.cloudflare, "completion", fail)
    original = evidence_plan.cloudflare.completion
    source_messages = [{"role": "system", "content": "original"}, {"role": "user", "content": json.dumps(payload())}]
    with pytest.raises(RuntimeError, match="mock inference failure"):
        with evidence_plan.candidate_strategy("reviewed-claims"):
            evidence_plan.cloudflare.completion(source_messages, {})
    assert evidence_plan.cloudflare.completion is original



@pytest.mark.parametrize("sentence,title,source_quote,expected", [
    ("Metformin may slow the process in people.", "Review", "Preclinical studies found the treatment might slow the process.", False),
    ("Preclinical studies suggest metformin may slow the process.", "Review", "Preclinical studies found the treatment might slow the process.", True),
    ("Patients can maintain metabolic control with treatment.", "Two case reports", "One patient maintained metabolic control for four years.", False),
    ("One patient maintained metabolic control in a case report.", "Two case reports", "One patient maintained metabolic control for four years.", True),
    ("The medication has a rare serious risk.", "Label", "The label lists this serious adverse reaction in its warnings.", False),
    ("The medication has a rare serious risk.", "Label", "The label describes a rare serious adverse reaction.", True),
])
def test_review_cannot_drop_explicit_scope_or_invent_rarity(sentence, title, source_quote, expected):
    item = evidence_plan.DraftClaim(text=sentence, citation="PubMed:study", paragraph=0)
    assert evidence_plan.scope_preserved(item, {"title": title}, source_quote) is expected


def test_review_cannot_approve_a_range_missing_from_its_quoted_evidence():
    item = evidence_plan.DraftClaim(text="Rates ranged from 0.6% to 3.9% across different trials.", citation="PubMed:study", paragraph=0)
    assert not evidence_plan.scope_preserved(item, {"title": "Trial data"}, "Rates in this trial were 0.6% for control and 1.6% for treatment.")
    assert evidence_plan.scope_preserved(item, {"title": "Trial data"}, "The quoted trials reported rates of 0.6% and 3.9% respectively.")
