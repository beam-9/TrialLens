"""Product scoping at the API boundary, using real retrieval and mocked inference."""
import json

import pytest
from fastapi.testclient import TestClient

from triallens import cloudflare, main
from triallens.models import EvidenceSource, SourceType, Workspace
from triallens.rag import build_chunks, build_extractions
from triallens.store import JsonStore


@pytest.fixture
def scoped_api(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "fixture-token")
    monkeypatch.setenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "true")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    def no_http(*args, **kwargs):
        pytest.fail("Scope tests must never call HTTP or local inference")
    monkeypatch.setattr("triallens.conversation.httpx.post", no_http)
    calls = []
    def unavailable(messages, schema):
        calls.append(json.loads(messages[1]["content"]))
        raise cloudflare.CloudflareUnavailable("quota")
    monkeypatch.setattr(cloudflare, "completion", unavailable)
    store = JsonStore(tmp_path / "workspace.json")
    workspace = store.create_workspace(Workspace(condition="type 2 diabetes", intervention="metformin", source_types=[SourceType.fda_label, SourceType.pubmed]))
    standalone = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.fda_label, external_id="standalone", title="FDA label: METFORMIN HYDROCHLORIDE", abstract="Metformin is indicated for glycemic control in adults with type 2 diabetes. Metformin adverse reactions include diarrhea and nausea.", metadata={"substance_names": ["METFORMIN HYDROCHLORIDE"]})
    combo = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.fda_label, external_id="combo", title="FDA label: ZITUVIMET, ZITUVIMET XR", abstract="ZITUVIMET is a combination of sitagliptin and metformin for type 2 diabetes. ZITUVIMET has not been studied in patients with a history of pancreatitis.", metadata={"substance_names": ["SITAGLIPTIN", "METFORMIN HYDROCHLORIDE"], "brand_names": ["ZITUVIMET", "ZITUVIMET XR"], "sections": {"Warnings and precautions": "ZITUVIMET (sitagliptin and metformin) safety: pancreatitis has been reported with sitagliptin. ZITUVIMET has not been studied in patients with a history of pancreatitis."}})
    trial = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed, external_id="trial", title="Metformin diabetes benefits", abstract="In adults with type 2 diabetes, metformin lowered HbA1c by 0.5 percentage points compared with placebo at 12 weeks.")
    sources = [combo, standalone, trial]
    store.replace_workspace_evidence(workspace.id, sources, build_chunks(sources), build_extractions(sources, workspace))
    monkeypatch.setattr(main, "store", store)
    return TestClient(main.app), f"/workspaces/{workspace.id}", combo, calls


@pytest.mark.parametrize("failure", ["quota", "revision_quota", "incomplete", "unconfigured"])
def test_broad_fallback_is_built_without_combination_evidence(scoped_api, monkeypatch, failure):
    client, base, combo, calls = scoped_api
    if failure == "revision_quota":
        def reject_revision(messages, schema):
            calls.append(json.loads(messages[1]["content"]))
            if len(calls) == 2:
                raise cloudflare.CloudflareUnavailable("quota")
            return json.dumps({"paragraphs": ["Draft must never be exposed"], "cited_sources": [], "uncertainty": []})
        monkeypatch.setattr(cloudflare, "completion", reject_revision)
    elif failure == "incomplete":
        def incomplete(*args, **kwargs):
            raise ValueError("Incomplete generation")
        monkeypatch.setattr(cloudflare, "completion", incomplete)
    elif failure == "unconfigured":
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN")
    response = client.post(base + "/ask", json={"question": "What are the benefits and limitations of metformin?"})
    assert response.status_code == 200
    answer = response.json()
    assert answer["generation_mode"] == "extractive"
    assert answer["citations"] and answer["retrieved_chunks"]
    # Inspect the entire saved answer, including readouts, safety prose, and trace.
    serialized = json.dumps(answer).lower()
    assert "zituvimet" not in serialized
    assert "pancreatitis" not in serialized
    assert "openfda label:combo" not in serialized
    assert all(chunk["source_id"] != combo.id for chunk in answer["retrieved_chunks"])
    assert "Combination-product labels were excluded from this single-ingredient summary." in answer["generation_note"]
    assert client.get(base + f'/retrievals/{answer["id"]}').json() == answer
    assert "draft must never be exposed" not in serialized
    if failure in {"quota", "revision_quota"}:
        assert "allowance" in answer["generation_note"]
        assert all(record["citation"] != "openFDA label:combo" for record in calls[0]["evidence"])


