import json
from pathlib import Path

import pytest

from evaluation.label_scope import label_scope_experiment, scope_clauses, scope_issues


def record(text, citation='label:1'):
    return {'source_type': 'fda_label', 'citation': citation, 'text': text, 'matched_passages': []}


def test_exact_complete_spans_no_inferred_formulation():
    text = '1 INDICATIONS & USAGE Example tablets are indicated for adults and pediatric patients 12 years of age and older with disease. Other warnings follow.'
    r = record(text)
    cue = scope_clauses(r)[0]
    assert text[cue['start']:cue['end']] == cue['quote']
    assert cue['location'] == 'text' and cue['citation'] == 'label:1'
    assert 'immediate-release' not in json.dumps(cue)
    assert len(cue['text_sha256']) == 64


@pytest.mark.parametrize('text', ['Example tablets are indicated for adults', 'There are no indication data.', 'a' * 1201 + ' is indicated for adults.'])
def test_incomplete_absent_and_overlong_are_unknown(text):
    assert scope_clauses(record(text)) == []


def test_decimal_and_complete_combination_clause_preserved():
    text = 'Example is a combination of A and B, indicated for adults with type 2 disease at 1.5 mg.'
    assert scope_clauses(record(text))[0]['quote'] == text
    assert scope_clauses({**record(text), 'source_type': 'pubmed'}) == []


def test_cues_only_reference_retained_context_with_passage_pointer_and_dedup():
    text = 'Example tablets are indicated for adults.'
    r = record('Unrelated abstract.')
    r['matched_passages'] = [text, text]
    cues = scope_clauses(r)
    assert len(cues) == 1 and cues[0]['location'] == 'matched_passages[0]'


def test_diagnostic_detects_observed_canary_age_loss_not_a_quality_pass():
    path = Path(__file__).parents[1] / 'evaluation/answer_coverage/results/quality-v6-llama-repair-canary-2026-11-01.json'
    run = json.loads(path.read_text())[0]
    answer = {'paragraphs': run['answer']['direct_answer'].split('\n\n')}
    notes = scope_issues(answer, run['generation_context'])
    assert any('10 years' in note for note in notes)
    assert any('populations differ' in note for note in notes)


def test_other_medicine_age_is_not_hardcoded_and_negative_claim_not_rewritten():
    payload = {'evidence': [record('Example tablets are indicated for pediatric patients 12 years and older.') ]}
    assert scope_issues({'paragraphs': ['Example is approved for children [label:1].']}, payload)
    assert scope_issues({'paragraphs': ['Example is used in children; 12 patients were treated [label:1].']}, payload)
    assert not scope_issues({'paragraphs': ['Example is approved for children aged 12 and older [label:1].']}, payload)
    assert not scope_issues({'paragraphs': ['Use in children is unknown in this excerpt [label:1].']}, payload)


def test_experiment_is_inert_and_restores_context_and_provider_on_failure(monkeypatch):
    from triallens import conversation
    original_build = lambda sources, chunks: [record('Example tablets are indicated for adults.')]
    def original_completion(messages, schema):
        raise RuntimeError('provider failure')
    monkeypatch.setattr(conversation, 'build_evidence_records', original_build)
    monkeypatch.setattr(conversation.cloudflare, 'completion', original_completion)
    with label_scope_experiment(False):
        assert conversation.build_evidence_records is original_build
    with pytest.raises(RuntimeError), label_scope_experiment(True):
        records = conversation.build_evidence_records([], [])
        assert records[0]['scope_clauses'] and 'scope_clauses' not in original_build([], [])[0]
        conversation.cloudflare.completion([{'role': 'system', 'content': ''}, {'role': 'user', 'content': json.dumps({'evidence': records})}], {})
    assert conversation.build_evidence_records is original_build
    assert conversation.cloudflare.completion is original_completion


def test_final_scope_failure_rejected_without_retry_and_feedback_is_bounded(monkeypatch):
    from triallens import conversation
    calls = []
    payload = {'evidence': [record('Example tablets are indicated for pediatric patients 12 years and older.')]}
    bad = {'paragraphs': ['Example is used in children [label:1].'], 'cited_sources': ['label:1'], 'uncertainty': []}
    def complete(messages, schema):
        calls.append(messages)
        return json.dumps(bad)
    monkeypatch.setattr(conversation.cloudflare, 'completion', complete)
    messages = [{'role': 'system', 'content': ''}, {'role': 'user', 'content': json.dumps(payload)},
                {'role': 'assistant', 'content': json.dumps(bad)}, {'role': 'user', 'content': 'review'}]
    with pytest.raises(ValueError), label_scope_experiment(True):
        conversation.cloudflare.completion(messages, {})
    assert len(calls) == 1
    assert '12 years' in calls[0][-1]['content']
    assert messages[-1]['content'] == 'review'
