import copy

import httpx
import pytest

from triallens import cloudflare

from evaluation.thinking_profile import SUPPORTED_MODEL, disabled_thinking


@pytest.fixture
def qwen(monkeypatch):
    monkeypatch.setattr(cloudflare, "MODEL", SUPPORTED_MODEL)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "fake-token")
    monkeypatch.setenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "true")
    reserved, sent = [], []
    original_reserve = cloudflare._reserve

    def reserve(payload):
        reserved.append(copy.deepcopy(payload))
        return "test-reservation"

    def post(url, **kwargs):
        sent.append(copy.deepcopy(kwargs["json"]))
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "success": True,
            "result": {"response": '{"ok": true}', "usage": {"prompt_tokens": 3, "completion_tokens": 2}},
        })

    monkeypatch.setattr(cloudflare, "_reserve", reserve)
    monkeypatch.setattr(cloudflare.httpx, "post", post)
    return reserved, sent, original_reserve, reserve


def completion():
    return cloudflare.completion([{"role": "user", "content": "Return a small JSON object."}],
                                 {"type": "object"})


def test_profile_disables_thinking_in_reserved_and_sent_request(qwen):
    reserved, sent, _, reserve = qwen

    with disabled_thinking(True):
        assert completion() == '{"ok": true}'

    assert reserved[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert sent[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert reserved[0]["reasoning_effort"] == "low"
    assert cloudflare._reserve is reserve

    completion()
    assert "chat_template_kwargs" not in sent[1]
    assert sent[1]["reasoning_effort"] == "low"


def test_existing_chat_template_kwargs_are_merged(qwen):
    _, _, _, reserve = qwen
    seen = []
    original = cloudflare._reserve
    cloudflare._reserve = lambda payload: seen.append(copy.deepcopy(payload)) or reserve(payload)
    try:
        with disabled_thinking(True):
            cloudflare._reserve({"messages": [], "chat_template_kwargs": {"custom": "kept"}})
    finally:
        cloudflare._reserve = original
    assert seen[0]["chat_template_kwargs"] == {"custom": "kept", "enable_thinking": False}


def test_disabled_profile_is_inert(qwen):
    _, _, _, reserve = qwen
    with disabled_thinking():
        assert cloudflare._reserve is reserve
    assert cloudflare._reserve is reserve


def test_unsupported_model_fails_before_installing_wrapper(qwen, monkeypatch):
    monkeypatch.setattr(cloudflare, "MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
    original = cloudflare._reserve
    with pytest.raises(ValueError, match="requires @cf/qwen/qwen3.8-27b"):
        with disabled_thinking(True):
            pytest.fail("unsupported model entered profile")
    assert cloudflare._reserve is original


def test_model_change_during_profile_fails_before_reservation(qwen, monkeypatch):
    reserved, _, _, _ = qwen
    original = cloudflare._reserve
    with disabled_thinking(True):
        monkeypatch.setattr(cloudflare, "MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
        with pytest.raises(ValueError, match="requires @cf/qwen/qwen3.8-27b"):
            cloudflare._reserve({"messages": []})
    assert cloudflare._reserve is original
    assert reserved == []


@pytest.mark.parametrize("kwargs", [None, [], "bad"])
def test_malformed_profile_options_fail_before_reservation(qwen, kwargs):
    reserved, _, _, _ = qwen
    original = cloudflare._reserve
    with disabled_thinking(True):
        with pytest.raises(ValueError, match="chat_template_kwargs must be an object"):
            cloudflare._reserve({"messages": [], "chat_template_kwargs": kwargs})
    assert cloudflare._reserve is original
    assert reserved == []


@pytest.mark.parametrize("payload", [
    {"messages": "not a list"},
    {"input": [], "messages": []},
    {"input": []},
])
def test_unsupported_protocol_fails_closed_before_reservation(qwen, payload):
    reserved, _, _, _ = qwen
    original = cloudflare._reserve
    with disabled_thinking(True):
        with pytest.raises(ValueError, match="native chat messages request"):
            cloudflare._reserve(payload)
    assert cloudflare._reserve is original
    assert reserved == []


def test_wrapper_restores_reservation_on_exception(qwen):
    original = cloudflare._reserve
    with pytest.raises(RuntimeError, match="injected"):
        with disabled_thinking(True):
            raise RuntimeError("injected")
    assert cloudflare._reserve is original
