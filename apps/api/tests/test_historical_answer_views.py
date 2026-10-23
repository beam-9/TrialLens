"""Historical generation provenance must not be invented from current evidence."""
import json

import pytest
from fastapi.testclient import TestClient

from triallens import main
from triallens.answer_views import HISTORICAL_PROVENANCE_NOTE, answer_read_view
from triallens.models import Answer, AnswerTraceItem, EvidenceBrief, RetrievedChunk, SourceType, Workspace
from triallens.store import JsonStore


def historical_answer(workspace_id):
    return Answer(
        workspace_id=workspace_id, question="What does the evidence show?",
        generation_mode="conversational", generation_note="Generated from indexed sources.",
        short_answer="The indexed excerpt is insufficient.", direct_answer="The indexed excerpt is insufficient.",
        citations=[], uncertainty=["The available excerpt does not establish benefit."],
        retrieved_chunks=[RetrievedChunk(chunk_id="old-chunk", source_id="removed-source",
            source_type=SourceType.pubmed, citation="PubMed:old", text="Original historical passage.", score=0.7)],
        source_readouts=["CITED · PubMed:old · Strong evidence"],
        evidence=["Extractive claim"], supporting_evidence=["Extractive support"],
        evidence_synthesis=["Benefit confirmed"], evidence_map=["Direct support"],
        reasoning_summary=["The answer is supported by one cited trial."],
        evidence_quality=["High confidence"], facet_coverage=["Benefit covered"],
        safety_limitations=["Extractive judgment"], limitations=["Old conclusion"],
        answer_trace=[AnswerTraceItem(label="Support", value="High")], saved_to_brief=True,
    )


def assert_historical_view(view, original):
    for field in ("id", "workspace_id", "question", "short_answer", "direct_answer", "citations", "retrieved_chunks", "uncertainty", "created_at"):
        assert view[field] == original[field]
    for field in ("source_readouts", "evidence", "supporting_evidence", "evidence_synthesis", "evidence_map", "facet_coverage", "safety_limitations"):
        assert view[field] == []
    assert HISTORICAL_PROVENANCE_NOTE in view["generation_note"]
    assert view["answer_trace"][0]["value"] == "Not reconstructed"
    assert "High confidence" not in json.dumps(view)
    assert "CITED ·" not in json.dumps(view)


def test_history_endpoints_and_brief_read_views_preserve_stored_record(monkeypatch, tmp_path):
    store = JsonStore(tmp_path / "store.json")
    workspace = store.create_workspace(Workspace(condition="diabetes", source_types=[]))
    answer = historical_answer(workspace.id)
    original = answer.model_dump(mode="json")
    store.save_answer(answer)
    monkeypatch.setattr(main, "store", store)
    client = TestClient(main.app)
    base = f"/workspaces/{workspace.id}"
    before_read = store.path.read_bytes()
    assert_historical_view(client.get(base + "/answers").json()[0], original)
    assert_historical_view(client.get(base + f"/retrievals/{answer.id}").json(), original)
    # There are deliberately no current sources: no contemporary lookup can
    # reconstruct which content an old generation actually received.
    brief = client.get(base + "/brief").json()
    assert_historical_view(brief["saved_answers"][0], original)
    assert brief["key_claims"] == [answer.direct_answer]
    assert store.path.read_bytes() == before_read
    assert_historical_view(client.patch(base + f"/answers/{answer.id}/brief?saved=false").json(), original)
    raw = json.loads(store.path.read_text())["answers"][answer.id]
    assert raw == {**original, "saved_to_brief": False}
    assert client.get(base + "/brief").json()["saved_answers"] == []
    restored = client.patch(base + f"/answers/{answer.id}/brief?saved=true").json()
    assert_historical_view(restored, original)
    assert json.loads(store.path.read_text())["answers"][answer.id] == original
    other = store.create_workspace(Workspace(condition="migraine", source_types=[]))
    assert client.patch(f"/workspaces/{other.id}/answers/{answer.id}/brief").status_code == 404
    assert store.get_answer(answer.id).saved_to_brief is True


def test_cached_brief_also_projects_historical_saved_answers(tmp_path):
    store = JsonStore(tmp_path / "store.json")
    answer = historical_answer("workspace")
    brief = EvidenceBrief(workspace_id="workspace", title="Saved brief", overview="Research notes",
        source_summary={}, key_claims=[answer.direct_answer], evidence_gaps=[], safety_note="Research only",
        citations=[], saved_answers=[answer])
    store.save_brief(brief)
    before_read = store.path.read_bytes()
    assert_historical_view(store.get_brief("workspace").saved_answers[0].model_dump(mode="json"), answer.model_dump(mode="json"))
    assert store.path.read_bytes() == before_read


@pytest.mark.parametrize("mode", ["extractive", "conversational"])
def test_current_reconciled_provenance_and_extractive_records_are_unchanged(mode):
    answer = historical_answer("workspace")
    answer.generation_mode = mode
    if mode == "conversational":
        answer.answer_trace = [AnswerTraceItem(label="Generation context", value="One source record"),
                               AnswerTraceItem(label="Final attribution", value="No citations")]
    assert answer_read_view(answer).model_dump() == answer.model_dump()


def test_historical_projection_is_idempotent_without_mutating_input():
    answer = historical_answer("workspace")
    before = answer.model_dump()
    view = answer_read_view(answer)
    assert answer.model_dump() == before
    assert answer_read_view(view).model_dump() == view.model_dump()


@pytest.mark.parametrize("question", ["Should I take this medicine?", "Is it better than the other treatment?"])
def test_current_treatment_and_clarification_guards_are_not_historical(question, monkeypatch, tmp_path):
    from triallens.conversation import ConversationService
    from triallens.models import EvidenceSource

    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-not-a-real-token")
    monkeypatch.setenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "true")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr("triallens.conversation.httpx.post", lambda *args, **kwargs: pytest.fail("Guard must not call inference"))
    workspace = Workspace(condition="diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    fallback = historical_answer(workspace.id)
    fallback.generation_mode = "extractive"
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
        external_id="123", title="Diabetes study", abstract="Adults received metformin.")
    answer = ConversationService().generate(workspace, question, [], [source], fallback)
    assert any(item.label == "Response method" and item.value == "No model generation" for item in answer.answer_trace)
    view = answer_read_view(answer)
    assert view.model_dump() == answer.model_dump()
    assert HISTORICAL_PROVENANCE_NOTE not in view.generation_note
