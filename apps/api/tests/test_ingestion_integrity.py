"""Refresh integrity tests: unavailable upstreams must not erase indexed evidence."""
from fastapi.testclient import TestClient

from triallens import main
from triallens.models import EvidenceSource, SourceType, Workspace
from triallens.rag import build_chunks, build_extractions
from triallens.store import JsonStore


def test_partial_refresh_preserves_failed_connector_sources_and_review(monkeypatch, tmp_path):
    store = JsonStore(tmp_path / 'research.json')
    workspace = store.create_workspace(Workspace(condition='diabetes', source_types=[SourceType.pubmed, SourceType.clinical_trials]))
    previous = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.clinical_trials, external_id='NCT-existing', title='Existing trial', abstract='A trial evaluated diabetes outcomes.')
    old_paper = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed, external_id='old-paper', title='Superseded paper', abstract='Earlier diabetes evidence.')
    initial = [previous, old_paper]
    store.replace_workspace_evidence(workspace.id, initial, build_chunks(initial), build_extractions(initial, workspace))
    old_chunks = [chunk for chunk in store.list_chunks(workspace.id) if chunk.source_id == previous.id]
    row = next(item for item in store.list_extractions(workspace.id) if item.source_id == previous.id)
    store.update_extraction(workspace.id, row.id, {'review_status': 'reviewed', 'outcome_result': 'Researcher correction.'})

    async def fetch(workspace, diagnostics):
        diagnostics.update({'pubmed': 'available', 'clinical_trials': 'unavailable'})
        return [EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed, external_id='new-paper', title='New paper', abstract='The diabetes trial reported results.')]

    monkeypatch.setattr(main, 'store', store)
    monkeypatch.setattr(main, 'fetch_sources', fetch)
    response = TestClient(main.app).post(f'/workspaces/{workspace.id}/ingest')
    assert response.status_code == 200
    assert response.json()['status'] == 'partial'
    # Reopen the store to verify persisted integrity, not just in-memory state.
    reopened = JsonStore(tmp_path / 'research.json')
    sources = reopened.list_sources(workspace.id)
    assert {source.external_id for source in sources} == {'NCT-existing', 'new-paper'}
    retained = next(item for item in reopened.list_extractions(workspace.id) if item.source_id == previous.id)
    assert retained.review_status == 'reviewed'
    assert retained.outcome_result == 'Researcher correction.'
    assert [chunk for chunk in reopened.list_chunks(workspace.id) if chunk.source_id == previous.id] == old_chunks
    assert retained.id == row.id
    assert any('previously indexed evidence was kept' in warning for warning in response.json()['ingestion_warnings'])
    assert reopened.list_workspaces()[0].status == 'partial'


def test_refresh_updates_extraction_provenance_when_only_source_date_and_url_change(monkeypatch, tmp_path):
    store = JsonStore(tmp_path / 'research.json')
    workspace = store.create_workspace(Workspace(condition='diabetes', source_types=[SourceType.pubmed]))
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed, external_id='same-paper', title='Diabetes trial', abstract='A clinical trial evaluated diabetes outcomes.', publication_date='2024', url='https://example.org/old')
    store.replace_workspace_evidence(workspace.id, [source], build_chunks([source]), build_extractions([source], workspace))
    row = store.list_extractions(workspace.id)[0]
    store.update_extraction(workspace.id, row.id, {
        'review_status': 'reviewed',
        'outcome_result': 'Reviewer correction from the previous source version.',
    })

    async def fetch(workspace, diagnostics):
        diagnostics.update({'pubmed': 'available'})
        return [source.model_copy(update={'id': 'refreshed-id', 'publication_date': '2025', 'url': 'https://example.org/new'})]

    monkeypatch.setattr(main, 'store', store)
    monkeypatch.setattr(main, 'fetch_sources', fetch)
    assert TestClient(main.app).post(f'/workspaces/{workspace.id}/ingest').status_code == 200
    refreshed = store.list_extractions(workspace.id)[0]
    assert refreshed.source_id == source.id
    assert refreshed.publication_date == '2025'
    assert refreshed.source_url == 'https://example.org/new'
    assert refreshed.review_status == 'needs_review'
    assert refreshed.outcome_result != 'Reviewer correction from the previous source version.'
    assert any('archived with the previous source version' in item for item in refreshed.evidence_limitations)


