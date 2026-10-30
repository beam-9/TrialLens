"""Source refresh keeps recoverable edits and labels historical answers honestly."""
from triallens.models import Answer, EvidenceExtraction, EvidenceSource, SourceType, Workspace
from triallens.provenance import source_revision
from triallens.rag import BriefService
from triallens.store import JsonStore


def fixture():
    workspace = Workspace(condition='asthma', source_types=[SourceType.pubmed])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
                            external_id='one', title='Trial', abstract='Original source text.')
    row = EvidenceExtraction(workspace_id=workspace.id, source_id=source.id, source_type=source.source_type,
                             title='Trial', citation='PubMed:one', outcome_result='Reviewer correction', review_status='reviewed')
    return workspace, source, row


def test_changed_evidence_archives_edits_without_changing_answers(tmp_path):
    workspace, source, row = fixture()
    store = JsonStore(tmp_path/'store.json')
    store.create_workspace(workspace)
    store.replace_workspace_evidence(workspace.id, [source], [], [row])
    answer = Answer(workspace_id=workspace.id, question='What happened?', short_answer='Original result',
                    evidence=[], limitations=[], citations=['PubMed:one'], retrieved_chunks=[], saved_to_brief=True,
                    source_revisions={'PubMed:one': source_revision(source)})
    store.save_answer(answer)
    before = store._read()['answers']
    refreshed = source.model_copy(update={'abstract': 'Updated source results.'})
    new_row = row.model_copy(update={'outcome_result': 'New extraction', 'review_status': 'needs_review'})
    store.replace_workspace_evidence(workspace.id, [refreshed], [], [new_row])
    revisions = store.list_evidence_revisions(workspace.id)
    assert len(revisions) == 1
    assert revisions[0]['extractions'][row.id]['outcome_result'] == 'Reviewer correction'
    assert revisions[0]['extractions'][row.id]['review_status'] == 'reviewed'
    assert revisions[0]['sources'][source.id]['abstract'] == 'Original source text.'
    assert store._read()['answers'] == before
    brief = BriefService().generate(workspace, [refreshed], [new_row], [answer])
    assert any('versions that have since changed' in gap for gap in brief.evidence_gaps)


def test_fetch_timestamp_alone_does_not_create_revision_or_stale_warning(tmp_path):
    workspace, source, row = fixture()
    store = JsonStore(tmp_path/'store.json')
    store.create_workspace(workspace)
    store.replace_workspace_evidence(workspace.id, [source], [], [row])
    refreshed = source.model_copy(update={'created_at': '2030-01-01T00:00:00+00:00'})
    assert source_revision(refreshed) == source_revision(source)
    store.replace_workspace_evidence(workspace.id, [refreshed], [], [row])
    assert store.list_evidence_revisions(workspace.id) == []


def test_legacy_saved_answer_reports_untracked_versions_not_invalidity():
    workspace, source, row = fixture()
    answer = Answer(workspace_id=workspace.id, question='Earlier question', short_answer='Earlier answer',
                    evidence=[], limitations=[], citations=['PubMed:one'], retrieved_chunks=[], saved_to_brief=True)
    brief = BriefService().generate(workspace, [source], [row], [answer])
    assert any('not tracked' in gap for gap in brief.evidence_gaps)
    assert not any('versions that have since changed' in gap for gap in brief.evidence_gaps)
