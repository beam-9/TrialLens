"""The candidate reuses complete source passages, not prior answer claims."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluation'))
from paper_reading import paper_reading_experiment, reading_focus
from triallens import cloudflare


def payload(question='Give numerical results and uncertainty.'):
    return {'question': question, 'history': [], 'evidence': [{
        'citation': 'PubMed:1', 'text': 'Abstract',
        'matched_passages': ['Arm A decreased 0.5±0.1; Arm B increased 0.2±0.1 at 12 weeks.',
                             'Fig. 2. Difference -0.7 (95% CI -0.9 to -0.5).'],
        'paper_passage_links': [{'matched_passage_index': 0, 'section': 'Full text paragraph 001'},
                                {'matched_passage_index': 1, 'section': 'Full text figure caption 001'}]}]}


def test_focus_preserves_entire_linked_packets_without_derived_numbers():
    p = payload()
    result = reading_focus(p)
    assert [r['reported_passage'] for r in result] == p['evidence'][0]['matched_passages']
    assert all(r['citation'] == 'PubMed:1' for r in result)
    assert reading_focus(payload('Do these results establish lower mortality?')) == []


def test_no_unlinked_or_oversized_passage_is_promoted_or_trimmed():
    p = payload(); p['evidence'][0]['matched_passages'][0] = '±' * 2601
    p['evidence'][0]['paper_passage_links'].pop()
    assert reading_focus(p) == []


def test_followup_uses_parent_question_for_intent_not_parent_prose_as_evidence():
    p = payload('Explain that more simply.')
    p['history'] = [{'question': 'Give statistics and uncertainty.', 'answer': 'Invented 999±88.'}]
    result = reading_focus(p)
    assert len(result) == 2 and '999' not in json.dumps(result)


def test_wrapper_only_changes_revision_and_restores_provider(monkeypatch):
    calls = []
    def complete(messages, schema):
        calls.append(messages)
        return '{}'
    monkeypatch.setattr(cloudflare, 'completion', complete)
    p = payload(); messages = [{'role': 'system', 'content': 'rules'}, {'role': 'user', 'content': json.dumps(p)}]
    revision = [*messages, {'role': 'assistant', 'content': '{}'}, {'role': 'user', 'content': 'revise'}]
    with paper_reading_experiment(True):
        cloudflare.completion(messages, {})
        cloudflare.completion(revision, {})
    assert calls[0] is messages
    assert '0.5±0.1' in calls[1][-1]['content']
    assert revision[-1]['content'] == 'revise'
    assert cloudflare.completion is complete
