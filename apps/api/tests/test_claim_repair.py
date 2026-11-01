"""Adversarial checks for evaluation-only repaired-claims rendering."""
import json
import sys
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
sys.path.insert(0, str(EVALUATION))
import evidence_plan
import claim_review


def payload():
    return {
        "evidence": [
            {
                "citation": "PubMed:one",
                "text": "The study enrolled 120 adults and reported a mean reduction of 2.4 cm after treatment.",
                "matched_passages": ["At week 12, the treated group had a mean reduction of 2.4 cm."],
            },
            {
                "citation": "PubMed:two",
                "text": "The separate study reported a mean reduction of 3.1 cm per year in its cohort.",
                "matched_passages": [],
            },
        ]
    }


def claim(text="The treatment reduced the measured value by 2.4 cm.", citation="PubMed:one", paragraph=0):
    return {"text": text, "citation": citation, "paragraph": paragraph}


def draft(*claims):
    return evidence_plan.ClaimDraft.model_validate({"claims": list(claims)})


def item(index=0, verdict="supported", text="The treatment reduced the measured value by 2.4 cm.",
         quotes=None):
    return {"index": index, "verdict": verdict, "text": text,
            "quotes": quotes if quotes is not None else [payload()["evidence"][0]["text"]]}


def review(*items):
    return json.dumps({"reviews": list(items)})


def test_revised_claim_renders_only_repaired_text_with_original_citation():
    revised = "The study reported a mean reduction of 2.4 cm after treatment in 120 adults."
    result = claim_review.render_repaired(
        draft(claim("Treatment reduced values by 2.4 cm in all patients.")),
        review(item(verdict="revised", text=revised)), payload())
    assert result["paragraphs"] == [revised + " [PubMed:one]"]
    assert result["cited_sources"] == ["PubMed:one"]


@pytest.mark.parametrize("quote,citation", [
    (payload()["evidence"][1]["text"], "PubMed:one"),  # quote belongs to another record
    (payload()["evidence"][0]["text"] + " This extra claim is invented.", "PubMed:one"),
    ("The study enrolled 120 adults and reported a mean reduction of 2.4 cm.", "PubMed:one"),  # spliced
])
def test_quote_must_be_exact_and_from_claims_own_record(quote, citation):
    with pytest.raises(ValueError, match="No.*claim|passed|verified"):
        claim_review.render_repaired(draft(claim(citation=citation)), review(item(quotes=[quote])), payload())


def test_numeric_mismatch_rejects_repair_even_when_quote_is_exact():
    revised = "The treatment reduced the measured value by 3.1 cm."
    with pytest.raises(ValueError, match="No.*claim|passed|verified"):
        claim_review.render_repaired(draft(claim()), review(item(text=revised)), payload())


def test_cm_per_year_cannot_verify_cm_but_exact_cm_can():
    original = claim("The treatment reduced the measured value by 3.1 cm.", citation="PubMed:two")
    with pytest.raises(ValueError, match="No.*claim|passed|verified"):
        claim_review.render_repaired(
            draft(original), review(item(text=original["text"], quotes=[payload()["evidence"][1]["text"]])), payload())

    cm_claim = claim("The treatment reduced the measured value by 2.4 cm.")
    result = claim_review.render_repaired(
        draft(cm_claim), review(item(text=cm_claim["text"], quotes=[payload()["evidence"][0]["text"]])), payload())
    assert result["paragraphs"] == [cm_claim["text"] + " [PubMed:one]"]


@pytest.mark.parametrize("items", [
    [],
    [item(index=1)],
    [item(), item()],
])
def test_review_must_cover_each_index_once(items):
    with pytest.raises((ValueError, TypeError)):
        claim_review.render_repaired(draft(claim()), review(*items), payload())


def test_invalid_claim_is_discarded_while_valid_claim_survives():
    invalid = claim("The treatment reduced the value by 999 cm.")
    valid = claim("The study enrolled 120 adults.", paragraph=1)
    result = claim_review.render_repaired(
        draft(invalid, valid),
        review(item(index=0, text=invalid["text"]),
               item(index=1, text=valid["text"], quotes=[payload()["evidence"][0]["text"]])), payload())
    assert result["paragraphs"] == [valid["text"] + " [PubMed:one]"]
    assert result["cited_sources"] == ["PubMed:one"]


