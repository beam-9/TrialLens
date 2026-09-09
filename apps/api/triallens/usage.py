"""Persistent, app-wide generation budget. Reserve before sending paid requests."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

# USD billionths; standard uncached GPT-4.1 mini token prices.
INPUT_RATE = 400
OUTPUT_RATE = 1600
BUDGET = 100_000_000  # US$0.10 total, no automatic reset
ANSWER_ALERT = 100
PRICED_MODELS = {"gpt-4.1-mini", "gpt-4.1-mini-2025-04-14"}


class BudgetUnavailable(Exception):
    pass


class UsageLedger:
    def __init__(self, path: Path | None = None):
        self.path = path or Path(os.getenv("TRIALLENS_USAGE_PATH", str(Path(__file__).resolve().parents[1] / "data" / "usage.sqlite3")))

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, charge INTEGER NOT NULL, pending INTEGER NOT NULL DEFAULT 1, answered INTEGER NOT NULL DEFAULT 0)")
            connection.commit()
            yield connection
        finally:
            connection.close()

    def reserve(self, payload: dict) -> str:
        if payload["model"] not in PRICED_MODELS:
            raise BudgetUnavailable("This model has no configured budget pricing. Paid generation is paused.")
        # A byte per input token is deliberately conservative. Include request/schema
        # overhead and maximum output; settle down to reported usage after success.
        upper_input = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 1024
        charge = upper_input * INPUT_RATE + payload["max_output_tokens"] * OUTPUT_RATE
        identifier = str(uuid4())
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            used = connection.execute("SELECT COALESCE(SUM(charge), 0) FROM requests").fetchone()[0]
            if used + charge > BUDGET:
                raise BudgetUnavailable("The next answer could exceed your US$0.10 TrialLens budget. Paid generation is paused; source excerpts remain available.")
            connection.execute("INSERT INTO requests (id, charge) VALUES (?, ?)", (identifier, charge))
            connection.commit()
        return identifier

    def settle(self, identifier: str, usage: dict):
        input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
        # Retain the reservation if the provider omits usage; do not assume zero cost.
        if type(input_tokens) is not int or type(output_tokens) is not int or min(input_tokens, output_tokens) < 0:
            return
        charge = input_tokens * INPUT_RATE + output_tokens * OUTPUT_RATE
        with self.connection() as connection:
            connection.execute("UPDATE requests SET charge = ?, pending = 0 WHERE id = ? AND pending = 1", (charge, identifier))
            connection.commit()

    def rejected(self, identifier: str):
        """A definitive pre-generation HTTP rejection did not generate paid tokens."""
        with self.connection() as connection:
            connection.execute("UPDATE requests SET charge = 0, pending = 0 WHERE id = ? AND pending = 1", (identifier,))
            connection.commit()

    def answered(self, identifier: str):
        with self.connection() as connection:
            connection.execute("UPDATE requests SET answered = 1 WHERE id = ?", (identifier,))
            connection.commit()

    def status(self) -> dict:
        with self.connection() as connection:
            charge, answered, pending = connection.execute("SELECT COALESCE(SUM(charge),0), COALESCE(SUM(answered),0), COALESCE(SUM(pending),0) FROM requests").fetchone()
        return {"budget_usd": BUDGET / 1e9, "used_or_reserved_usd": charge / 1e9,
                "remaining_usd": max(0, BUDGET - charge) / 1e9,
                "generated_answers": answered, "answer_alert_at": ANSWER_ALERT,
                "answer_alert": answered >= ANSWER_ALERT, "pending_requests": pending,
                "budget_exhausted": charge >= BUDGET}
