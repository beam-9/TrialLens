import importlib.util
import json
import sys
from pathlib import Path

import pytest

from evaluation.numeric_checks import numeric_values, unsupported_numbers


_API = Path(__file__).resolve().parents[1]
_EVALUATION = _API / "evaluation"
sys.path.insert(0, str(_EVALUATION))
_FEEDBACK_SPEC = importlib.util.spec_from_file_location(
    "revision_feedback", _EVALUATION / "answer_coverage/revision_feedback.py"
)
feedback = importlib.util.module_from_spec(_FEEDBACK_SPEC)
sys.modules["revision_feedback"] = feedback
_FEEDBACK_SPEC.loader.exec_module(feedback)


def test_numeric_values_normalize_common_formats_and_ranges():
    assert numeric_values("2,550 participants; 2550 total; 0.5 and .5; 1–5") == {
        "2550", "0.5", "1", "5"
    }
    assert numeric_values("−0.5, -2, 1–5") == {"-0.5", "-2", "1", "5"}
    assert numeric_values("1-5") == {"1", "5"}
    assert numeric_values("1e-3 and 2.5E+2") == {"0.001", "250"}
    assert numeric_values("1e999999 and 2e-101") == set()


def test_numeric_values_do_not_extract_embedded_ids_or_citation_digits():
    assert numeric_values("trial NCT00545844 [ClinicalTrials.gov:NCT12345678] n=145") == {"145"}
    assert numeric_values("OG045 and cohort145") == set()


def test_only_numbers_absent_from_that_paragraphs_cited_source_are_reported():
    payload = {"evidence": [
        {"citation": "PubMed:1", "text": "Response was 1–5% among 145 participants."},
        {"citation": "PubMed:2", "text": "The estimate was 99.7%."},
    ]}
    answer = {"paragraphs": ["The response was 1–5% [PubMed:1].", "It reached 45% [PubMed:1]."],
              "cited_sources": ["PubMed:1", "PubMed:2"], "uncertainty": []}
    assert unsupported_numbers(answer, payload) == [
        "paragraphs[2] contains numeric value(s) 45 not found in PubMed:1."
    ]


def test_metadata_titles_dates_and_passages_are_numeric_sources():
    payload = {"evidence": [{
        "citation": "ClinicalTrials.gov:NCT00545844",
        "title": "Trial published 2024",
        "publication_date": "2023-06-01",
        "text": "Registered enrollment 145.",
        "matched_passages": ["Outcome was 99.7% in 2022."],
        "registry_design": {"enrollment": 145, "age": "18 years"},
    }]}
    answer = {"paragraphs": ["The record was published in 2024 and enrolled 145 [ClinicalTrials.gov:NCT00545844].",
                             "The rate was 99.7% [ClinicalTrials.gov:NCT00545844]."],
              "cited_sources": ["ClinicalTrials.gov:NCT00545844"], "uncertainty": []}
    assert unsupported_numbers(answer, payload) == []


def test_calculated_rates_are_not_inferred_from_source_counts():
    payload = {"evidence": [{"citation": "PubMed:1", "text": "There were 3 events among 301 patients."}]}
    answer = {"paragraphs": ["The rate was 99.7% [PubMed:1]."], "cited_sources": ["PubMed:1"], "uncertainty": []}
    assert unsupported_numbers(answer, payload) == [
        "paragraphs[1] contains numeric value(s) 99.7 not found in PubMed:1."
    ]


def test_unattributed_single_declared_source_is_feedback_only():
    payload = {"evidence": [{"citation": "PubMed:1", "text": "Only 145 participants."}]}
    answer = {"paragraphs": ["The sample had 145 participants and 45 events."],
              "cited_sources": ["PubMed:1"], "uncertainty": []}
    assert unsupported_numbers(answer, payload) == [
        "paragraphs[1] contains numeric value(s) 45 not found in PubMed:1."
    ]


def test_no_evidence_or_ambiguous_citations_skips_numeric_check():
    answer = {"paragraphs": ["The rate was 99.7%."], "cited_sources": [], "uncertainty": []}
    assert unsupported_numbers(answer, {"evidence": []}) == []