def test_no_matches_retains_prior_connector_cohort_when_another_connector_returns_sources(monkeypatch, tmp_path):
    store = JsonStore(tmp_path / 'research.json')
    workspace = store.create_workspace(Workspace(condition='diabetes', source_types=[SourceType.pubmed, SourceType.clinical_trials]))
    old_paper = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
                               external_id='old-paper', title='Existing paper', abstract='Earlier diabetes evidence.')
    old_trial = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.clinical_trials,
                               external_id='old-trial', title='Existing trial', abstract='Earlier trial evidence.')
    initial = [old_paper, old_trial]
    store.replace_workspace_evidence(workspace.id, initial, build_chunks(initial), build_extractions(initial, workspace))
    old_row = next(row for row in store.list_extractions(workspace.id) if row.source_id == old_paper.id)
    store.update_extraction(workspace.id, old_row.id, {'review_status': 'reviewed', 'outcome_result': 'Manual review retained.'})
    old_chunks = [chunk for chunk in store.list_chunks(workspace.id) if chunk.source_id == old_paper.id]
    new_trial = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.clinical_trials,
                               external_id='new-trial', title='New trial', abstract='New diabetes trial evidence.')

    async def fetch(workspace, diagnostics):
        diagnostics.update({'pubmed': 'no_matches', 'clinical_trials': 'available'})
        return [new_trial]

    monkeypatch.setattr(main, 'store', store)
    monkeypatch.setattr(main, 'fetch_sources', fetch)
    response = TestClient(main.app).post(f'/workspaces/{workspace.id}/ingest')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'partial'
    assert {source.external_id for source in store.list_sources(workspace.id)} == {'old-paper', 'new-trial'}
    retained = next(row for row in store.list_extractions(workspace.id) if row.source_id == old_paper.id)
    assert retained.review_status == 'reviewed'
    assert retained.outcome_result == 'Manual review retained.'
    assert [chunk for chunk in store.list_chunks(workspace.id) if chunk.source_id == old_paper.id] == old_chunks
    assert any('no matching records were returned' in warning and 'PubMed' in warning
               for warning in payload['ingestion_warnings'])


def test_unchanged_source_refresh_preserves_manual_extraction_edits(monkeypatch, tmp_path):
    store = JsonStore(tmp_path / 'research.json')
    workspace = store.create_workspace(Workspace(condition='diabetes', source_types=[SourceType.pubmed]))
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
                            external_id='same-paper', title='Diabetes trial', abstract='A clinical trial evaluated diabetes outcomes.')
    store.replace_workspace_evidence(workspace.id, [source], build_chunks([source]), build_extractions([source], workspace))
    row = store.list_extractions(workspace.id)[0]
    store.update_extraction(workspace.id, row.id, {
        'review_status': 'reviewed',
        'outcome_result': 'Manual correction retained for unchanged source.',
        'supporting_quote': 'Reviewer-verified quote.',
    })

    async def fetch(workspace, diagnostics):
        diagnostics.update({'pubmed': 'available'})
        return [source.model_copy(update={'id': 'new-transient-id'})]

    monkeypatch.setattr(main, 'store', store)
    monkeypatch.setattr(main, 'fetch_sources', fetch)
    response = TestClient(main.app).post(f'/workspaces/{workspace.id}/ingest')

    assert response.status_code == 200
    refreshed = store.list_extractions(workspace.id)[0]
    assert refreshed.id == row.id
    assert refreshed.review_status == 'reviewed'
    assert refreshed.outcome_result == 'Manual correction retained for unchanged source.'
    assert refreshed.supporting_quote == 'Reviewer-verified quote.'
