"""Real isolated HTTP evaluation seam with mocked hosted inference only."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys

import httpx
import pytest

EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
sys.path.insert(0, str(EVALUATION))
spec = importlib.util.spec_from_file_location("cloudflare_run", EVALUATION / "cloudflare_run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "b" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")
    monkeypatch.setenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "true")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "original.sqlite3"))


def test_fixture_dependencies_and_output_paths_fail_before_inference(configured, tmp_path):
    with pytest.raises(ValueError, match="predecessor"):
        runner.run(tmp_path / "metrics", tmp_path / "answers", ["numerical-simplify"])
    with pytest.raises(ValueError, match="different paths"):
        runner.run(tmp_path / "same", tmp_path / "same", ["numerical-hba1c"])
    (tmp_path / "metrics").write_text("retain")
    with pytest.raises(ValueError, match="immutable"):
        runner.run(tmp_path / "metrics", tmp_path / "answers", ["numerical-hba1c"])
    assert (tmp_path / "metrics").read_text() == "retain"


def test_evaluation_calls_only_hosted_model_and_preserves_original_store(configured, monkeypatch, tmp_path):
    from triallens import main, conversation
    store = main.store
    calls = []
    submitted_contexts = []
    def post(url, **kwargs):
        assert url == "https://api.cloudflare.com/client/v4/accounts/" + "b" * 32 + "/ai/run/" + runner.cloudflare.MODEL
        calls.append(url)
        submitted_contexts.append(kwargs["json"]["messages"][1]["content"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={"success": True, "result": {"response": {"paragraphs": ["Adults had a 0.5-point lower HbA1c result than placebo at 12 weeks [PubMed:EVAL-NUMBERS]."], "cited_sources": ["PubMed:EVAL-NUMBERS"], "uncertainty": []}, "usage": {"prompt_tokens": 900, "completion_tokens": 100}}})
    monkeypatch.setattr(conversation.httpx, "post", post)
    result = runner.run(tmp_path / "metrics", tmp_path / "answers", ["numerical-hba1c"])
    assert result["complete"] and result["isolation_verified"]
    assert result["summary"]["model_answers"] == 1 and len(calls) == 2
    assert result["quota"]["requests"] == 2
    assert main.store is store and conversation.httpx.post is post
    assert not (tmp_path / "original.sqlite3").exists()
    encoded = (tmp_path / "metrics").read_text()
    assert "test-token" not in encoded and "b" * 32 not in encoded
    saved_answers = json.loads((tmp_path / "answers").read_text())
    assert len(saved_answers) == 1
    captured = saved_answers[0]
    context = captured["generation_context"]
    assert context["history"] == []
    assert context["question"] == "How much did it help, and what does that mean?"
    assert context["evidence"][0]["citation"] == "PubMed:EVAL-NUMBERS"
    assert "240 adults" in context["evidence"][0]["text"]
    assert context == json.loads(submitted_contexts[0])
    assert captured["generation_context_sha256"] == hashlib.sha256(submitted_contexts[0].encode("utf-8")).hexdigest()
    assert {item["generation_context_sha256"] for item in captured["provider_outputs"]} == {captured["generation_context_sha256"]}
    encoded_answers = (tmp_path / "answers").read_text()
    assert "test-token" not in encoded_answers and "b" * 32 not in encoded_answers
    assert "Authorization" not in encoded_answers


@pytest.mark.parametrize("next_case", ["numerical-simplify", "personal-treatment"])
def test_captured_context_tracks_followup_and_resets_before_guard(configured, monkeypatch, tmp_path, next_case):
    from triallens import conversation
    def post(url, **kwargs):
        return httpx.Response(200, request=httpx.Request("POST", url), json={"success": True, "result": {
            "response": {"paragraphs": ["Adults had a 0.5-point lower HbA1c result than placebo at 12 weeks [PubMed:EVAL-NUMBERS]."],
                         "cited_sources": ["PubMed:EVAL-NUMBERS"], "uncertainty": []},
            "usage": {"prompt_tokens": 900, "completion_tokens": 100}}})
    monkeypatch.setattr(conversation.httpx, "post", post)
    runner.run(tmp_path / "metrics", tmp_path / "answers", ["numerical-hba1c", next_case])
    first, followup = json.loads((tmp_path / "answers").read_text())
    context = followup["generation_context"]
    if next_case == "personal-treatment":
        assert context is None and followup["generation_context_sha256"] is None
        assert followup["provider_outputs"] == []
        return
    assert context["question"] == "Can you explain that more simply without changing the numbers?"
    assert context["history"] == [{"question": first["answer"]["question"], "answer": first["answer"]["direct_answer"]}]
    assert context["evidence"] == first["generation_context"]["evidence"]


def test_experiments_share_separate_daily_ledger(configured, monkeypatch, tmp_path):
    from triallens import conversation
    def post(url, **kwargs):
        return httpx.Response(200, request=httpx.Request("POST", url), json={"success": True, "result": {
            "response": {"paragraphs": ["Adults had a 0.5-point lower HbA1c result than placebo at 12 weeks [PubMed:EVAL-NUMBERS]."],
                         "cited_sources": ["PubMed:EVAL-NUMBERS"], "uncertainty": []},
            "usage": {"prompt_tokens": 900, "completion_tokens": 100}}})
    monkeypatch.setattr(conversation.httpx, "post", post)
    ledger = tmp_path / "evaluation.sqlite3"
    first = runner.run(tmp_path / "metrics1", tmp_path / "answers1", ["numerical-hba1c"], ledger)
    second = runner.run(tmp_path / "metrics2", tmp_path / "answers2", ["numerical-hba1c"], ledger)
    assert first["quota"]["requests"] == 2
    assert second["quota"]["requests"] == 4
    assert second["quota"]["used_or_reserved_neurons"] == 2 * first["quota"]["used_or_reserved_neurons"]
    assert not (tmp_path / "original.sqlite3").exists()
    with pytest.raises(ValueError, match="separate"):
        runner.run(tmp_path / "metrics3", tmp_path / "answers3", ["numerical-hba1c"], tmp_path / "original.sqlite3")


def test_candidate_instructions_are_isolated_even_on_failure(tmp_path):
    from triallens import conversation
    previous = conversation.INSTRUCTIONS, conversation.REVISION_INSTRUCTIONS
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({"instructions": "candidate system", "revision_instructions": "candidate revision"}))
    with pytest.raises(RuntimeError):
        with runner.candidate_instructions(candidate):
            assert conversation.INSTRUCTIONS == "candidate system"
            assert conversation.REVISION_INSTRUCTIONS == "candidate revision"
            raise RuntimeError("provider failure")
    assert (conversation.INSTRUCTIONS, conversation.REVISION_INSTRUCTIONS) == previous
    candidate.write_text(json.dumps({"instructions": "", "revision_instructions": "revision"}))
    with pytest.raises(ValueError):
        with runner.candidate_instructions(candidate):
            pass
    assert (conversation.INSTRUCTIONS, conversation.REVISION_INSTRUCTIONS) == previous