def _revision_messages(draft_text):
    payload = {"question": "Summarize", "evidence": [
        {"citation": "PubMed:1", "text": "The reported value was 1.0%.", "matched_passages": []}
    ]}
    draft = {"paragraphs": [draft_text], "cited_sources": ["PubMed:1"], "uncertainty": []}
    return [
        {"role": "system", "content": "system"},
        {"role": "user", "content": json.dumps(payload)},
        {"role": "assistant", "content": json.dumps(draft)},
        {"role": "user", "content": "Revise."},
    ]


def test_numeric_guard_adds_mechanical_feedback_and_preserves_correct_two_pass_result(monkeypatch):
    from triallens import conversation

    draft = _revision_messages("The rate was 99.7% [PubMed:1].")
    final = json.dumps({"paragraphs": ["The rate was 1.0% [PubMed:1]."],
                        "cited_sources": ["PubMed:1"], "uncertainty": []})
    calls = []

    def fake_completion(messages, schema):
        calls.append(messages)
        return final

    monkeypatch.setattr(conversation.cloudflare, "completion", fake_completion)
    installed = conversation.cloudflare.completion
    with feedback.revision_feedback_experiment(numeric_guard=True):
        conversation.cloudflare.completion([{"role": "user", "content": "initial"}], {})
        result = conversation.cloudflare.completion(draft, {})
    assert len(calls) == 2
    assert calls[0][0]["content"] == "initial"
    assert calls[1] is not draft
    assert "unreported_number" in calls[1][-1]["content"]
    assert result == final
    assert conversation.cloudflare.completion is installed


def test_numeric_guard_rejects_unreported_number_in_final_answer_and_restores_provider(monkeypatch):
    from triallens import conversation

    draft = _revision_messages("The rate was 1.0% [PubMed:1].")
    final = json.dumps({"paragraphs": ["The rate was 45% [PubMed:1]."],
                        "cited_sources": ["PubMed:1"], "uncertainty": []})
    monkeypatch.setattr(conversation.cloudflare, "completion", lambda messages, schema: final)
    installed = conversation.cloudflare.completion
    with pytest.raises(ValueError, match="unreported numeric values"):
        with feedback.revision_feedback_experiment(numeric_guard=True):
            conversation.cloudflare.completion([{"role": "user", "content": "initial"}], {})
            conversation.cloudflare.completion(draft, {})
    assert conversation.cloudflare.completion is installed


def test_repair_once_uses_two_calls_when_second_answer_has_no_mechanical_failures(monkeypatch):
    from triallens import conversation

    messages = _revision_messages("The rate was 1.0% [PubMed:1].")
    result = json.dumps({"paragraphs": ["The rate was 1.0% [PubMed:1]."],
                         "cited_sources": ["PubMed:1"], "uncertainty": []})
    calls = []
    monkeypatch.setattr(conversation.cloudflare, "completion", lambda items, schema: calls.append(items) or result)
    with feedback.revision_feedback_experiment(repair_once=True):
        conversation.cloudflare.completion([{"role": "user", "content": "initial"}], {})
        actual = conversation.cloudflare.completion(messages, {})
    assert len(calls) == 2
    assert actual == result


