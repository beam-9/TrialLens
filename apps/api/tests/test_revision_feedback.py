import importlib.util
import json

import pytest


MODULE = __import__("pathlib").Path(__file__).resolve().parents[1] / "evaluation/answer_coverage/revision_feedback.py"
spec = importlib.util.spec_from_file_location("revision_feedback", MODULE)
feedback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feedback)


def messages(question, paragraphs, cited_sources, source_text="A measured score improved by 0.5 points at week 8."):
    payload = {"question": question, "evidence": [
        {"citation": "PubMed:123", "text": source_text, "matched_passages": []},
        {"citation": "PubMed:999", "text": "Mortality count was 4 in an unrelated analysis.", "matched_passages": []},
    ]}
    draft = {"paragraphs": paragraphs, "cited_sources": cited_sources, "uncertainty": []}
    return [
        {"role": "system", "content": "system"},
        {"role": "user", "content": json.dumps(payload)},
        {"role": "assistant", "content": json.dumps(draft)},
        {"role": "user", "content": "Revise this answer."},
    ]


def codes(call):
    return {item["code"] for item in feedback.feedback_notes(call)}


def test_feedback_targets_only_second_call_copies_messages_and_keeps_two_calls(monkeypatch):
    from triallens import conversation

    calls = []

    def fake_completion(items, schema):
        calls.append((items, schema))
        return "{}"

    original = conversation.cloudflare.completion
    monkeypatch.setattr(conversation.cloudflare, "completion", fake_completion)
    first = [{"role": "system", "content": "s"}, {"role": "user", "content": "{}"}]
    second = messages("How much did it change?", ["It improved [PubMed:123]."], ["PubMed:123"])
    original_last = second[-1]["content"]
    with feedback.revision_feedback_experiment():
        conversation.cloudflare.completion(first, {})
        conversation.cloudflare.completion(second, {})
        assert conversation.cloudflare.completion is not original
    assert conversation.cloudflare.completion is fake_completion
    assert len(calls) == 2
    assert calls[0][0] is first
    assert calls[1][0] is not second
    assert calls[1][0][-1] is not second[-1]
    assert calls[1][0][-1]["content"].startswith(original_last)
    assert "requested_statistic_missing" in calls[1][0][-1]["content"]
    assert second[-1]["content"] == original_last


def test_completion_restores_even_when_experiment_raises(monkeypatch):
    from triallens import conversation

    previous = conversation.cloudflare.completion
    with pytest.raises(RuntimeError):
        with feedback.revision_feedback_experiment():
            raise RuntimeError("injected")
    assert conversation.cloudflare.completion is previous


def test_invalid_draft_unknown_citation_and_28_word_copy_are_machine_reported():
    invalid = messages("Explain the result", ["x"], [], source_text="short")
    invalid[2]["content"] = "{broken"
    assert codes(invalid) == {"invalid_draft"}

    copied = " ".join(f"term{i}" for i in range(28))
    call = messages("Explain the result", [copied + " [PubMed:123]"], ["Unknown:7"], copied)
    reported = codes(call)
    assert "unknown_citation" in reported
    assert "citation_list_mismatch" in reported
    assert "long_source_copy" in reported


def test_rarity_feedback_is_absence_only_and_skips_scoped_uncertainty():
    asserted = messages("Is the risk common?", ["The reaction is rare [PubMed:123]."], ["PubMed:123"], "Reports list the reaction without a frequency estimate.")
    assert "rarity_word_not_in_cited_context" in codes(asserted)

    uncertain = messages(
        "Is the risk common?",
        ["Frequency was not reported here, so the excerpt cannot establish whether the event is rare or common [PubMed:123]."],
        ["PubMed:123"],
        "The source reports events but gives no denominator or frequency estimate.",
    )
    assert "rarity_word_not_in_cited_context" not in codes(uncertain)


def test_quantitative_feedback_ignores_citation_digits_and_does_not_force_unrelated_numbers():
    no_number = messages("How much did the symptom score change?", ["It improved [PubMed:123]."], ["PubMed:123"])
    assert "requested_statistic_missing" in codes(no_number)
    assert "999" not in json.dumps(feedback.feedback_notes(no_number))

    scoped_gap = messages("What was the effect size for mortality?", ["Mortality was not reported in this excerpt [PubMed:123]."], ["PubMed:123"])
    assert "requested_statistic_missing" not in codes(scoped_gap)

    measured = messages("What was the effect size?", ["The score changed by 0.5 points at week 8 [PubMed:123]."], ["PubMed:123"])
    assert "requested_statistic_missing" not in codes(measured)


def test_missing_citation_note_allows_scoped_gap_paragraph():
    call = messages("What happened?", ["This excerpt does not report the requested outcome."], [])
    assert "paragraph_without_citation" not in codes(call)

    cited_fact = messages("What happened?", ["The score improved."], [])
    assert "paragraph_without_citation" in codes(cited_fact)


def test_every_rendered_paragraph_needs_citation_when_answer_cites_any_source():
    blank_line = messages("What happened?", ["The score improved [PubMed:123].\n\nThis excerpt does not report long-term results."], ["PubMed:123"])
    assert "paragraph_without_citation" in codes(blank_line)
    assert "scoped gaps" in next(note["message"] for note in feedback.feedback_notes(blank_line)
                                 if note["code"] == "paragraph_without_citation")

    separate_gap = messages("What happened?", [
        "The score improved [PubMed:123].",
        "This excerpt does not report long-term results.",
    ], ["PubMed:123"])
    assert "paragraph_without_citation" in codes(separate_gap)

    standalone_gap = messages("What happened?", ["This excerpt does not report the requested outcome."], [])
    assert "paragraph_without_citation" not in codes(standalone_gap)


def test_cited_source_must_be_inline_and_rarity_compares_exact_term():
    cited_only = messages("What happened?", ["The score improved [PubMed:123]."], ["PubMed:123", "PubMed:999"])
    assert "cited_source_not_inline" in codes(cited_only)

    near_match = messages("Is it rare?", ["The reaction is rare [PubMed:123]."], ["PubMed:123"],
                          "The event occurred frequently in this synthetic source.")
    assert "rarity_word_not_in_cited_context" in codes(near_match)
