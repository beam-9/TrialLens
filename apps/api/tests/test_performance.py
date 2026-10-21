"""Request profiling is observational: no answer text or behavior changes."""
import asyncio
import json
import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from triallens import main, performance
from triallens.conversation import _LOCAL_GENERATION_LOCK
from triallens.models import EvidenceSource, SourceType, Workspace
from triallens.rag import build_chunks, build_extractions
from triallens.store import JsonStore
from triallens.usage import UsageLedger


@pytest.fixture
def profiled(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("TRIALLENS_PERF_TELEMETRY", "1")
    monkeypatch.setenv("TRIALLENS_PERF_MODEL_DIGEST", "fixture-digest")
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    test_store = JsonStore(tmp_path / "store.json")
    workspace = test_store.create_workspace(Workspace(condition="PRIVATE_TOPIC", source_types=[SourceType.pubmed]))
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed, external_id="123", title="PRIVATE_TITLE", abstract="PRIVATE_SOURCE A trial reports outcomes over twelve weeks.")
    test_store.replace_workspace_evidence(workspace.id, [source], build_chunks([source]), build_extractions([source], workspace))
    monkeypatch.setattr(main, "store", test_store)
    caplog.set_level(logging.INFO, logger="triallens.performance")
    return TestClient(main.app, raise_server_exceptions=False), workspace, test_store


def logs(caplog):
    return [json.loads(record.message) for record in caplog.records if record.name == "triallens.performance"]


def fake_provider(monkeypatch, usage=None, error_at=None, error=None, invalid=False):
    calls = []
    def post(url, **kwargs):
        calls.append(kwargs)
        if len(calls) == error_at:
            raise error
        content = json.dumps({"paragraphs": ["PRIVATE_ANSWER The trial reports a comparison [PubMed:123]."], "cited_sources": ["PubMed:123"], "uncertainty": []})
        if invalid:
            content = "{}"
        return httpx.Response(200, request=httpx.Request("POST", url), json={"done": True, "message": {"content": content}, **(usage or {})})
    monkeypatch.setattr("triallens.conversation.httpx.post", post)
    return calls


def ask(profiled, question="PRIVATE_QUESTION What changed?", **payload):
    client, workspace, _ = profiled
    return client.post(f"/workspaces/{workspace.id}/ask", json={"question": question, **payload})


def test_opt_in_and_get_scope(profiled, monkeypatch, caplog):
    fake_provider(monkeypatch)
    client, workspace, _ = profiled
    client.get("/health")
    assert not logs(caplog)
    monkeypatch.delenv("TRIALLENS_PERF_TELEMETRY")
    assert ask(profiled).status_code == 200
    assert not logs(caplog)
    assert performance.current_trace() is None


def test_two_pass_metadata_privacy_and_missing_counts(profiled, monkeypatch, caplog):
    calls = fake_provider(monkeypatch, {"load_duration": 1000000, "eval_count": 0, "prompt_eval_count": 42, "eval_duration": 0})
    response = ask(profiled)
    assert response.status_code == 200 and response.json()["generation_mode"] == "conversational"
    trace, = logs(caplog)
    encoded = json.dumps(trace)
    assert all(secret not in encoded for secret in ["PRIVATE_TOPIC", "PRIVATE_TITLE", "PRIVATE_SOURCE", "PRIVATE_QUESTION", "PRIVATE_ANSWER", response.json()["id"]])
    assert trace["model_digest_or_version"] == "fixture-digest"
    assert trace["result_kind"] == "model_answer" and trace["revision_ran"] is True
    assert trace["revision_reason"] == "baseline_always"
    assert trace["source_count_selected"] == 1 and trace["context_char_count"] > 0
    assert trace["retrieved_passage_count"] > 0
    assert trace["serialization_ms"] >= 0 and trace["total_wall_ms"] > 0
    assert all(trace["phases_ms"][name] > 0 for name in performance.PHASES)
    assert [item["pass"] for item in trace["model_calls"]] == ["draft", "revision"]
    for item, call in zip(trace["model_calls"], calls):
        assert item["prompt_char_count"] == sum(len(m["content"]) for m in call["json"]["messages"][:item["message_count"]])
        assert item["load_duration_ns"] == 1000000 and item["eval_duration_ns"] == 0
        assert item["prompt_eval_count"] == 42 and item["eval_count"] == 0
        assert item["prompt_eval_duration_ns"] is None and item["total_duration_ns"] is None
    assert UsageLedger().status()["generated_answers"] == 1


