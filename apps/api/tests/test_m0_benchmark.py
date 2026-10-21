import importlib.util
import json
from pathlib import Path
import time

import httpx
import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "evaluation/m0/benchmark.py"
spec = importlib.util.spec_from_file_location("m0_benchmark", MODULE_PATH)
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_rates_do_not_invent_missing_tokens_or_divide_by_zero():
    assert benchmark.rates({}) == {"generation_tokens_per_second": None, "prompt_tokens_per_second": None}
    assert benchmark.rates({"eval_count": 0, "eval_duration_ns": 0})["generation_tokens_per_second"] is None
    assert benchmark.rates({"eval_count": 0, "eval_duration_ns": 1000})["generation_tokens_per_second"] == 0
    assert benchmark.rates({"eval_count": 10, "eval_duration_ns": 500_000_000})["generation_tokens_per_second"] == 20
    assert benchmark.percentile([], .95) is None
    assert benchmark.percentile(list(range(1, 11)), .95) == 10


def test_frozen_store_refuses_modified_snapshot(tmp_path):
    inventory = json.loads(benchmark.INVENTORY.read_text())
    inventory["snapshots"][0]["sha256"] = "tampered"
    with pytest.raises(ValueError, match="hash mismatch"):
        benchmark.frozen_store(tmp_path / "isolated.json", inventory)
    assert not (tmp_path / "isolated.json").exists()


def test_real_http_guard_keeps_data_and_usage_isolated(monkeypatch, tmp_path):
    from triallens import main
    original_store = main.store
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "original-usage.sqlite3"))
    inventory = json.loads(benchmark.INVENTORY.read_text())
    guard = next(case for case in inventory["cases"] if case["expected_route"] == "treatment_guard")
    with benchmark.isolated_server(tmp_path, inventory, "test-digest") as (base, ids, handler):
        assert main.store is not original_store
        with httpx.Client(timeout=5, trust_env=False) as client:
            response = client.post(base + f'/workspaces/{ids[guard["snapshot_id"]]}/ask', json={"question": guard["question"]})
        assert response.status_code == 200
        deadline = time.monotonic() + 1
        while not handler.records and time.monotonic() < deadline:
            time.sleep(.001)
        assert len(handler.records) == 1
        assert handler.records[0]["result_kind"] == "treatment_guard"
        assert handler.records[0]["model_calls"] == []
        assert guard["question"] not in json.dumps(handler.records)
    assert main.store is original_store
    assert not (tmp_path / "original-usage.sqlite3").exists()
    import os
    assert os.environ["TRIALLENS_CHAT_PROVIDER"] == "openai"
