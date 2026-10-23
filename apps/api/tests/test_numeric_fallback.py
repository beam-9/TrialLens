"""Measured endpoint detection and quota fallback; all inference is blocked."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from triallens import cloudflare, main
from triallens.rag import has_effectiveness_statistic
from triallens.store import JsonStore
from triallens.usage import UsageLedger


@pytest.mark.parametrize("passage", [
    "At 12 weeks, HbA1c was 0.5 percentage points lower with intervention A than placebo (95% CI 0.2 to 0.8 percentage points lower).",
    "At week 12, systolic blood pressure was 5 mmHg lower with treatment than with placebo.",
    "The mean fasting plasma glucose was 18 mg/dL lower with treatment than with placebo at week 24.",
    "At week 8, the symptom score was 2 points lower with treatment than with placebo.",
])
def test_measured_endpoint_differences_are_quantitative_results(passage):
    assert has_effectiveness_statistic(passage)


@pytest.mark.parametrize("passage", [
    "The study enrolled 240 adults and assigned them to intervention A or placebo for 12 weeks.",
    "Adults were randomized to a 500 mg dose of metformin or placebo, with 120 participants in each group.",
    "Metformin was given at a dose of 500 mg to improve HbA1c, and follow-up lasted 12 weeks.",
    "The trial will assess whether HbA1c is 0.5 percentage points lower than placebo at 12 weeks.",
    "The primary outcome is HbA1c reduction of 0.5 percentage points at 12 weeks compared with placebo.",
    "The planned study aims to show a 42% reduction in lesion counts at 12 weeks compared with placebo.",
])
def test_sample_size_dose_and_planned_outcomes_are_not_measured_results(passage):
    assert not has_effectiveness_statistic(passage)


def test_planned_followup_sentence_does_not_hide_a_reported_result():
    assert has_effectiveness_statistic(
        "The study will assess mortality in a later follow-up at 24 months. "
        "At 12 weeks, HbA1c was 0.5 percentage points lower with intervention A than placebo."
    )


def test_frozen_numeric_followup_keeps_results_when_free_quota_is_unavailable(monkeypatch, tmp_path):
    fixture = Path(__file__).resolve().parents[1] / "evaluation/m0/snapshots/numerical.json"
    data = json.loads(fixture.read_text())
    store = JsonStore(tmp_path / "workspaces.json")
    payload = {key: {} for key in ("workspaces", "sources", "chunks", "extractions", "answers", "briefs")}
    workspace_id = data["workspace"]["id"]
    payload["workspaces"][workspace_id] = data["workspace"]
    for key in ("sources", "chunks", "extractions"):
        payload[key] = {item["id"]: item for item in data[key]}
    store._write(payload)
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-only")
    monkeypatch.setenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "true")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    def quota_unavailable(*args, **kwargs):
        raise cloudflare.CloudflareUnavailable("quota")
    monkeypatch.setattr(cloudflare, "completion", quota_unavailable)
    monkeypatch.setattr("triallens.conversation.httpx.post", lambda *args, **kwargs: pytest.fail("No inference or network permitted"))
    client = TestClient(main.app)
    base = f"/workspaces/{workspace_id}/ask"
    first = client.post(base, json={"question": "What numbers support the HbA1c result?"})
    assert first.status_code == 200
    follow = client.post(base, json={"question": "Can you explain that more simply without changing the numbers?", "previous_answer_id": first.json()["id"]})
    assert follow.status_code == 200
    answer = follow.json()
    assert answer["generation_mode"] == "extractive"
    assert "free allowance" in answer["generation_note"]
    assert "did not find quantitative effectiveness statistics" not in answer["direct_answer"]
    support = " ".join(answer["supporting_evidence"])
    assert "0.5 percentage points lower" in support
    assert "placebo" in support and "12 weeks" in support
    assert "95% CI 0.2 to 0.8 percentage points lower" in support
    assert "PubMed:EVAL-NUMBERS" in answer["citations"]
    assert any("This was a between-group difference" in chunk["text"] for chunk in answer["retrieved_chunks"])
    assert UsageLedger().status()["generated_answers"] == 0
