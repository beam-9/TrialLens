"""Research input validation must run after trimming, before writes/inference."""
import pytest
from fastapi.testclient import TestClient

from triallens import main
from triallens.models import Workspace
from triallens.store import JsonStore


@pytest.fixture
def client(monkeypatch, tmp_path):
    store = JsonStore(tmp_path / "data.json")
    monkeypatch.setattr(main, "store", store)
    return TestClient(main.app), store


@pytest.mark.parametrize("condition", ["  ", " a ", "\t\n"])
def test_blank_or_too_short_trimmed_topic_does_not_create_workspace(client, condition):
    api, store = client
    assert api.post("/workspaces", json={"condition": condition}).status_code == 422
    assert store.list_workspaces() == []


def test_trimmed_valid_topic_and_empty_optional_intervention(client):
    api, _ = client
    result = api.post("/workspaces", json={"condition": "  diabetes  ", "intervention": "  "})
    assert result.status_code == 200
    assert result.json()["condition"] == "diabetes"
    assert result.json()["intervention"] is None


@pytest.mark.parametrize("question", ["   ", "  a  ", "\t\n\t"])
def test_whitespace_question_rejected_before_generation(client, monkeypatch, question):
    api, store = client
    workspace = store.create_workspace(Workspace(condition="diabetes", source_types=[]))
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid question reached generation")
    monkeypatch.setattr(main.conversation_service, "generate", unexpected)
    assert api.post(f"/workspaces/{workspace.id}/ask", json={"question": question}).status_code == 422
    assert store.list_answers(workspace.id) == []
