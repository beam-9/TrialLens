"""Integrity checks for the frozen M0 inputs, not biomedical answer scoring."""
import hashlib
import json
from pathlib import Path

from triallens.models import EvidenceChunk, EvidenceExtraction, EvidenceSource, Workspace

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / 'apps/api/evaluation/m0'
REQUIRED_CATEGORIES = {
    'metformin_vs_zituvimet', 'standalone_vs_add_on', 'numerical_hba1c',
    'numerical_fasting_glucose', 'comparator_group_difference', 'time_windows',
    'pediatric_age_floor', 'postmarketing_frequency_unknown',
    'not_established_vs_not_measured', 'mixed_significance', 'protocol_vs_results',
    'unrelated_question', 'ambiguous_follow_up', 'summary_source_diversity',
    'treatment_decision', 'source_filtered_history',
}


def inventory():
    return json.loads((FIXTURES / 'inventory.json').read_text())


def test_m0_inventory_covers_retained_failures_and_all_required_categories():
    data = inventory()
    assert data['schema_version'] == 1
    cases = data['cases']
    assert 12 <= len(cases) <= 20
    assert len({case['id'] for case in cases}) == len(cases)
    assert REQUIRED_CATEGORIES <= {tag for case in cases for tag in case['categories']}
    assert {case['seed']['artifact'] for case in cases if case['seed']} == {
        'apps/api/evaluation/final-results.json',
        'apps/api/evaluation/workspace-browser-results.json',
    }
    assert len([case for case in cases if 'real_workspace' in case['categories']]) >= 2
    seen = {}
    for case in cases:
        assert case['must_include'] and case['must_not_claim']
        assert case['critical_error_categories']
        assert case['snapshot_id'] in {snapshot['id'] for snapshot in data['snapshots']}
        parent = case['history_case_id']
        if parent:
            assert parent in seen, 'Follow-ups must execute after their actual generated parent.'
            assert seen[parent]['snapshot_id'] == case['snapshot_id']
            assert seen[parent]['source_types'] == case['source_types']
        if case['seed']:
            outputs = json.loads((ROOT / case['seed']['artifact']).read_text())
            assert outputs[case['seed']['index']]['question'] == case['question']
        seen[case['id']] = case


def test_m0_snapshots_and_original_outputs_match_frozen_hashes():
    data = inventory()
    for artifact in data['snapshots']:
        path = FIXTURES / artifact['path']
        assert path.resolve().is_relative_to(FIXTURES.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact['sha256']
    for artifact in data['retained_outputs']:
        assert hashlib.sha256((ROOT / artifact['path']).read_bytes()).hexdigest() == artifact['sha256']


def test_m0_snapshot_references_validate_and_exclude_saved_research_history():
    for artifact in inventory()['snapshots']:
        data = json.loads((FIXTURES / artifact['path']).read_text())
        assert set(data) == {'workspace', 'sources', 'chunks', 'extractions'}
        workspace = Workspace(**data['workspace'])
        assert workspace.id.startswith('m0-')
        sources = [EvidenceSource(**item) for item in data['sources']]
        chunks = [EvidenceChunk(**item) for item in data['chunks']]
        rows = [EvidenceExtraction(**item) for item in data['extractions']]
        assert len(sources) == artifact['source_count']
        assert len(chunks) == artifact['chunk_count']
        assert len(rows) == artifact['extraction_count']
        assert sum(len(source.abstract) for source in sources) == artifact['source_char_count']
        source_ids = {source.id for source in sources}
        assert len(source_ids) == len(sources)
        for item in [*sources, *chunks, *rows]:
            assert item.workspace_id == workspace.id
            assert item.id.startswith('m0-')
        for item in [*chunks, *rows]:
            assert item.source_id in source_ids
        if artifact['kind'] == 'synthetic_control':
            assert all(source.metadata.get('demo') is True for source in sources)
            assert all('synthetic' in source.abstract.lower() for source in sources)
        assert all(row.review_status == 'unreviewed' for row in rows)
