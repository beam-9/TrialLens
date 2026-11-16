"""Production guard regression tests; provider calls are mocked, not inferred."""
import json
from pathlib import Path

import pytest

from triallens import conversation
from triallens.label_checks import pediatric_indication_issue
from triallens.models import Answer, EvidenceSource, SourceType, Workspace


def test_observed_bad_canary_rejected_and_compact_controls_preserved():
    root = Path(__file__).parents[1] / 'evaluation/answer_coverage/results'
    bad = json.loads((root / 'quality-v6-llama-repair-canary-2026-11-01.json').read_text())[0]
    assert pediatric_indication_issue(bad['answer']['direct_answer'], bad['generation_context']['evidence'])
    for name in ('label-scope-control', 'label-scope-candidate'):
        run = json.loads((root / f'{name}-2026-11-01.json').read_text())[0]
        assert pediatric_indication_issue(run['answer']['direct_answer'], run['generation_context']['evidence']) is None
    # Acceptance by this guard does not verify the candidate's uncertainty claims.


@pytest.mark.parametrize('statement,rejected', [
    ('Example is approved for children', True),
    ('Example is used in children; the trial enrolled 12 participants', True),
    ('Example is indicated for pediatric patients 12 years and older', False),
    ('Example is indicated for children aged 12 and older', False),
    ('Example is approved for children at least 12 years old', False),
    ('Example is approved for pediatric patients ≥12 years', False),
    ('Example is approved for pediatric patients\u202f≥\u202f12\u202fyears', False),
    ('Example is approved for children >= 12 years old', False),
    ('Example is indicated for children 12+ years', False),
    ('Example is approved for children ≥11 years', True),
    ('Example is approved for children ≤12 years', True),
    ('Example is approved for children >=120 years', True),
    ('Example is approved for children under 12; adults are ≥12 years', True),
    ('Example is approved for children under 12 and adults are >=12 years', True),
    ('Example is approved for children under 12; another cohort is 12+ years', True),
    ('Example is not approved for children', False),
    ('Use in children is unknown', False),
])
def test_explicit_known_age_boundary_only(statement, rejected):
    records = [{'source_type': 'fda_label', 'citation': 'label:1', 'text':
                'Example tablets are indicated for pediatric patients 12 years and older.', 'matched_passages': []}]
    assert bool(pediatric_indication_issue(statement + ' [label:1].', records)) == rejected
    assert pediatric_indication_issue(statement + ' [unrelated].', records) is None


@pytest.mark.parametrize('qualification,accepted', [
    ('', False), (' aged 12 and older', True), (' ≥12 years', True),
    (' >= 12 years', True), (' 12+ years', True), (' ≥11 years', False),
])
def test_final_guard_runs_after_two_passes_without_retry_or_answer_charge(monkeypatch, tmp_path, qualification, accepted):
    monkeypatch.setenv('TRIALLENS_CHAT_PROVIDER', 'cloudflare')
    monkeypatch.setenv('TRIALLENS_USAGE_PATH', str(tmp_path / 'usage.sqlite3'))
    monkeypatch.setattr(conversation, 'chat_configured', lambda: True)
    w = Workspace(condition='disease', source_types=[SourceType.fda_label])
    source = EvidenceSource(workspace_id=w.id, source_type=SourceType.fda_label, external_id='EXAMPLE', title='Example label',
                            abstract='Example tablets are indicated for adults and pediatric patients 12 years and older with disease.')
    fallback = Answer(workspace_id=w.id, question='What is the intended use?', short_answer='Source excerpt', evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    calls = []
    def complete(messages, schema):
        calls.append(messages)
        wording = 'Example is approved for children' + qualification
        return json.dumps({'paragraphs': [wording + ' [openFDA label:EXAMPLE].'], 'cited_sources': ['openFDA label:EXAMPLE'], 'uncertainty': []})
    monkeypatch.setattr(conversation.cloudflare, 'completion', complete)
    answer = conversation.ConversationService().generate(w, fallback.question, [], [source], fallback)
    assert len(calls) == 2
    assert (answer.generation_mode == 'conversational') == accepted
    from triallens.usage import UsageLedger
    assert UsageLedger().status()['generated_answers'] == int(accepted)
    if not accepted:
        assert 'failed validation' in answer.generation_note and 'children' not in answer.direct_answer


def test_age_notation_in_citation_identifier_cannot_supply_a_missing_boundary():
    citation = 'label:12 years and older ≥12 years'
    records = [{'source_type': 'fda_label', 'citation': citation, 'text':
                'Example tablets are indicated for pediatric patients 12 years and older.', 'matched_passages': []}]
    assert pediatric_indication_issue(f'Example is approved for children [{citation}].', records)


def test_recorded_native_mathematical_age_floor_is_not_a_missing_boundary():
    root = Path(__file__).parents[1] / 'evaluation/answer_coverage/results'
    run = json.loads((root / 'revision-native-combined-2026-11-16.json').read_text())[0]
    final = json.loads(run['provider_outputs'][-1]['response'])
    records = run['generation_context']['evidence']
    allowed = {record['citation'] for record in records}
    direct = conversation.normalize_citations('\n\n'.join(final['paragraphs']), allowed)
    assert pediatric_indication_issue(direct, records) is None
    import re
    broadened = re.sub(r'≥\s*10(?=\s*years)', '≥9', direct)
    assert broadened != direct
    assert pediatric_indication_issue(broadened, records)
