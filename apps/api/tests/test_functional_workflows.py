"""API audit workflows: isolated persistence, mocked ingestion, no inference."""
import pytest
from fastapi.testclient import TestClient

from triallens import main
from triallens.models import EvidenceSource, SourceType
from triallens.store import JsonStore


@pytest.fixture
def workflow(monkeypatch, tmp_path):
    path = tmp_path / "workspace.json"
    monkeypatch.setattr(main, "store", JsonStore(path))
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    def no_network(*args, **kwargs):
        pytest.fail("Functional fixture must never invoke inference or external HTTP")
    monkeypatch.setattr("triallens.conversation.httpx.post", no_network)
    client = TestClient(main.app)
    response = client.post("/workspaces", json={"condition": "diabetes", "intervention": "metformin", "source_types": ["pubmed", "clinical_trials"]})
    assert response.status_code == 200
    workspace_id = response.json()["id"]
    sources = [EvidenceSource(workspace_id=workspace_id, source_type=kind, external_id=f"audit-{index}", title="Metformin diabetes trial", abstract="Adults received metformin or placebo. At 12 weeks HbA1c decreased by 0.5 percentage points compared with placebo.") for index, kind in enumerate((SourceType.pubmed, SourceType.clinical_trials))]
    async def fetch(workspace, diagnostics):
        diagnostics.update({"pubmed": "available", "clinical_trials": "available"})
        return sources
    monkeypatch.setattr(main, "fetch_sources", fetch)
    base = f"/workspaces/{workspace_id}"
    assert client.post(base + "/ingest").status_code == 200
    return client, base, path, sources


def test_history_review_brief_and_retrieval_survive_store_restart(workflow, monkeypatch):
    client, base, path, sources = workflow
    first = client.post(base + "/ask", json={"question": "What does metformin research report?", "source_types": ["pubmed"]})
    assert first.status_code == 200
    answer = first.json()
    assert answer["generation_mode"] == "extractive"
    assert answer["retrieved_chunks"] and all(row["source_type"] == "pubmed" for row in answer["retrieved_chunks"])
    assert all(citation.startswith("PubMed:") for citation in answer["citations"])
    follow = client.post(base + "/ask", json={"question": "Explain that more simply", "source_types": ["pubmed"], "previous_answer_id": answer["id"]})
    assert follow.status_code == 200
    assert client.patch(base + f'/answers/{answer["id"]}/brief?saved=true').status_code == 200
    row = client.get(base + "/extractions").json()[0]
    correction = "Reviewer confirmed: 0.5 percentage points versus placebo at 12 weeks."
    assert client.patch(base + f'/extractions/{row["id"]}', json={"review_status": "reviewed", "outcome_result": correction}).status_code == 200
    monkeypatch.setattr(main, "store", JsonStore(path))
    persisted = client.get(base + "/answers").json()
    assert {item["id"] for item in persisted} == {answer["id"], follow.json()["id"]}
    assert client.get(base + f'/retrievals/{answer["id"]}').json()["retrieved_chunks"] == answer["retrieved_chunks"]
    brief = client.get(base + "/brief").json()
    assert [item["id"] for item in brief["saved_answers"]] == [answer["id"]]
    assert brief["review_summary"]["reviewed"] == 1
    assert next(item for item in client.get(base + "/extractions").json() if item["id"] == row["id"])["outcome_result"] == correction
    assert client.patch(base + f'/answers/{answer["id"]}/brief?saved=false').status_code == 200
    assert client.get(base + "/brief").json()["saved_answers"] == []


def test_document_scope_filters_and_negative_paths(workflow):
    client, base, path, sources = workflow
    doc = client.post(base + "/ask", json={"question": "What did this trial report?", "mode": "document", "source_id": sources[0].id})
    assert doc.status_code == 200
    assert all(row["source_id"] == sources[0].id for row in doc.json()["retrieved_chunks"])
    assert client.post(base + "/ask", json={"question": "Explain that", "previous_answer_id": doc.json()["id"]}).status_code == 400
    assert client.post(base + "/ask", json={"question": "What did this trial report?", "mode": "document", "source_id": sources[0].id, "source_types": ["clinical_trials"]}).status_code == 404
    assert client.post(base + "/ask", json={"question": "No", "source_types": ["pubmed"]}).status_code == 422
    assert client.patch(base + "/extractions/missing", json={"review_status": "reviewed"}).status_code == 404
    other = client.post("/workspaces", json={"condition": "migraine", "source_types": []}).json()["id"]
    assert client.get(f'/workspaces/{other}/retrievals/{doc.json()["id"]}').status_code == 404
    assert client.post(f'/workspaces/{other}/ask', json={"question": "Explain that", "mode": "document", "source_id": sources[0].id}).status_code == 404
    empty = client.post(base + "/ask", json={"question": "What changed?", "source_types": []})
    assert empty.status_code == 200 and empty.json()["retrieved_chunks"] == [] and empty.json()["citations"] == []


