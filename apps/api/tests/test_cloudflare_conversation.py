"""Hosted two-pass integration, with HTTP mocked: no paid or local inference."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from triallens import cloudflare, main
from triallens.conversation import ConversationService, GeneratedAnswer, INSTRUCTIONS, REVISION_INSTRUCTIONS, _LOCAL_GENERATION_LOCK, chat_configured, chat_model
from triallens.models import Answer, EvidenceSource, SourceType, Workspace
from triallens.usage import UsageLedger


@pytest.fixture
def context(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token-not-a-secret")
    monkeypatch.setenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "true")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("TRIALLENS_CHAT_MODEL", "gpt-4.1-mini")
    workspace = Workspace(condition="diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed, external_id="123", title="Adult trial", abstract="Adults receiving add-on treatment had HbA1c 0.5 percentage points lower than placebo at 12 weeks.")
    fallback = Answer(workspace_id=workspace.id, question="What changed?", short_answer="Extracted result", evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    return workspace, source, fallback


def provider(monkeypatch, *, reject_pass=None, bad_citation=False, copied=None):
    calls = []
    def post(url, **kwargs):
        assert url == "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/run/" + cloudflare.MODEL
        calls.append(kwargs["json"])
        if len(calls) == reject_pass:
            return httpx.Response(429, request=httpx.Request("POST", url), json={"secret": "must never surface"})
        marker = "PubMed:999" if bad_citation else "PubMed:123"
        wording = copied or ("The draft should be replaced" if len(calls) == 1 else "In adults, the add-on treatment lowered HbA1c by 0.5 percentage points versus placebo at 12 weeks")
        answer = {"paragraphs": [wording + f" [{marker}]."], "cited_sources": [marker], "uncertainty": []}
        return httpx.Response(200, request=httpx.Request("POST", url), json={"success": True, "result": {"response": answer, "usage": {"prompt_tokens": 100, "completion_tokens": 50}}})
    monkeypatch.setattr("triallens.cloudflare.httpx.post", post)
    return calls


def generate(context, question="Explain the result", history=None):
    workspace, source, fallback = context
    return ConversationService().generate(workspace, question, history or [], [source], fallback)


def test_two_pass_keeps_schema_history_citations_and_counts_once(monkeypatch, context):
    calls = provider(monkeypatch)
    previous = context[2].model_copy(update={"direct_answer": "Prior answer is not evidence", "question": "Earlier question"})
    answer = generate(context, history=[previous])
    assert chat_configured() and chat_model() == cloudflare.MODEL
    assert answer.generation_mode == "conversational"
    assert "draft" not in answer.direct_answer and "12 weeks" in answer.direct_answer
    assert "Cloudflare" in answer.generation_note
    assert answer.citations == ["PubMed:123"]
    assert len(calls) == 2
    assert calls[0]["messages"][0]["content"] == INSTRUCTIONS
    assert calls[1]["messages"][-1]["content"].startswith(REVISION_INSTRUCTIONS)
    payload = json.loads(calls[0]["messages"][1]["content"])
    assert payload["history"][0]["question"] == "Earlier question"
    assert payload["evidence"][0]["citation"] == "PubMed:123"
    assert calls[0]["response_format"]["json_schema"] == GeneratedAnswer.model_json_schema()
    status = UsageLedger().status()
    assert status["generated_answers"] == 1 and status["used_or_reserved_usd"] == 0
    assert cloudflare.quota_status()["requests"] == 2


@pytest.mark.parametrize("reject_pass", [1, 2])
def test_quota_failure_never_exposes_draft_or_falls_back_to_another_provider(monkeypatch, context, reject_pass):
    calls = provider(monkeypatch, reject_pass=reject_pass)
    answer = generate(context)
    assert answer.generation_mode == "extractive" and answer.short_answer == "Extracted result"
    assert "allowance" in answer.generation_note and "no local model or paid fallback" in answer.generation_note
    assert "secret" not in answer.generation_note
    assert len(calls) == reject_pass and UsageLedger().status()["generated_answers"] == 0
    assert _LOCAL_GENERATION_LOCK.acquire(False)
    _LOCAL_GENERATION_LOCK.release()


def test_unknown_citation_and_copy_guard_still_apply(monkeypatch, context):
    provider(monkeypatch, bad_citation=True)
    assert generate(context).generation_mode == "extractive"
    phrase = " ".join(f"unique{i}" for i in range(40))
    context[1].abstract = phrase
    provider(monkeypatch, copied=phrase)
    assert generate(context).generation_mode == "extractive"
    assert UsageLedger().status()["generated_answers"] == 0


def test_missing_config_guards_and_busy_never_invoke_inference(monkeypatch, context):
    def unexpected(*args, **kwargs):
        pytest.fail("No provider should be called")
    monkeypatch.setattr("triallens.cloudflare.httpx.post", unexpected)
    assert "Individual treatment decision" in generate(context, "Should I stop metformin?").generation_note
    assert "Clarification needed" in generate(context, "Compare the other one").generation_note
    assert _LOCAL_GENERATION_LOCK.acquire(False)
    try:
        assert "answering another question" in generate(context).generation_note
    finally:
        _LOCAL_GENERATION_LOCK.release()
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN")
    assert not chat_configured()
    assert "setup is incomplete" in generate(context).generation_note
    assert UsageLedger().status()["generated_answers"] == 0


def test_health_and_usage_never_expose_cloudflare_credentials(context):
    client = TestClient(main.app)
    health = client.get("/health").json()
    usage = client.get("/usage").json()
    assert health["provider"] == usage["provider"] == "cloudflare"
    assert health["model"] == cloudflare.MODEL
    assert "test-token-not-a-secret" not in json.dumps([health, usage])
    assert "a" * 32 not in json.dumps([health, usage])
