import json
from pathlib import Path

import pytest

from evaluation.atomic_reporting_oracle import render_atomic_oracle
from triallens.answer_checks import estimate_interval_issue, unreported_percentage_issue


_EVALUATION = Path(__file__).resolve().parents[1] / "evaluation"


@pytest.fixture
def frozen_atomic():
    snapshot = (_EVALUATION / "cohorts/paper-captions-v2-2026-11-23/captions.json").read_bytes()
    capture = _EVALUATION / "answer_coverage/results/paper-passage-feedback-2026-11-25.json"
    evidence = {
        row["case_id"]: row["generation_context"]["evidence"]
        for row in json.loads(capture.read_text())
    }
    return snapshot, evidence


def test_frozen_atomic_oracle_retains_arms_uncertainty_and_figure_scope(frozen_atomic):
    snapshot, contexts = frozen_atomic
    evidence = contexts["full-text-results"]
    answer = render_atomic_oracle("full-text-results", evidence, snapshot)
    assert "fell 0.58% ± 0.11% with metformin plus atorvastatin" in answer
    assert "rose 0.35% ± 0.11% with atorvastatin alone" in answer
    assert "difference magnitude of 0.94%" in answer
    assert "signed contrast was -0.94% (95% CI -1.25 to -0.63)" in answer
    assert "Article coverage is partial" in answer
    assert "8 weeks" not in answer
    assert estimate_interval_issue(answer, evidence) is None
    assert unreported_percentage_issue(answer, evidence, require_citations=True) is None
    assert render_atomic_oracle("full-text-results", evidence, snapshot) == answer


def test_frozen_atomic_oracle_does_not_fill_missing_rewrite_caption(frozen_atomic):
    snapshot, contexts = frozen_atomic
    with pytest.raises(ValueError, match="Missing or ambiguous selected support: Full text figure caption 002"):
        render_atomic_oracle("full-text-simplify", contexts["full-text-simplify"], snapshot)


def test_frozen_atomic_oracle_figure_case_does_not_insert_unrequested_arm_estimates(frozen_atomic):
    snapshot, contexts = frozen_atomic
    answer = render_atomic_oracle("caption-interval", contexts["full-text-results"], snapshot)
    assert "signed contrast was -0.94%" in answer
    assert "±" not in answer
    assert "difference magnitude" not in answer


@pytest.mark.parametrize("invalid", ["snapshot", "caption", "results", "owner", "link"])
def test_frozen_atomic_oracle_rejects_altered_support(frozen_atomic, invalid):
    snapshot, contexts = frozen_atomic
    evidence = contexts["full-text-results"]
    record, = evidence
    if invalid == "snapshot":
        snapshot += b" "
    elif invalid == "owner":
        evidence.append(record)
    else:
        section_id = "019" if invalid == "results" else "002"
        link = next(link for link in record["paper_passage_links"] if section_id in link["section"])
        if invalid == "link":
            link["matched_passage_index"] = True
        else:
            index = link["matched_passage_index"]
            original = record["matched_passages"][index]
            record["matched_passages"][index] = original.replace("0.94%", "0.95%")
            assert record["matched_passages"][index] != original
    with pytest.raises(ValueError):
        render_atomic_oracle("full-text-results", evidence, snapshot)


def test_oracle_answer_and_rewrite_pass_final_guards_in_isolated_ask(monkeypatch, tmp_path, frozen_atomic):
    from fastapi.testclient import TestClient

    from triallens import conversation, main
    from triallens.store import JsonStore

    snapshot_bytes, _ = frozen_atomic
    snapshot = json.loads(snapshot_bytes)
    workspace = snapshot["workspace"]
    seeded = {key: {row["id"]: row for row in snapshot[key]} for key in ("sources", "chunks", "extractions")}
    store = JsonStore(tmp_path / "workspace.json")
    store._write({**seeded, "workspaces": {workspace["id"]: workspace}, "answers": {}, "briefs": {}})
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(conversation, "chat_configured", lambda: True)
    inventory = json.loads((_EVALUATION / "cohorts/paper-captions-v2-2026-11-23/inventory.json").read_text())
    cases = {case["id"]: case["question"] for case in inventory["cases"]}
    ids_by_question = {question: identifier for identifier, question in cases.items()}
    calls = []

    def fixture_completion(messages, schema):
        payload = json.loads(messages[1]["content"])
        case_id = ids_by_question[payload["question"]]
        calls.append(case_id)
        answer = render_atomic_oracle(case_id, payload["evidence"], snapshot_bytes)
        return json.dumps({"paragraphs": answer.split("\n\n"), "cited_sources": ["PubMed:38763510"], "uncertainty": []})

    monkeypatch.setattr(conversation.cloudflare, "completion", fixture_completion)
    previous = None
    with TestClient(main.app) as client:
        for case_id in ("full-text-results", "full-text-simplify"):
            response = client.post(f'/workspaces/{workspace["id"]}/ask', json={
                "question": cases[case_id], "previous_answer_id": previous,
            })
            assert response.status_code == 200
            answer = response.json()
            assert answer["generation_mode"] == "conversational"
            assert "signed contrast was -0.94% (95% CI -1.25 to -0.63)" in answer["direct_answer"]
            assert answer["direct_answer"].count("± 0.11%") == 2
            previous = answer["id"]
    assert calls == ["full-text-results"] * 2 + ["full-text-simplify"] * 2