@pytest.mark.parametrize("selection", ["document", "named", "combination", "history"])
def test_explicit_combination_scope_survives_quota_fallback(scoped_api, selection):
    client, base, combo, calls = scoped_api
    payload = {"question": "What are the benefits and limitations of ZITUVIMET?"}
    if selection == "document":
        payload = {"question": "What does this document say about safety?", "mode": "document", "source_id": combo.id}
    elif selection == "combination":
        payload = {"question": "What are the benefits and limitations of the metformin combination?"}
    elif selection == "history":
        first = client.post(base + "/ask", json=payload)
        assert first.status_code == 200
        payload = {"question": "Explain that more simply", "previous_answer_id": first.json()["id"]}
    response = client.post(base + "/ask", json=payload)
    assert response.status_code == 200
    answer = response.json()
    assert answer["generation_mode"] == "extractive"
    assert "openFDA label:combo" in answer["citations"]
    assert any(chunk["source_id"] == combo.id for chunk in answer["retrieved_chunks"])
    assert "pancreatitis" in json.dumps(answer).lower()
    assert "Combination-product labels were excluded" not in answer["generation_note"]
    assert any(record["citation"] == "openFDA label:combo" for record in calls[-1]["evidence"])
    if selection == "document":
        assert all(chunk["source_id"] == combo.id for chunk in answer["retrieved_chunks"])


def test_source_type_filter_remains_authoritative(scoped_api):
    client, base, combo, calls = scoped_api
    response = client.post(base + "/ask", json={"question": "What does ZITUVIMET's label say about safety?", "source_types": ["pubmed"]})
    assert response.status_code == 200
    answer = response.json()
    assert all(chunk["source_type"] == "pubmed" for chunk in answer["retrieved_chunks"])
    assert all(citation.startswith("PubMed:") for citation in answer["citations"])
    assert "Combination-product labels were excluded" not in answer["generation_note"]


def test_historical_label_without_substance_metadata_is_still_scoped(scoped_api):
    client, base, combo, calls = scoped_api
    workspace_id = combo.workspace_id
    sources = main.store.list_sources(workspace_id)
    sources = [source.model_copy(update={"metadata": {}}) if source.id == combo.id else source for source in sources]
    workspace = main.store.get_workspace(workspace_id)
    main.store.replace_workspace_evidence(workspace_id, sources, build_chunks(sources), build_extractions(sources, workspace))
    answer = client.post(base + "/ask", json={"question": "What are metformin's benefits and limitations?"}).json()
    assert answer["citations"] and answer["retrieved_chunks"]
    assert "zituvimet" not in json.dumps(answer).lower()
    assert "pancreatitis" not in json.dumps(answer).lower()
    assert "Combination-product labels were excluded" in answer["generation_note"]


def test_combination_is_retained_when_no_standalone_label_exists(scoped_api):
    client, base, combo, calls = scoped_api
    workspace_id = combo.workspace_id
    sources = [source for source in main.store.list_sources(workspace_id) if source.external_id != "standalone"]
    workspace = main.store.get_workspace(workspace_id)
    main.store.replace_workspace_evidence(workspace_id, sources, build_chunks(sources), build_extractions(sources, workspace))
    answer = client.post(base + "/ask", json={"question": "What are metformin's benefits and limitations?"}).json()
    assert any(chunk["source_id"] == combo.id for chunk in answer["retrieved_chunks"])
    assert "Combination-product labels were excluded" not in answer["generation_note"]
    assert any(record["citation"] == "openFDA label:combo" for record in calls[0]["evidence"])