def test_revised_prose_must_be_nonempty_and_backed_by_supplied_quote():
    source_quote = "At week 12, the treated group had a mean reduction of 2.4 cm."
    corrected = "At week 12, the treated group had a mean reduction of 2.4 cm."
    result = claim_review.render_repaired(
        draft(claim("A much broader unsupported original claim.")),
        review(item(verdict="revised", text=corrected, quotes=[source_quote])), payload())
    assert result["paragraphs"] == [corrected + " [PubMed:one]"]

    with pytest.raises(ValueError, match="No.*claim|passed|verified"):
        claim_review.render_repaired(
            draft(claim()), review(item(text="", quotes=[source_quote])), payload())


def request_messages(context=None):
    return [
        {"role": "system", "content": "Original answer and safety instructions."},
        {"role": "user", "content": json.dumps(context or payload())},
    ]


def test_strategy_makes_exactly_two_calls_and_preserves_original_context(monkeypatch):
    calls = []
    encoded_draft = json.dumps({"claims": [claim()]})
    parsed_draft = evidence_plan.ClaimDraft.model_validate_json(encoded_draft)
    passage_ids = [key for key, value in claim_review.passage_index(parsed_draft, payload()).items()
                   if value["citation"] == "PubMed:one"]
    review_json = review(item(quotes=[passage_ids[0]]))

    def fake_completion(messages, schema):
        calls.append((messages, schema))
        if messages[0]["content"] == claim_review.DRAFT:
            return encoded_draft
        assert messages[0]["content"] == claim_review.ANCHORED_REVIEW
        return review_json

    monkeypatch.setattr(claim_review.cloudflare, "completion", fake_completion)
    original = claim_review.cloudflare.completion
    source_messages = request_messages()
    context = source_messages[1]["content"]
    with claim_review.repaired_claims_experiment():
        first = claim_review.cloudflare.completion(source_messages, {"type": "answer-schema"})
        final = claim_review.cloudflare.completion(
            [*source_messages, {"role": "assistant", "content": first},
             {"role": "user", "content": "normal final revision instructions"}],
            {"type": "answer-schema"})

    assert len(calls) == 2
    assert calls[0][0][1]["content"] == context
    assert calls[0][1]["$defs"]["DraftClaim"]["properties"]["citation"]["enum"] == ["PubMed:one", "PubMed:two"]
    assert calls[1][0][1]["content"] == context
    assert json.loads(calls[1][0][2]["content"]) == json.loads(encoded_draft)
    expected_review_schema = claim_review.RepairedReview.model_json_schema()
    expected_review_schema["$defs"]["RepairedClaim"]["properties"]["quotes"]["items"]["enum"] = sorted(
        claim_review.passage_index(parsed_draft, payload()))
    expected_review_schema["$defs"]["RepairedClaim"]["properties"]["index"]["enum"] = [0]
    expected_review_schema["properties"]["reviews"]["minItems"] = 1
    expected_review_schema["properties"]["reviews"]["maxItems"] = 1
    assert json.loads(calls[1][0][-1]["content"])["indexed_claims"] == [{"index": 0, **claim()}]
    assert calls[1][1] == expected_review_schema
    assert json.loads(final)["paragraphs"] == [claim()["text"] + " [PubMed:one]"]
    assert claim_review.cloudflare.completion is original


def test_strategy_rejects_context_mismatch_without_second_call(monkeypatch):
    calls = []

    def fake_completion(messages, schema):
        calls.append(messages)
        return json.dumps({"claims": [claim()]})

    monkeypatch.setattr(claim_review.cloudflare, "completion", fake_completion)
    original = claim_review.cloudflare.completion
    with claim_review.repaired_claims_experiment():
        encoded = claim_review.cloudflare.completion(request_messages(), {})
        changed = request_messages({"evidence": payload()["evidence"], "question": "A different question"})
        with pytest.raises(ValueError, match="sequence/context mismatch"):
            claim_review.cloudflare.completion(
                [*changed, {"role": "assistant", "content": encoded}, {"role": "user", "content": "revision"}], {})
    assert len(calls) == 1
    assert claim_review.cloudflare.completion is original


