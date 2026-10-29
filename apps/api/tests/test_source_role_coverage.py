"""Requested source roles survive actual HTTP Ask context assembly."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from triallens import conversation, main
from triallens.models import Workspace, EvidenceSource, EvidenceChunk, SourceType
from triallens.rag import Retriever
from triallens.store import JsonStore

ROOT = Path(__file__).resolve().parents[1]


def frozen():
    return json.loads((ROOT / 'evaluation/m0/snapshots/real-metformin.json').read_text())


def question():
    return json.loads((ROOT / 'evaluation/answer_coverage/m0-quality-holdout-cases.json').read_text())['cases'][0]['question']


def test_requested_label_registry_roles_are_retrieved_without_filter_bypass():
    data = frozen()
    workspace = Workspace.model_validate(data['workspace'])
    sources = [EvidenceSource.model_validate(s) for s in data['sources']]
    chunks = [EvidenceChunk.model_validate(c) for c in data['chunks']]
    result = Retriever().retrieve_conversation(workspace, question(), chunks, sources)
    assert len(result) <= 8
    assert len({c.source_id for c in result}) == len(result)
    assert {'ClinicalTrials.gov:NCT05689684', 'openFDA label:FDA-LABEL-metformin-3'} <= {c.citation for c in result}
    filtered = Retriever().retrieve_conversation(workspace, question(), chunks, sources, [SourceType.pubmed])
    assert filtered and all(c.source_type == SourceType.pubmed for c in filtered)


def test_requested_role_records_reach_both_generation_passes_over_http(monkeypatch, tmp_path):
    data = frozen()
    content = {key: {} for key in ('workspaces', 'sources', 'chunks', 'extractions', 'answers', 'briefs')}
    content['workspaces'][data['workspace']['id']] = data['workspace']
    for key in ('sources', 'chunks', 'extractions'):
        content[key] = {item['id']: item for item in data[key]}
    store = JsonStore(tmp_path / 'store.json')
    store._write(content)
    monkeypatch.setattr(main, 'store', store)
    monkeypatch.setenv('TRIALLENS_CHAT_PROVIDER', 'cloudflare')
    monkeypatch.setenv('TRIALLENS_USAGE_PATH', str(tmp_path / 'usage.sqlite3'))
    monkeypatch.setattr(conversation, 'chat_configured', lambda: True)
    seen = []
    def complete(messages, schema):
        seen.append(json.loads(messages[1]['content']))
        return json.dumps({'paragraphs': ['The registry excerpt supplies the planned-study rationale [ClinicalTrials.gov:NCT05689684].'],
                           'cited_sources': ['ClinicalTrials.gov:NCT05689684'], 'uncertainty': []})
    monkeypatch.setattr(conversation.cloudflare, 'completion', complete)
    response = TestClient(main.app).post('/workspaces/' + data['workspace']['id'] + '/ask', json={'question': question()})
    assert response.status_code == 200
    assert response.json()['generation_mode'] == 'conversational'
    assert len(seen) == 2 and seen[0]['evidence'] == seen[1]['evidence']
    citations = {r['citation'] for r in seen[0]['evidence']}
    assert {'ClinicalTrials.gov:NCT05689684', 'openFDA label:FDA-LABEL-metformin-3'} <= citations