def test_repair_once_makes_third_call_for_source_copy_using_exact_final_context(monkeypatch):
    from triallens import conversation

    source = "The study measured a clinically important outcome among participants receiving treatment over a carefully monitored period with consistent follow up and complete reporting of every prespecified result for the full analysis population."
    payload = {"question": "Summarize", "evidence": [
        {"citation": "PubMed:1", "text": source, "matched_passages": []}
    ]}
    copied = source + " [PubMed:1]"
    draft = [{"role": "system", "content": "exact-system"},
             {"role": "user", "content": json.dumps(payload)},
             {"role": "assistant", "content": json.dumps({"paragraphs": [copied], "cited_sources": ["PubMed:1"], "uncertainty": []})},
             {"role": "user", "content": "revise"}]
    second = json.dumps({"paragraphs": [copied], "cited_sources": ["PubMed:1"], "uncertainty": []})
    third = json.dumps({"paragraphs": ["The trial tracked a key outcome during treatment, with follow up and reporting across the enrolled group [PubMed:1]."],
                        "cited_sources": ["PubMed:1"], "uncertainty": []})
    calls = []

    def provider(items, schema):
        calls.append(items)
        return second if len(calls) <= 2 else third

    monkeypatch.setattr(conversation.cloudflare, "completion", provider)
    installed = conversation.cloudflare.completion
    with feedback.revision_feedback_experiment(repair_once=True):
        conversation.cloudflare.completion([{"role": "user", "content": "initial"}], {})
        result = conversation.cloudflare.completion(draft, {})
    assert len(calls) == 3
    repair = calls[2]
    assert repair[0] == draft[0]
    assert repair[1] == draft[1]
    assert repair[2]["content"] == second
    assert "mechanical_feedback" in repair[3]["content"]
    assert "Copied source windows to rephrase" in repair[3]["content"]
    assert result == third
    assert conversation.cloudflare.completion is installed


def test_repair_once_corrects_numeric_failure_and_rejects_bad_third_answer_without_fourth_call(monkeypatch):
    from triallens import conversation

    draft = _revision_messages("The rate was 1.0% [PubMed:1].")
    bad = json.dumps({"paragraphs": ["The rate was 45% [PubMed:1]."],
                      "cited_sources": ["PubMed:1"], "uncertainty": []})
    good = json.dumps({"paragraphs": ["The rate was 1.0% [PubMed:1]."],
                       "cited_sources": ["PubMed:1"], "uncertainty": []})
    calls = []

    def provider(items, schema):
        calls.append(items)
        return good if len(calls) in {1, 3} else bad

    monkeypatch.setattr(conversation.cloudflare, "completion", provider)
    with feedback.revision_feedback_experiment(numeric_guard=True, repair_once=True):
        conversation.cloudflare.completion([{"role": "user", "content": "initial"}], {})
        assert conversation.cloudflare.completion(draft, {}) == good
    assert len(calls) == 3

    calls.clear()
    def always_bad(items, schema):
        calls.append(items)
        return good if len(calls) == 1 else bad

    monkeypatch.setattr(conversation.cloudflare, "completion", always_bad)
    installed = conversation.cloudflare.completion
    with pytest.raises(ValueError, match="unreported numeric values"):
        with feedback.revision_feedback_experiment(numeric_guard=True, repair_once=True):
            conversation.cloudflare.completion([{"role": "user", "content": "initial"}], {})
            conversation.cloudflare.completion(draft, {})
    assert len(calls) == 3
    assert conversation.cloudflare.completion is installed


def test_nonbreaking_hyphens_preserve_numeric_sign_and_range_meaning():
    from triallens.text import normalize_numeric_signs

    assert numeric_values('‑0.58% and ‐55.20%, 1‑5 and 16‑week') == {'-0.58', '-55.2', '1', '5', '16'}
    assert normalize_numeric_signs('NCT‑123 trial‐12 1‑5 ‑.5') == 'NCT‑123 trial‐12 1‑5 -.5'


def test_native_recorded_negatives_do_not_become_unreported_positive_values():
    run_path = _EVALUATION / 'answer_coverage/results/attribution-native-medium-2026-11-06.json'
    run = json.loads(run_path.read_text())[0]
    final = json.loads(run['provider_outputs'][-1]['response'])
    assert unsupported_numbers(final, run['generation_context']) == []


def test_written_hundreds_can_support_numeric_sample_sizes():
    assert numeric_values('One hundred eighty-five adults and two hundred and forty patients') == {'185', '240'}
    assert numeric_values('Negative one hundred twenty-one; nine hundred ninety nine') == {'-121', '999'}
    assert numeric_values('one hundred thousand and one hundred point five') == set()
    run_path = _EVALUATION / 'answer_coverage/results/attribution-native-scoped-2026-11-06.json'
    run = json.loads(run_path.read_text())[0]
    answer = json.loads(run['provider_outputs'][-1]['response'])
    assert unsupported_numbers(answer, run['generation_context']) == []