@pytest.mark.parametrize("error,kind", [
    (httpx.ReadTimeout("SECRET_TIMEOUT"), "provider_timeout"),
    (httpx.ConnectError("SECRET_CONNECT"), "provider_connection_error"),
    (httpx.ReadError("SECRET_DISCONNECT"), "provider_disconnect"),
    (httpx.HTTPStatusError("SECRET_HTTP", request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"), response=httpx.Response(503)), "provider_http_error"),
])
@pytest.mark.parametrize("error_at", [1, 2])
def test_provider_failure_classified_and_lock_released(profiled, monkeypatch, caplog, error, kind, error_at):
    fake_provider(monkeypatch, error_at=error_at, error=error)
    response = ask(profiled)
    assert response.status_code == 200 and response.json()["generation_mode"] == "extractive"
    trace, = logs(caplog)
    assert trace["fallback_reason"] == trace["error_kind"] == kind
    assert trace["result_kind"] == "excerpt_fallback"
    assert trace["revision_ran"] is (error_at == 2)
    assert "SECRET" not in json.dumps(trace)
    assert UsageLedger().status()["generated_answers"] == 0
    assert _LOCAL_GENERATION_LOCK.acquire(blocking=False)
    _LOCAL_GENERATION_LOCK.release()


def test_validation_busy_and_guards_are_distinct(profiled, monkeypatch, caplog):
    fake_provider(monkeypatch, invalid=True)
    assert ask(profiled).json()["generation_mode"] == "extractive"
    assert logs(caplog)[-1]["fallback_reason"] == "validation_rejection"
    assert _LOCAL_GENERATION_LOCK.acquire(blocking=False)
    try:
        assert ask(profiled).status_code == 200
        assert logs(caplog)[-1]["busy_response"] is True
        assert logs(caplog)[-1]["result_kind"] == "busy"
        assert logs(caplog)[-1]["model_calls"] == []
    finally:
        _LOCAL_GENERATION_LOCK.release()
    assert ask(profiled, "Should I start this treatment?").status_code == 200
    assert logs(caplog)[-1]["result_kind"] == "treatment_guard"
    assert ask(profiled, "Is it better than the other one?").status_code == 200
    assert logs(caplog)[-1]["result_kind"] == "clarification"
    assert len({t["trace_id"] for t in logs(caplog)}) == 4
    assert _LOCAL_GENERATION_LOCK.acquire(blocking=False)
    _LOCAL_GENERATION_LOCK.release()


def test_request_rejection_and_storage_failure(profiled, monkeypatch, caplog):
    fake_provider(monkeypatch)
    assert ask(profiled, mode="document").status_code == 400
    assert logs(caplog)[-1]["result_kind"] == "request_rejected"
    def broken_store(answer):
        raise OSError("PRIVATE_DISK_PATH")
    monkeypatch.setattr(profiled[2], "save_answer", broken_store)
    assert ask(profiled).status_code == 500
    trace = logs(caplog)[-1]
    assert trace["error_kind"] == trace["result_kind"] == "storage_error"
    assert "PRIVATE_DISK_PATH" not in json.dumps(trace)


def test_bad_usage_values_stay_unknown_and_logging_cannot_fail_answer(profiled, monkeypatch, caplog):
    fake_provider(monkeypatch, {"eval_count": "42", "prompt_eval_count": True, "load_duration": -1, "eval_duration": float("inf")})
    assert ask(profiled).status_code == 200
    assert all(value is None for key, value in logs(caplog)[-1]["model_calls"][0].items() if key in {"eval_count", "prompt_eval_count", "load_duration_ns", "eval_duration_ns"})
    def broken_log(*args, **kwargs):
        raise OSError("logger unavailable")
    monkeypatch.setattr(performance.LOGGER, "info", broken_log)
    assert ask(profiled).status_code == 200
    assert performance.current_trace() is None


def test_client_disconnect_is_recorded(monkeypatch, caplog):
    monkeypatch.setenv("TRIALLENS_PERF_TELEMETRY", "1")
    caplog.set_level(logging.INFO, logger="triallens.performance")
    async def app(scope, receive, send):
        assert (await receive())["type"] == "http.disconnect"
    async def receive():
        return {"type": "http.disconnect"}
    async def send(message):
        pass
    asyncio.run(performance.AskPerformanceMiddleware(app)({"type": "http", "method": "POST", "path": "/workspaces/a/ask"}, receive, send))
    assert logs(caplog)[0]["error_kind"] == "client_disconnect"


def test_usage_failure_and_unexpected_exception_release_lock(profiled, monkeypatch, caplog):
    import sqlite3
    fake_provider(monkeypatch)
    def unavailable(self):
        raise sqlite3.OperationalError("SECRET_LEDGER")
    monkeypatch.setattr(UsageLedger, "local_answer", unavailable)
    assert ask(profiled).json()["generation_mode"] == "extractive"
    assert logs(caplog)[-1]["fallback_reason"] == "usage_tracking_error"
    assert _LOCAL_GENERATION_LOCK.acquire(blocking=False)
    _LOCAL_GENERATION_LOCK.release()
    def unexpected(*args, **kwargs):
        raise RuntimeError("SECRET_RUNTIME")
    monkeypatch.setattr("triallens.conversation.httpx.post", unexpected)
    assert ask(profiled).status_code == 500
    assert logs(caplog)[-1]["error_kind"] == "application_error"
    assert "SECRET" not in json.dumps(logs(caplog))
    assert _LOCAL_GENERATION_LOCK.acquire(blocking=False)
    _LOCAL_GENERATION_LOCK.release()


def test_storage_read_and_no_source_and_not_configured_paths(profiled, monkeypatch, caplog):
    client, workspace, test_store = profiled
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert ask(profiled).status_code == 200
    assert logs(caplog)[-1]["fallback_reason"] == "not_configured"
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    test_store.replace_workspace_evidence(workspace.id, [], [], [])
    assert ask(profiled).status_code == 200
    assert logs(caplog)[-1]["fallback_reason"] == "no_sources"
    def unreadable(workspace_id):
        raise OSError("SECRET_PATH")
    monkeypatch.setattr(test_store, "get_workspace", unreadable)
    assert ask(profiled).status_code == 500
    assert logs(caplog)[-1]["error_kind"] == "storage_error"
    assert "SECRET" not in json.dumps(logs(caplog))


def test_off_and_on_return_same_contract_and_model_requests(profiled, monkeypatch, caplog):
    calls = fake_provider(monkeypatch)
    monkeypatch.delenv("TRIALLENS_PERF_TELEMETRY", raising=False)
    off = ask(profiled).json()
    monkeypatch.setenv("TRIALLENS_PERF_TELEMETRY", "1")
    on = ask(profiled).json()
    # The persisted answer gets a fresh ID/date in both modes; all answer fields stay identical.
    for key in ("id", "created_at"):
        off.pop(key, None)
        on.pop(key, None)
    assert off == on
    assert len(calls) == 4
    assert calls[0] == calls[2] and calls[1] == calls[3]
    assert len(logs(caplog)) == 1


def test_flag_alone_emits_once_without_logging_configuration(monkeypatch, capsys):
    monkeypatch.setenv("TRIALLENS_PERF_TELEMETRY", "1")
    # Match native run.py/direct uvicorn: unrelated uvicorn handlers may exist,
    # while this logger inherits WARNING and has no handler of its own.
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", logging.WARNING)
    monkeypatch.setattr(performance.LOGGER, "handlers", [])
    monkeypatch.setattr(performance.LOGGER, "level", logging.NOTSET)
    monkeypatch.setattr(performance.LOGGER, "propagate", True)
    # logging caches effective levels, so reset through its public API.
    performance.LOGGER.setLevel(logging.NOTSET)
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})
    async def receive():
        return {"type": "http.request", "body": b""}
    async def send(message):
        pass
    asyncio.run(performance.AskPerformanceMiddleware(app)({"type": "http", "method": "POST", "path": "/workspaces/native/ask"}, receive, send))
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["http_status"] == 200
    assert root.level == logging.WARNING and root.handlers == []
    assert performance.LOGGER.level == logging.NOTSET and performance.LOGGER.handlers == []


def test_configured_info_logger_does_not_duplicate_stderr(profiled, monkeypatch, caplog, capsys):
    fake_provider(monkeypatch)
    assert ask(profiled).status_code == 200
    assert len(logs(caplog)) == 1
    assert capsys.readouterr().err == ""


def test_malformed_provider_metadata_cannot_reject_valid_answer(profiled, monkeypatch, caplog):
    fake_provider(monkeypatch, {"done_reason": ["invalid", "structured"], "eval_count": 10**400, "load_duration": {"bad": 1}})
    response = ask(profiled)
    assert response.status_code == 200 and response.json()["generation_mode"] == "conversational"
    trace, = logs(caplog)
    assert trace["result_kind"] == "model_answer"
    assert all(call["done_reason"] is None and call["eval_count"] is None and call["load_duration_ns"] is None for call in trace["model_calls"])
