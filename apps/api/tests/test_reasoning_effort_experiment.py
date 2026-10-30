"""Evaluation-only reasoning experiments, using fake HTTP and temporary counters."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import httpx
import pytest

from triallens import cloudflare

ROOT = Path(__file__).resolve().parents[1] / "evaluation/answer_coverage"
spec = importlib.util.spec_from_file_location("evaluate_quality", ROOT / "evaluate_quality.py")
quality = importlib.util.module_from_spec(spec)
# The CLI naturally has this directory on sys.path. Restore import-time changes.
_previous_path = list(sys.path)
try:
    sys.path.insert(0, str(ROOT))
    spec.loader.exec_module(quality)
finally:
    sys.path[:] = _previous_path


@pytest.fixture
def native(monkeypatch, tmp_path):
    monkeypatch.setattr(cloudflare, "MODEL", "@cf/openai/gpt-oss-120b")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "fake-token")
    monkeypatch.setenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "true")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    original_reserve = cloudflare._reserve
    reserved, captured = [], []
    def reserve(payload):
        reserved.append(copy.deepcopy(payload))
        return original_reserve(payload)
    def post(url, **kwargs):
        assert url.endswith("/ai/run/@cf/openai/gpt-oss-120b")
        captured.append(copy.deepcopy(kwargs["json"]))
        return httpx.Response(200, json={"success": True, "result": {
            "status": "completed", "output": [{"type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": '{"answer":"final"}'}]}],
            "usage": {"input_tokens": 50, "output_tokens": 20}}})
    monkeypatch.setattr(cloudflare, "_reserve", reserve)
    monkeypatch.setattr(cloudflare.httpx, "post", post)
    return reserved, captured, reserve


def call():
    return cloudflare.completion([{"role": "system", "content": "instructions"}, {"role": "user", "content": "question"}], {"type": "object"})


@pytest.mark.parametrize("effort", ["low", "medium", "high"])
def test_same_reasoning_option_reaches_exact_reservation_and_http_capture(native, effort):
    reserved, captured, original = native
    with quality.reasoning_effort_experiment(effort):
        assert json.loads(call()) == {"answer": "final"}
    assert cloudflare._reserve is original
    assert reserved == captured
    assert reserved[0]["reasoning"] == {"effort": effort}
    assert "messages" not in reserved[0] and "input" in reserved[0]
    # Production profile is unchanged after leaving the wrapper.
    call()
    assert reserved[-1]["reasoning"] == {"effort": "low"}


def test_wrapper_restores_on_exception(native):
    original = cloudflare._reserve
    with pytest.raises(RuntimeError, match="injected"):
        with quality.reasoning_effort_experiment("medium"):
            raise RuntimeError("injected")
    assert cloudflare._reserve is original


@pytest.mark.parametrize("effort", ["unknown", "", False, []])
def test_invalid_option_refused_before_patch_or_http(native, effort):
    reserved, captured, original = native
    with pytest.raises(ValueError, match="low, medium or high"):
        with quality.reasoning_effort_experiment(effort):
            pytest.fail("Invalid experiment entered")
    assert cloudflare._reserve is original and not reserved and not captured


def test_other_models_refused_before_patch_or_http(native, monkeypatch):
    reserved, captured, original = native
    monkeypatch.setattr(cloudflare, "MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
    with pytest.raises(ValueError, match="requires native GPT-OSS"):
        with quality.reasoning_effort_experiment("medium"):
            pytest.fail("Non-native experiment entered")
    assert cloudflare._reserve is original and not reserved and not captured


def test_absent_option_is_inert_for_production_model(native, monkeypatch):
    original = cloudflare._reserve
    monkeypatch.setattr(cloudflare, "MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
    with quality.reasoning_effort_experiment(None):
        assert cloudflare._reserve is original


@pytest.mark.parametrize("payload", [{"messages": []}, {"input": [], "max_output_tokens": 100, "reasoning": {}},
    {"input": [], "max_output_tokens": True, "reasoning": {"effort": "low"}},
    {"input": [], "max_tokens": 100, "max_output_tokens": 100, "reasoning": {"effort": "low"}}])
def test_invalid_native_profile_refused_before_original_reservation(native, payload):
    reserved, captured, original = native
    with quality.reasoning_effort_experiment("medium"):
        with pytest.raises(ValueError, match="native Responses request profile"):
            cloudflare._reserve(payload)
    assert not reserved and not captured and cloudflare._reserve is original


def test_model_cannot_change_inside_experiment(native, monkeypatch):
    reserved, captured, _ = native
    with quality.reasoning_effort_experiment("high"):
        monkeypatch.setattr(cloudflare, "MODEL", "@cf/zai-org/glm-4.7-flash")
        with pytest.raises(ValueError, match="native Responses request profile"):
            cloudflare._reserve({"input": [], "reasoning": {"effort": "low"}, "max_output_tokens": 100})
    assert not reserved and not captured


def test_cli_records_option_and_restores_seams(native, monkeypatch, tmp_path):
    output, answers = tmp_path / "metrics.json", tmp_path / "answers.json"
    original_model, original_reserve = cloudflare.MODEL, cloudflare._reserve
    monkeypatch.setattr(quality, "load_dotenv", lambda *a, **k: None)
    def run(*args, **kwargs):
        call()
        return {"complete": True}
    monkeypatch.setattr(quality.cloudflare_run, "run", run)
    monkeypatch.setattr(sys, "argv", ["evaluate_quality.py", "--model-experiment", "@cf/openai/gpt-oss-120b",
        "--reasoning-effort", "medium", "--output", str(output), "--answers", str(answers)])
    assert quality.main() == 0
    result = json.loads(output.read_text())
    assert result["quality_experiment"]["reasoning_effort"] == "medium"
    assert native[0][0]["reasoning"] == {"effort": "medium"}
    assert cloudflare.MODEL == original_model and cloudflare._reserve is original_reserve