def test_refresh_keeps_historical_provenance_and_warns_brief_about_replaced_sources(workflow, monkeypatch):
    client, base, path, sources = workflow
    answer = client.post(base + "/ask", json={"question": "What does metformin research report?", "source_types": ["pubmed"]}).json()
    assert answer["citations"]
    assert client.patch(base + f'/answers/{answer["id"]}/brief?saved=true').status_code == 200
    replacement = sources[0].model_copy(update={"id": "replacement-source", "external_id": "replacement-record"})
    async def refreshed(workspace, diagnostics):
        diagnostics.update({"pubmed": "available", "clinical_trials": "available"})
        return [replacement]
    monkeypatch.setattr(main, "fetch_sources", refreshed)
    assert client.post(base + "/ingest").status_code == 200
    monkeypatch.setattr(main, "store", JsonStore(path))
    retained = client.get(base + f'/retrievals/{answer["id"]}').json()
    assert retained["retrieved_chunks"] == answer["retrieved_chunks"] and retained["citations"] == answer["citations"]
    brief = client.get(base + "/brief").json()
    assert brief["saved_answers"][0]["id"] == answer["id"]
    assert any("earlier source collection" in gap for gap in brief["evidence_gaps"])


def test_reextract_preserves_manual_review_and_corrections(workflow):
    client, base, path, sources = workflow
    row = client.get(base + "/extractions").json()[0]
    correction = "Confirmed by reviewer against source: 0.5 percentage points at 12 weeks."
    assert client.patch(base + f'/extractions/{row["id"]}', json={"review_status": "reviewed", "outcome_result": correction}).status_code == 200
    assert client.post(base + "/extract").status_code == 200
    regenerated = next(item for item in client.get(base + "/extractions").json() if item["source_id"] == row["source_id"])
    assert regenerated["review_status"] == "reviewed"
    assert regenerated["outcome_result"] == correction


def test_reextract_keeps_unreviewed_edits_and_regenerates_derived_details(workflow):
    client, base, path, sources = workflow
    row = client.get(base + "/extractions").json()[0]
    assert client.patch(base + f'/extractions/{row["id"]}', json={"outcome_result": "Reviewer says this is inconclusive."}).status_code == 200
    # Simulate an older persisted row lacking generated detail fields.
    store = JsonStore(path)
    rows = store.list_extractions(row["workspace_id"])
    rows = [item.model_copy(update={"source_understanding": [], "source_overview": ""}) if item.id == row["id"] else item for item in rows]
    store.replace_workspace_extractions(row["workspace_id"], rows)
    assert client.post(base + "/extract").status_code == 200
    rebuilt = next(item for item in client.get(base + "/extractions").json() if item["id"] == row["id"])
    assert rebuilt["review_status"] == "unreviewed" and rebuilt["outcome_result"] == "Reviewer says this is inconclusive."
    assert rebuilt["source_overview"] and rebuilt["has_quantitative_result"] is False


def test_partial_refresh_preserves_unavailable_source_cohort(workflow, monkeypatch):
    client, base, path, sources = workflow
    async def partial(workspace, diagnostics):
        diagnostics.update({"pubmed": "available", "clinical_trials": "unavailable"})
        return [sources[0]]
    monkeypatch.setattr(main, "fetch_sources", partial)
    response = client.post(base + "/ingest")
    assert response.status_code == 200 and response.json()["status"] == "partial"
    assert {source["id"] for source in client.get(base + "/sources").json()} == {source.id for source in sources}


def test_workspace_rejects_whitespace_only_topic(workflow):
    client, base, path, sources = workflow
    assert client.post("/workspaces", json={"condition": "   ", "source_types": []}).status_code == 422


@pytest.mark.parametrize("first_scope,second_scope", [(None, []), ([], None)])
def test_all_sources_and_no_sources_are_different_conversation_scopes(workflow, first_scope, second_scope):
    client, base, path, sources = workflow
    first = client.post(base + "/ask", json={"question": "What changed?", "source_types": first_scope})
    assert first.status_code == 200
    follow = client.post(base + "/ask", json={"question": "Explain that", "source_types": second_scope, "previous_answer_id": first.json()["id"]})
    assert follow.status_code == 400
