"""Gated GPT-OSS native Responses profile. HTTP is always mocked."""
import copy
import json

import httpx
import pytest

from triallens import cloudflare as cf

FINAL = {"paragraphs": ["The supplied evidence is insufficient."], "cited_sources": [], "uncertainty": []}
SCHEMA = {"type": "object", "additionalProperties": False, "properties": {"paragraphs": {"type": "array", "items": {"type": "string"}}}}
MESSAGES = [{"role": "system", "content": "Keep citations"}, {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Draft"}, {"role": "user", "content": "Revise"}]


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "fake-not-a-secret")
    monkeypatch.setenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "true")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(cf, "MODEL", "@cf/openai/gpt-oss-120b")
    monkeypatch.setattr(cf, "MAX_OUTPUT_TOKENS", 4096)
    monkeypatch.setattr(cf.httpx, "post", lambda *a, **k: pytest.fail("Unexpected HTTP call"))


def completed():
    return {"object": "response", "status": "completed", "error": None, "incomplete_details": None,
            "output": [{"type": "reasoning", "status": "completed", "summary": [{"type": "summary_text", "text": "NEVER EXPOSE REASONING"}]},
                       {"type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": json.dumps(FINAL)}]}],
            "usage": {"input_tokens": 100, "output_tokens": 70, "output_tokens_details": {"reasoning_tokens": 20}}}


def fake(monkeypatch, result):
    calls = []
    def post(url, **kwargs):
        calls.append((url, copy.deepcopy(kwargs)))
        return httpx.Response(200, json={"success": True, "errors": [], "result": result})
    monkeypatch.setattr(cf.httpx, "post", post)
    return calls


def call():
    return cf.completion(MESSAGES, SCHEMA)


def test_responses_payload_native_endpoint_low_effort_and_final_only(monkeypatch):
    calls = fake(monkeypatch, completed())
    observed = []
    monkeypatch.setattr(cf.performance, "provider_usage", observed.append)
    text = call()
    assert json.loads(text) == FINAL and "NEVER EXPOSE" not in text
    url, kwargs = calls[0]
    assert url == "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/run/@cf/openai/gpt-oss-120b"
    assert kwargs["trust_env"] is False
    assert kwargs["json"] == {"instructions": "Keep citations", "input": MESSAGES[1:], "stream": False,
                              "temperature": 0, "max_output_tokens": 4096, "reasoning": {"effort": "low"},
                              "text": {"format": {"type": "json_schema", "name": "triallens_answer", "strict": True, "schema": SCHEMA}}}
    assert observed == [{"prompt_eval_count": 100, "eval_count": 70}]
    status = cf.quota_status()
    assert status["pending_requests"] == 0
    # Output usage includes reasoning tokens; never subtract those from the quota.
    assert status["used_or_reserved_neurons"] == (100 * cf.INPUT_RATE + 70 * cf.OUTPUT_RATE) / 1e6
    with cf._connection() as connection:
        assert "NEVER EXPOSE" not in repr(connection.execute("SELECT * FROM cloudflare_requests").fetchall())


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(status="incomplete", incomplete_details={"reason": "max_output_tokens"}),
    lambda r: r.update(status="failed", error={"message": "PRIVATE RAW ERROR"}),
    lambda r: r.pop("status"),
    lambda r: r.update(output=[]),
    lambda r: r.update(output=r["output"][:1]),
    lambda r: r["output"].append(copy.deepcopy(r["output"][-1])),
    lambda r: r["output"].append({"type": "function_call", "status": "completed", "name": "tool"}),
    lambda r: r["output"][-1].update(role="user"),
    lambda r: r["output"][-1].update(status="in_progress"),
    lambda r: r["output"][-1].pop("status"),
    lambda r: r["output"][-1].update(content=[{"type": "refusal", "refusal": "Declined"}]),
    lambda r: r["output"][-1].update(content=[{"type": "output_text", "text": "{}", "refusal": "Declined"}]),
    lambda r: r["output"][-1].update(tool_calls=[{"name": "tool"}]),
    lambda r: r["output"][-1]["content"].append({"type": "output_text", "text": "{}"}),
    lambda r: r["output"][-1]["content"][0].update(text=""),
    lambda r: r["output"][-1]["content"][0].update(text="{broken"),
    lambda r: r["output"][-1]["content"][0].update(text='{"value": NaN}'),
    lambda r: r["output"][0].update(status="incomplete"),
    lambda r: r.update(response=FINAL),
    lambda r: r.update(choices=[]),
    lambda r: r.update(output_text=json.dumps(FINAL)),
    lambda r: r.update(object="chat.completion"),
    lambda r: r.update(incomplete_details={"reason": "length"}),
    lambda r: r["usage"].update(output_tokens=4096),
    lambda r: r["usage"].update(output_tokens=4097),
    lambda r: r["usage"].update(prompt_tokens=99, completion_tokens=70),
    lambda r: r.update(output="not a list"),
    lambda r: r["output"].append(None),
])
def test_incomplete_ambiguous_refused_and_tool_results_keep_full_reservation(monkeypatch, mutation):
    result = completed()
    mutation(result)
    fake(monkeypatch, result)
    with pytest.raises(cf.CloudflareUnavailable) as error:
        call()
    assert error.value.reason == "invalidresponse"
    assert "PRIVATE RAW ERROR" not in str(error.value)
    status = cf.quota_status()
    assert status["pending_requests"] == 1
    assert status["used_or_reserved_neurons"] >= 4096 * cf.OUTPUT_RATE / 1e6


@pytest.mark.parametrize("usage", [None, {}, {"input_tokens": True, "output_tokens": 1},
                                    {"input_tokens": 1, "output_tokens": -1}, {"input_tokens": "100", "output_tokens": 70},
                                    {"input_tokens": 100, "output_tokens": 1.5}])
def test_missing_invalid_native_usage_does_not_invent_counters_or_release_reservation(monkeypatch, usage):
    result = completed()
    result["usage"] = usage
    fake(monkeypatch, result)
    observed = []
    monkeypatch.setattr(cf.performance, "provider_usage", observed.append)
    assert json.loads(call()) == FINAL
    assert observed == []
    assert cf.quota_status()["pending_requests"] == 1


def test_gpt_profile_rejects_legacy_protocol_even_if_json_valid(monkeypatch):
    fake(monkeypatch, {"response": FINAL, "usage": {"prompt_tokens": 100, "completion_tokens": 70}})
    with pytest.raises(cf.CloudflareUnavailable, match="invalidresponse"):
        call()
    assert cf.quota_status()["pending_requests"] == 1


def test_valid_zero_native_usage_is_observed_and_settled(monkeypatch):
    result = completed()
    result["usage"] = {"input_tokens": 0, "output_tokens": 0}
    fake(monkeypatch, result)
    assert json.loads(call()) == FINAL
    assert cf.quota_status()["used_or_reserved_neurons"] == 0
    assert cf.quota_status()["pending_requests"] == 0


def test_quota_rejection_precedes_any_http_for_native_profile(monkeypatch):
    monkeypatch.setattr(cf, "DAILY_LIMIT", 1)
    with pytest.raises(cf.CloudflareUnavailable, match="quota"):
        call()
    assert cf.quota_status()["requests"] == 0


def test_native_profile_rejects_tool_input_without_http():
    with pytest.raises(cf.CloudflareUnavailable, match="configuration"):
        cf.completion([{"role": "tool", "content": "tool output"}], SCHEMA)
    assert cf.quota_status()["requests"] == 0
