import json

import httpx
import pytest

from triallens.conversation import ConversationService, retrieval_question
from triallens.models import Answer, EvidenceSource, SourceType, Workspace


@pytest.fixture
def context(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("TRIALLENS_CHAT_MODEL", "gpt-4.1-mini")
    workspace = Workspace(condition="diabetes", source_types=[SourceType.pubmed])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
                            external_id="123", title="Trial results", abstract="The intervention reduced HbA1c by 0.5 percentage points versus placebo at 12 weeks.")
    fallback = Answer(workspace_id=workspace.id, question="What changed?", short_answer="Extracted result",
                      evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    return workspace, source, fallback


def mock_generation(monkeypatch, output, status="completed"):
    captured = []
    def post(url, **kwargs):
        captured.append(kwargs["json"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={"status": status,
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(output)}]}]})
    monkeypatch.setattr("triallens.conversation.httpx.post", post)
    return captured


def test_conversational_generation_preserves_history_and_provenance(monkeypatch, context):
    workspace, source, fallback = context
    captured = mock_generation(monkeypatch, {"paragraphs": ["At 12 weeks, HbA1c was 0.5 percentage points lower than with placebo [PubMed:123]."], "cited_sources": ["PubMed:123"], "uncertainty": ["Longer-term outcomes are not available."]})
    result = ConversationService().generate(workspace, "Explain that result", [fallback], [source], fallback)
    assert result.generation_mode == "conversational"
    assert result.citations == ["PubMed:123"]
    assert captured[0]["store"] is False
    payload = json.loads(captured[0]["input"])
    assert payload["history"][0]["question"] == "What changed?"
    assert payload["evidence"][0]["citation"] == "PubMed:123"


@pytest.mark.parametrize("output,status", [
    ({"paragraphs": ["It works [PubMed:999]."], "cited_sources": ["PubMed:999"], "uncertainty": []}, "completed"),
    ({"paragraphs": ["It works."], "cited_sources": ["PubMed:123"], "uncertainty": []}, "completed"),
    ({"paragraphs": ["It works."], "cited_sources": [], "uncertainty": []}, "completed"),
    ({"paragraphs": ["It works [PubMed:123]."], "cited_sources": ["PubMed:123"], "uncertainty": []}, "incomplete"),
    ({"paragraphs": ["   "], "cited_sources": [], "uncertainty": []}, "completed"),
])
def test_invalid_generation_falls_back(monkeypatch, context, output, status):
    workspace, source, fallback = context
    mock_generation(monkeypatch, output, status)
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert result.generation_mode == "extractive"
    assert result.short_answer == "Extracted result"
    assert "failed validation" in result.generation_note


def test_long_copied_passage_rejected(monkeypatch, context):
    workspace, source, fallback = context
    source.abstract = " ".join(f"word{i}" for i in range(35))
    mock_generation(monkeypatch, {"paragraphs": [source.abstract + " [PubMed:123]"], "cited_sources": ["PubMed:123"], "uncertainty": []})
    assert ConversationService().generate(workspace, "What changed?", [], [source], fallback).generation_mode == "extractive"


def test_missing_config_does_not_call_provider(monkeypatch, context):
    workspace, source, fallback = context
    monkeypatch.delenv("OPENAI_API_KEY")
    def unexpected(*args, **kwargs):
        pytest.fail("Provider must not be called without configuration")
    monkeypatch.setattr("triallens.conversation.httpx.post", unexpected)
    assert "not connected" in ConversationService().generate(workspace, "What changed?", [], [source], fallback).generation_note


def test_timeout_falls_back(monkeypatch, context):
    workspace, source, fallback = context
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("test timeout")
    monkeypatch.setattr("triallens.conversation.httpx.post", timeout)
    assert ConversationService().generate(workspace, "What changed?", [], [source], fallback).generation_mode == "extractive"


def test_follow_up_retrieval_keeps_original_referent(context):
    _, _, first = context
    first.question = "What is the HbA1c result?"
    second = first.model_copy(update={"question": "Explain that more simply"})
    query = retrieval_question("Why is that important?", [first, second])
    assert "HbA1c" in query
    assert first.short_answer not in query
    assert retrieval_question("What safety concerns exist?", [first]) == "What safety concerns exist?"


def test_budget_rejection_never_calls_provider(monkeypatch, context):
    from triallens.usage import BudgetUnavailable
    workspace, source, fallback = context
    def reject(*args):
        raise BudgetUnavailable("Budget reached")
    monkeypatch.setattr("triallens.conversation.UsageLedger.reserve", reject)
    def unexpected(*args, **kwargs):
        pytest.fail("No request should be sent after budget rejection")
    monkeypatch.setattr("triallens.conversation.httpx.post", unexpected)
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert result.generation_note == "Budget reached"


def test_credit_exhaustion_releases_reservation(monkeypatch, context):
    from triallens.usage import UsageLedger
    workspace, source, fallback = context
    def reject(url, **kwargs):
        return httpx.Response(429, request=httpx.Request("POST", url), json={"error": {"code": "credit_balance_exhausted"}})
    monkeypatch.setattr("triallens.conversation.httpx.post", reject)
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert "credits are exhausted" in result.generation_note
    status = UsageLedger().status()
    assert status["used_or_reserved_usd"] == 0
    assert status["generated_answers"] == 0
    assert status["pending_requests"] == 0


def test_local_generation_needs_no_key_and_never_sends_auth(monkeypatch, context):
    from triallens.usage import UsageLedger
    workspace, source, fallback = context
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    monkeypatch.delenv("OPENAI_API_KEY")
    requests = []
    def local(url, **kwargs):
        requests.append(url)
        assert url == "http://127.0.0.1:11434/api/chat"
        assert "headers" not in kwargs
        assert kwargs["json"]["think"] is False
        assert kwargs["json"]["format"]["type"] == "object"
        content = json.dumps({"paragraphs": ["HbA1c was lower at 12 weeks with the intervention [PubMed:123]."], "cited_sources": ["PubMed:123"], "uncertainty": []})
        return httpx.Response(200, request=httpx.Request("POST", url), json={"done": True, "done_reason": "stop", "message": {"content": content}})
    monkeypatch.setattr("triallens.conversation.httpx.post", local)
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert result.generation_mode == "conversational"
    assert len(requests) == 1
    assert UsageLedger().status()["used_or_reserved_usd"] == 0
    assert UsageLedger().status()["generated_answers"] == 1


def test_local_failure_never_falls_back_to_paid_provider(monkeypatch, context):
    workspace, source, fallback = context
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    requests = []
    def offline(url, **kwargs):
        requests.append(url)
        raise httpx.ConnectError("Ollama is stopped")
    monkeypatch.setattr("triallens.conversation.httpx.post", offline)
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert result.generation_mode == "extractive"
    assert "local model" in result.generation_note
    assert requests == ["http://127.0.0.1:11434/api/chat"]


def test_cloud_tag_is_rejected_in_local_mode(monkeypatch, context):
    from triallens.conversation import chat_configured
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    monkeypatch.setenv("TRIALLENS_LOCAL_MODEL", "some-model:cloud")
    assert not chat_configured()
