"""Workers AI adapter tests use fake HTTP only; no model or credentials required."""
import importlib
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from triallens import cloudflare as cf


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token-never-real")
    monkeypatch.setenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "true")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(cf.httpx, "post", lambda *args, **kwargs: pytest.fail("Unexpected HTTP call"))


def response(result=None, status=200, **extra):
    return httpx.Response(status, json={"success": True, "errors": [], "result": result or {"response": '{"answer":"Supported [S1]"}', "usage": {"prompt_tokens": 100, "completion_tokens": 20}}, **extra})


def call():
    return cf.completion([{"role": "user", "content": "Private question"}], {"type": "object", "properties": {"answer": {"type": "string"}}})


@pytest.mark.parametrize("duplicate", [None, {"answer": "Supported [S1]"}, '{ "answer": "Supported [S1]" }'])
def test_completed_chat_choice_returns_only_final_json_and_settles_usage(monkeypatch, duplicate):
    final = '{"answer":"Supported [S1]"}'
    result = {"choices": [{"index": 0, "finish_reason": "stop", "message": {
        "role": "assistant", "content": final, "reasoning_content": "Do not expose or log this field"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
    if duplicate is not None:
        result["response"] = duplicate
    monkeypatch.setattr(cf.httpx, "post", lambda *a, **k: response(result))
    assert call() == final
    assert cf.quota_status()["pending_requests"] == 0


@pytest.mark.parametrize("choice", [
    {"index": 0, "finish_reason": "length", "message": {"role": "assistant", "content": '{"answer":"partial"}'}},
    {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": None, "reasoning_content": "No final"}},
    {"index": 0, "finish_reason": "stop", "message": {"role": "tool", "content": '{"answer":"not assistant"}'}},
    {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{}', "refusal": "declined"}},
    {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{}', "tool_calls": [{"id": "call"}]}},
    {"index": 1, "finish_reason": "stop", "message": {"role": "assistant", "content": '{}'}},
    {"index": False, "finish_reason": "stop", "message": {"role": "assistant", "content": '{}'}},
])
def test_chat_choice_rejects_incomplete_nonfinal_and_refused_outputs(monkeypatch, choice):
    monkeypatch.setattr(cf.httpx, "post", lambda *a, **k: response({"choices": [choice], "usage": {"prompt_tokens": 100, "completion_tokens": 20}}))
    with pytest.raises(cf.CloudflareUnavailable, match="invalidresponse"):
        call()
    assert cf.quota_status()["pending_requests"] == 1


def test_chat_choice_rejects_ambiguous_multiple_outputs(monkeypatch):
    choice = {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": '{}'}}
    for result in ({"choices": [choice, choice]}, {"choices": [choice], "response": '{"different":true}'}):
        monkeypatch.setattr(cf.httpx, "post", lambda *a, **k: response(result))
        with pytest.raises(cf.CloudflareUnavailable, match="invalidresponse"):
            call()


def test_glm_conversation_profile_uses_named_schema_and_disables_reasoning(monkeypatch):
    monkeypatch.setattr(cf, "MODEL", "@cf/zai-org/glm-4.7-flash")
    def post(url, **kwargs):
        assert kwargs["json"]["chat_template_kwargs"] == {"enable_thinking": False}
        envelope = kwargs["json"]["response_format"]["json_schema"]
        assert envelope["name"] == "triallens_answer" and envelope["strict"] is True
        assert envelope["schema"]["type"] == "object"
        assert kwargs["json"]["max_tokens"] == cf.MAX_OUTPUT_TOKENS
        return response()
    monkeypatch.setattr(cf.httpx, "post", post)
    assert json.loads(call())["answer"] == "Supported [S1]"


@pytest.mark.parametrize("answer", ['{"answer":"Supported [S1]"}', {"answer": "Supported [S1]"}])
def test_success_payload_usage_and_no_content_in_ledger(monkeypatch, answer):
    captured = {}
    def fake(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response({"response": answer, "usage": {"prompt_tokens": 100, "completion_tokens": 20}})
    monkeypatch.setattr(cf.httpx, "post", fake)
    assert json.loads(call()) == {"answer": "Supported [S1]"}
    assert captured["url"] == "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/run/" + cf.MODEL
    assert captured["headers"] == {"Authorization": "Bearer test-token-never-real"}
    assert captured["trust_env"] is False and captured["timeout"] == 180
    payload = captured["json"]
    assert payload["stream"] is False and payload["temperature"] == 0 and payload["max_tokens"] == 1800
    assert payload["response_format"] == {"type": "json_schema", "json_schema": {"type": "object", "properties": {"answer": {"type": "string"}}}}
    status = cf.quota_status()
    assert status["pending_requests"] == 0 and status["requests"] == 1
    assert status["used_or_reserved_neurons"] == (100 * cf.INPUT_RATE + 20 * cf.OUTPUT_RATE) / 1e6
    with cf._connection() as connection:
        stored = repr(connection.execute("SELECT * FROM cloudflare_requests").fetchall())
    assert "Private question" not in stored and "Supported" not in stored and "test-token" not in stored


@pytest.mark.parametrize("key,value", [("CLOUDFLARE_ACCOUNT_ID", ""), ("CLOUDFLARE_ACCOUNT_ID", "a" * 31), ("CLOUDFLARE_ACCOUNT_ID", "../accounts"), ("CLOUDFLARE_API_TOKEN", " "), ("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "false"), ("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "1")])
def test_unconfigured_never_calls_http(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    assert not cf.configured()
    with pytest.raises(cf.CloudflareUnavailable) as error:
        call()
    assert error.value.reason == "auth"
    assert cf.quota_status()["requests"] == 0


@pytest.mark.parametrize("status,reason", [(401, "auth"), (403, "auth"), (429, "quota"), (500, "provider"), (302, "provider")])
def test_http_rejections_keep_reservation(monkeypatch, status, reason):
    monkeypatch.setattr(cf.httpx, "post", lambda *a, **k: response(status=status))
    with pytest.raises(cf.CloudflareUnavailable) as error:
        call()
    assert error.value.reason == reason
    assert cf.quota_status()["pending_requests"] == 1
    assert cf.quota_status()["used_or_reserved_neurons"] > 0


def test_network_error_is_generic_and_reserved(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("Sensitive provider error or token")
    monkeypatch.setattr(cf.httpx, "post", fail)
    with pytest.raises(cf.CloudflareUnavailable) as error:
        call()
    assert str(error.value) == "Cloudflare inference unavailable: provider"
    assert cf.quota_status()["pending_requests"] == 1


@pytest.mark.parametrize("body", [None, [], {}, {"success": False, "result": {"response": "{}"}}, {"success": True, "errors": ["Secret"], "result": {"response": "{}"}}, {"success": True, "result": []}, {"success": True, "result": {"response": "broken JSON"}}, {"success": True, "result": {"response": "[]"}}, {"success": True, "result": {"response": '{"value":NaN}'}}, {"success": True, "result": {"response": ""}}, {"success": True, "result": {"response": None}}])
def test_malformed_envelopes_do_not_release_reservation(monkeypatch, body):
    monkeypatch.setattr(cf.httpx, "post", lambda *a, **k: httpx.Response(200, json=body))
    with pytest.raises(cf.CloudflareUnavailable) as error:
        call()
    assert error.value.reason == "invalidresponse"
    assert cf.quota_status()["pending_requests"] == 1


@pytest.mark.parametrize("extra", [{"refusal": "No"}, {"tool_calls": [{}]}, {"function_call": {"name": "x"}}, {"incomplete": True}, {"incomplete_details": {"reason": "length"}}, {"finish_reason": "length"}, {"finish_reason": "tool_calls"}, {"status": "incomplete"}, {"error": "Secret"}, {"usage": {"prompt_tokens": 100, "completion_tokens": 1800}}])
def test_refusals_tools_and_possible_truncation_fail_closed(monkeypatch, extra):
    monkeypatch.setattr(cf.httpx, "post", lambda *a, **k: response({"response": "{}", **extra}))
    with pytest.raises(cf.CloudflareUnavailable) as error:
        call()
    assert error.value.reason == "invalidresponse"
    assert cf.quota_status()["pending_requests"] == 1


@pytest.mark.parametrize("usage", [None, {}, {"prompt_tokens": True, "completion_tokens": 20}, {"prompt_tokens": -1, "completion_tokens": 20}, {"prompt_tokens": 100, "completion_tokens": "20"}])
def test_missing_or_invalid_usage_retains_reservation(monkeypatch, usage):
    monkeypatch.setattr(cf.httpx, "post", lambda *a, **k: response({"response": "{}", "usage": usage}))
    assert call() == "{}"
    assert cf.quota_status()["pending_requests"] == 1
    assert cf.quota_status()["used_or_reserved_neurons"] >= 1800 * cf.OUTPUT_RATE / 1e6


def test_quota_stops_http_and_survives_module_reload(monkeypatch):
    monkeypatch.setattr(cf, "DAILY_LIMIT", 1)
    with pytest.raises(cf.CloudflareUnavailable) as error:
        call()
    assert error.value.reason == "quota"
    monkeypatch.setattr(cf, "DAILY_LIMIT", 9_000_000_000)
    identifier = cf._reserve({"messages": []})
    before = cf.quota_status()
    importlib.reload(cf)
    assert cf.quota_status() == before
    cf._settle(identifier, {"prompt_tokens": 0, "completion_tokens": 0})
    assert cf.quota_status()["used_or_reserved_neurons"] == 0


def test_reservation_atomic_across_connections(monkeypatch):
    payload = {"messages": []}
    single_charge = (len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 1024) * cf.INPUT_RATE + 1800 * cf.OUTPUT_RATE
    monkeypatch.setattr(cf, "DAILY_LIMIT", single_charge * 2)
    cf.quota_status()  # initialize schema before the concurrent transaction checks
    def reserve(_):
        try:
            return cf._reserve(payload)
        except cf.CloudflareUnavailable:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(reserve, range(8)))
    assert sum(value is not None for value in results) == 2
    assert cf.quota_status()["pending_requests"] == 2
    assert cf.quota_status()["remaining_neurons"] == 0


def test_daily_reset_does_not_delete_old_reservations(monkeypatch):
    monkeypatch.setattr(cf, "_day", lambda: "2026-10-22")
    cf._reserve({})
    assert cf.quota_status()["requests"] == 1
    monkeypatch.setattr(cf, "_day", lambda: "2026-10-23")
    assert cf.quota_status()["requests"] == 0
    with cf._connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM cloudflare_requests").fetchone()[0] == 1


def test_actual_usage_reported_without_fake_provider_durations(monkeypatch):
    observed = []
    monkeypatch.setattr(cf.performance, "provider_usage", observed.append)
    monkeypatch.setattr(cf.httpx, "post", lambda *a, **k: response())
    call()
    assert observed == [{"prompt_eval_count": 100, "eval_count": 20}]