def test_passage_index_uses_exact_bounded_source_windows():
    long_text = "Adults in the treatment group completed the study at week 12. " * 500
    source_payload = {"question": "What happened at week 12?", "evidence": [{
        "citation": "PubMed:long", "text": long_text, "matched_passages": []}]}
    source_draft = draft(claim("The treatment group completed the study at week 12.", citation="PubMed:long"))
    indexed = claim_review.passage_index(source_draft, source_payload)
    passages = [entry["text"] for entry in indexed.values()]
    assert indexed
    assert sum(map(len, passages)) <= claim_review.PASSAGE_BUDGET
    assert all(30 <= len(text) <= 900 and text in long_text for text in passages)


def test_expand_review_discards_foreign_and_unknown_passage_ids():
    source_draft = draft(claim())
    index = {
        "S0P0": {"citation": "PubMed:one", "text": payload()["evidence"][0]["text"]},
        "S1P0": {"citation": "PubMed:two", "text": payload()["evidence"][1]["text"]},
    }
    foreign = claim_review.expand_review(review(item(quotes=["S1P0"])), source_draft, index)
    unknown = claim_review.expand_review(review(item(quotes=["S0P999"])), source_draft, index)
    assert json.loads(foreign)["reviews"][0]["quotes"] == []
    assert json.loads(unknown)["reviews"][0]["quotes"] == []


def test_passage_index_returns_empty_for_too_short_source():
    short_payload = {"question": "status?", "evidence": [{
        "citation": "PubMed:short", "text": "Too short.", "matched_passages": []}]}
    short_draft = draft(claim("The source is too short to quote.", citation="PubMed:short"))
    assert claim_review.passage_index(short_draft, short_payload) == {}


def test_strategy_refuses_repeated_draft_call_while_review_is_pending(monkeypatch):
    calls = []

    def fake_completion(messages, schema):
        calls.append(messages)
        return json.dumps({"claims": [claim()]})

    monkeypatch.setattr(claim_review.cloudflare, "completion", fake_completion)
    original = claim_review.cloudflare.completion
    with claim_review.repaired_claims_experiment():
        with pytest.raises(ValueError, match="already has a pending draft"):
            claim_review.cloudflare.completion(request_messages(), {})
            claim_review.cloudflare.completion(request_messages(), {})
    assert len(calls) == 1
    assert claim_review.cloudflare.completion is original


def test_strategy_rejects_invalid_draft_citation_without_review_call(monkeypatch):
    calls = []

    def fake_completion(messages, schema):
        calls.append(messages)
        return json.dumps({"claims": [claim(citation="PubMed:missing")]})

    monkeypatch.setattr(claim_review.cloudflare, "completion", fake_completion)
    original = claim_review.cloudflare.completion
    with claim_review.repaired_claims_experiment():
        with pytest.raises(ValueError, match="Invalid draft claim attribution"):
            claim_review.cloudflare.completion(request_messages(), {})
    assert len(calls) == 1
    assert claim_review.cloudflare.completion is original


@pytest.mark.parametrize("bad_review", [
    '{"reviews":[{"index":0,"verdict":"revised","text":"The treatment reduced the measured value by 2.4 cm.","quotes":["S0P0"],"extra":"injected"}]}',
    '{"reviews":[{"index":0,"verdict":"revised","text":"The treatment reduced the measured value by 2.4 cm. [PubMed:two]","quotes":["S0P0"]}]}',
])
def test_strategy_rejects_malformed_review_or_citation_injection_without_retry(monkeypatch, bad_review):
    calls = []

    def fake_completion(messages, schema):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps({"claims": [claim()]})
        return bad_review

    monkeypatch.setattr(claim_review.cloudflare, "completion", fake_completion)
    original = claim_review.cloudflare.completion
    with claim_review.repaired_claims_experiment():
        with pytest.raises((ValueError, TypeError)):
            encoded = claim_review.cloudflare.completion(request_messages(), {})
            claim_review.cloudflare.completion(
                [*request_messages(), {"role": "assistant", "content": encoded}, {"role": "user", "content": "review"}], {})
    assert len(calls) == 2
    assert claim_review.cloudflare.completion is original


