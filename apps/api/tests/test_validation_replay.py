import importlib.util
import json
from pathlib import Path
import sys

import pytest

EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"
sys.path.insert(0, str(EVALUATION))
spec = importlib.util.spec_from_file_location("replay_validation", EVALUATION / "replay_validation.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def test_replay_uses_real_citation_guard_without_inference_or_production_writes(tmp_path, monkeypatch):
    fixture = json.loads((EVALUATION / "m0/results/cloudflare-qualifiers-final-answers.json").read_text())
    case = next(item for item in fixture if item["case_id"] == "numerical-hba1c")
    candidate = {"paragraphs": ["The reported group difference was 0.5 percentage points at 12 weeks [PubMed:EVAL-NUMBERS]."],
                 "cited_sources": ["PubMed:EVAL-NUMBERS"], "uncertainty": []}
    unknown = {**candidate, "paragraphs": ["A result [PubMed:UNKNOWN]."], "cited_sources": ["PubMed:UNKNOWN"]}
    case["provider_outputs"] = [{"response": unknown}, {"response": candidate}]
    source = tmp_path / "recorded.json"
    source.write_text(json.dumps([case]))
    output = tmp_path / "observations.json"
    production_store = replay.main.store
    production_before = production_store.path.read_bytes()
    quota = tmp_path / "real-usage.sqlite3"
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(quota))
    result = replay.run(source, output)
    assert result["provider_requests"] == result["local_model_calls"] == 0
    assert result["summary"] == {"draft": {"n": 1, "accepted": 0}, "revision": {"n": 1, "accepted": 1}}
    assert all(row["mock_completion_calls"] == 2 for row in result["observations"])
    assert replay.main.store is production_store
    assert production_store.path.read_bytes() == production_before
    assert not quota.exists()
    retained = output.read_bytes()
    with pytest.raises(ValueError, match="immutable"):
        replay.run(source, output)
    assert output.read_bytes() == retained


def test_replay_rejects_duplicate_case_ids(tmp_path):
    case = {"case_id": "numerical-hba1c", "answer": {}, "provider_outputs": []}
    source = tmp_path / "duplicate.json"
    source.write_text(json.dumps([case, case]))
    with pytest.raises(ValueError, match="duplicate"):
        replay.run(source, tmp_path / "result.json")
