from fastapi.testclient import TestClient

from triallens import main
from triallens.models import SourceType, Workspace
from triallens.store import JsonStore


def test_document_ask_requires_source_id(monkeypatch, tmp_path):
    test_store = JsonStore(tmp_path / "triallens.json")
    workspace = test_store.create_workspace(
        Workspace(condition="type 2 diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    )
    monkeypatch.setattr(main, "store", test_store)
    client = TestClient(main.app)

    response = client.post(
        f"/workspaces/{workspace.id}/ask",
        json={"question": "What does this document say about safety?", "mode": "document"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "source_id is required for document mode"


def test_conversation_scope_and_brief_lifecycle(monkeypatch, tmp_path):
    from triallens.models import EvidenceSource
    from triallens.rag import build_chunks, build_extractions
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    test_store = JsonStore(tmp_path / "triallens.json")
    workspace = test_store.create_workspace(Workspace(condition="diabetes", intervention="metformin", source_types=[SourceType.pubmed, SourceType.fda_label]))
    sources = [EvidenceSource(workspace_id=workspace.id, source_type=kind, external_id=str(index), title="Metformin diabetes safety", abstract="Metformin adverse reactions include gastrointestinal symptoms. Clinical trial results show improved glycemic control.") for index, kind in enumerate(workspace.source_types)]
    test_store.replace_workspace_evidence(workspace.id, sources, build_chunks(sources))
    test_store.replace_workspace_extractions(workspace.id, build_extractions(sources, workspace))
    monkeypatch.setattr(main, "store", test_store)
    client = TestClient(main.app)
    base = f"/workspaces/{workspace.id}"
    first = client.post(base + "/ask", json={"question": "What safety concerns exist?", "source_types": ["pubmed"]})
    assert first.status_code == 200
    answer = first.json()
    assert all(c.startswith("PubMed:") for c in answer["citations"])
    assert all(c["source_type"] == "pubmed" for c in answer["retrieved_chunks"])
    follow = client.post(base + "/ask", json={"question": "Explain that more simply", "source_types": ["pubmed"], "previous_answer_id": answer["id"]})
    assert follow.status_code == 200
    assert follow.json()["previous_answer_id"] == answer["id"]
    mismatch = client.post(base + "/ask", json={"question": "What about safety?", "source_types": ["fda_label"], "previous_answer_id": answer["id"]})
    assert mismatch.status_code == 400
    assert client.get(base + "/brief").json()["saved_answers"] == []
    assert client.patch(base + f'/answers/{answer["id"]}/brief?saved=true').status_code == 200
    brief = client.get(base + "/brief").json()
    assert brief["saved_answers"][0]["id"] == answer["id"]
    assert brief["key_claims"] == [answer["direct_answer"]]
    row = test_store.list_extractions(workspace.id)[0]
    client.patch(base + f"/extractions/{row.id}", json={"review_status": "reviewed"})
    assert client.get(base + "/brief").json()["review_summary"]["reviewed"] == 1
    client.patch(base + f'/answers/{answer["id"]}/brief?saved=false')
    assert client.get(base + "/brief").json()["saved_answers"] == []
    assert len(client.get(base + "/answers").json()) == 2
    other = test_store.create_workspace(Workspace(condition="migraine", source_types=[]))
    assert client.post(f"/workspaces/{other.id}/ask", json={"question": "Explain that", "previous_answer_id": answer["id"]}).status_code == 404
    assert client.patch(f'/workspaces/{other.id}/answers/{answer["id"]}/brief').status_code == 404