def test_strategy_does_not_retry_when_every_claim_fails_source_checks(monkeypatch):
    calls = []

    def fake_completion(messages, schema):
        calls.append(messages)
        return json.dumps({"claims": [claim()]}) if len(calls) == 1 else review(
            item(text="The treatment reduced the measured value by 999 cm.", quotes=["S0P0"]))

    monkeypatch.setattr(claim_review.cloudflare, "completion", fake_completion)
    original = claim_review.cloudflare.completion
    with claim_review.repaired_claims_experiment():
        encoded = claim_review.cloudflare.completion(request_messages(), {})
        with pytest.raises(ValueError, match="No repaired claims passed"):
            claim_review.cloudflare.completion(
                [*request_messages(), {"role": "assistant", "content": encoded}, {"role": "user", "content": "review"}], {})
    assert len(calls) == 2
    assert claim_review.cloudflare.completion is original


def test_strategy_restores_completion_after_provider_exception(monkeypatch):
    def fail(messages, schema):
        raise RuntimeError("mock provider failure")

    monkeypatch.setattr(claim_review.cloudflare, "completion", fail)
    original = claim_review.cloudflare.completion
    with pytest.raises(RuntimeError, match="mock provider failure"):
        with claim_review.repaired_claims_experiment():
            claim_review.cloudflare.completion(request_messages(), {})
    assert claim_review.cloudflare.completion is original


def test_registry_identity_is_separate_from_outcome_numbers():
    context = {'evidence': [{'citation': 'ClinicalTrials.gov:NCT00545844',
        'text': 'At baseline 313 participants were assessed and 301 completed week 8 asthma control assessments.',
        'matched_passages': []}]}
    sentence = 'In NCT00545844, 313 participants were assessed at baseline and 301 completed week 8.'
    original = draft(claim(sentence, citation='ClinicalTrials.gov:NCT00545844'))
    content = review(item(text=sentence, quotes=[context['evidence'][0]['text']]))
    assert claim_review.render_repaired(original, content, context)['paragraphs']
    wrong = sentence.replace('NCT00545844', 'NCT99999999')
    with pytest.raises(ValueError):
        claim_review.render_repaired(original, review(item(text=wrong, quotes=[context['evidence'][0]['text']])), context)


def test_feedback_identifies_unreported_percentages_without_treating_id_as_statistic():
    context = {'evidence': [{'citation': 'ClinicalTrials.gov:NCT00545844',
        'text': 'At baseline, 312 of 313 participants were uncontrolled and at week 8, 72 of 301 were uncontrolled.',
        'matched_passages': []}]}
    original = draft(claim('In NCT00545844, 312 of 313 participants (99.7%) were uncontrolled.', citation='ClinicalTrials.gov:NCT00545844'))
    notes = claim_review.draft_feedback(original, context)
    assert notes[0]['numbers_not_present_in_source'] == ['99.7']


def test_explicit_registry_design_is_indexed_as_same_source_support():
    context = {'question': 'What design was used?', 'evidence': [{
        'citation': 'ClinicalTrials.gov:NCT00545844', 'text': 'Effectiveness of adding treatment in adults.',
        'matched_passages': [], 'registry_design': {'allocation': 'NON_RANDOMIZED', 'intervention_model': 'SINGLE_GROUP'}}]}
    sentence = 'The registry reports NON_RANDOMIZED allocation and a SINGLE_GROUP intervention model.'
    original = draft(claim(sentence, citation='ClinicalTrials.gov:NCT00545844'))
    index = claim_review.passage_index(original, context)
    key = next(key for key,value in index.items() if 'Allocation:' in value['text'])
    expanded = claim_review.expand_review(review(item(text=sentence, quotes=[key])), original, index)
    assert claim_review.render_repaired(original, expanded, context)['paragraphs']
