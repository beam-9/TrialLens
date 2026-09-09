from concurrent.futures import ThreadPoolExecutor

import pytest

from triallens.usage import BudgetUnavailable, UsageLedger


def payload(size=100):
    return {"model": "gpt-4.1-mini", "input": "a" * size, "max_output_tokens": 2200}


def test_budget_persists_and_counts_successful_answers(tmp_path):
    path = tmp_path / "usage.sqlite3"
    ledger = UsageLedger(path)
    for _ in range(100):
        request = ledger.reserve(payload())
        ledger.settle(request, {"input_tokens": 10, "output_tokens": 10})
        ledger.answered(request)
        ledger.answered(request)  # idempotent
    status = UsageLedger(path).status()
    assert status["generated_answers"] == 100
    assert status["answer_alert"] is True
    assert status["used_or_reserved_usd"] == pytest.approx(0.002)
    assert status["pending_requests"] == 0


def test_concurrent_reservations_cannot_exceed_budget(tmp_path):
    ledger = UsageLedger(tmp_path / "usage.sqlite3")
    ledger.status()  # create schema
    def reserve(_):
        try:
            return ledger.reserve(payload(40_000))
        except BudgetUnavailable:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        reservations = list(pool.map(reserve, range(20)))
    assert any(item is None for item in reservations)
    assert ledger.status()["used_or_reserved_usd"] <= 0.1
    assert ledger.status()["generated_answers"] == 0


def test_uncertain_requests_keep_reserved_cost(tmp_path):
    ledger = UsageLedger(tmp_path / "usage.sqlite3")
    request = ledger.reserve(payload())
    before = ledger.status()
    ledger.settle(request, {})
    assert ledger.status() == before
    ledger.settle(request, {"input_tokens": -1, "output_tokens": 0})
    assert ledger.status() == before


def test_unknown_pricing_and_oversized_requests_fail_closed(tmp_path):
    ledger = UsageLedger(tmp_path / "usage.sqlite3")
    with pytest.raises(BudgetUnavailable):
        ledger.reserve({**payload(), "model": "unknown"})
    with pytest.raises(BudgetUnavailable):
        ledger.reserve(payload(300_000))
    assert ledger.status()["used_or_reserved_usd"] == 0
