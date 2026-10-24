"""Explicitly enabled Workers AI inference with a conservative local daily quota.

The free-plan setting is an operator attestation, not a billing/account lookup.
Keep the Cloudflare account on Workers Free: this ledger cannot see other apps'
usage or prevent Cloudflare billing on a paid account.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

import httpx

from . import performance

MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
MAX_OUTPUT_TOKENS = 1800
# Integer micro-neurons: documented neurons per million input/output tokens.
INPUT_RATE = 26668
OUTPUT_RATE = 204805
DAILY_LIMIT = 9_000_000_000  # 9,000 neurons, below the 10,000 Free allocation


class CloudflareUnavailable(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__("Cloudflare inference unavailable: " + reason)


def configured() -> bool:
    return bool(re.fullmatch(r"[a-fA-F0-9]{32}", os.getenv("CLOUDFLARE_ACCOUNT_ID", ""))
                and os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
                and os.getenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "").strip().lower() == "true")


def _day() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@contextmanager
def _connection():
    path = Path(os.getenv("TRIALLENS_USAGE_PATH", str(Path(__file__).resolve().parents[1] / "data" / "usage.sqlite3")))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=10)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS cloudflare_requests (id TEXT PRIMARY KEY, day TEXT NOT NULL, charge INTEGER NOT NULL CHECK(charge >= 0), pending INTEGER NOT NULL DEFAULT 1)")
            connection.execute("CREATE INDEX IF NOT EXISTS cloudflare_requests_day ON cloudflare_requests(day)")
            connection.commit()
            yield connection
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        raise CloudflareUnavailable("quota") from None


def _reserve(payload: dict) -> str:
    # This is a deliberately high byte-based reservation, NOT a token estimate.
    input_bound = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 1024
    charge = input_bound * INPUT_RATE + MAX_OUTPUT_TOKENS * OUTPUT_RATE
    identifier, day = str(uuid4()), _day()
    with _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        used = connection.execute("SELECT COALESCE(SUM(charge), 0) FROM cloudflare_requests WHERE day = ?", (day,)).fetchone()[0]
        if used + charge > DAILY_LIMIT:
            raise CloudflareUnavailable("quota")
        connection.execute("INSERT INTO cloudflare_requests (id, day, charge) VALUES (?, ?, ?)", (identifier, day, charge))
        connection.commit()
    return identifier


def _valid_usage(usage) -> bool:
    return isinstance(usage, dict) and all(type(usage.get(key)) is int and 0 <= usage[key] <= 2**31 - 1 for key in ("prompt_tokens", "completion_tokens"))


def _settle(identifier: str, usage):
    # Missing/invalid usage and every failed request retain the entire reservation.
    if not _valid_usage(usage):
        return
    charge = usage["prompt_tokens"] * INPUT_RATE + usage["completion_tokens"] * OUTPUT_RATE
    with _connection() as connection:
        connection.execute("UPDATE cloudflare_requests SET charge = ?, pending = 0 WHERE id = ? AND pending = 1", (charge, identifier))
        connection.commit()


def quota_status() -> dict:
    with _connection() as connection:
        charge, pending, requests = connection.execute("SELECT COALESCE(SUM(charge), 0), COALESCE(SUM(pending), 0), COUNT(*) FROM cloudflare_requests WHERE day = ?", (_day(),)).fetchone()
    return {"daily_limit_neurons": DAILY_LIMIT / 1e6, "used_or_reserved_neurons": charge / 1e6,
            "remaining_neurons": max(0, DAILY_LIMIT - charge) / 1e6,
            "pending_requests": pending, "requests": requests}


def _reject_constant(value):
    raise ValueError("Non-finite JSON constant")


def response_content(result: dict):
    """Read only completed assistant output; never expose reasoning/tool fields."""
    if "choices" not in result:
        return result.get("response")
    choices = result["choices"]
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("Ambiguous provider output")
    choice = choices[0]
    if (not isinstance(choice, dict) or choice.get("finish_reason") != "stop"
            or type(choice.get("index")) is not int or choice["index"] != 0):
        raise ValueError("Incomplete provider choice")
    message = choice.get("message")
    if (not isinstance(message, dict) or message.get("role") != "assistant"
            or message.get("tool_calls") or message.get("function_call") or message.get("refusal")
            or not isinstance(message.get("content"), str) or not message["content"].strip()):
        raise ValueError("Not a final assistant answer")
    # Some Cloudflare models return both a parsed response and its original
    # chat-completion envelope. Accept redundant output only when the JSON is
    # identical; conflicting answers remain an error.
    legacy = result.get("response")
    if legacy is not None:
        primary = json.loads(message["content"], parse_constant=_reject_constant)
        duplicate = json.loads(legacy, parse_constant=_reject_constant) if isinstance(legacy, str) else legacy
        if not isinstance(primary, dict) or not isinstance(duplicate, dict) or primary != duplicate:
            raise ValueError("Conflicting provider output")
    return message["content"]


def completion(messages: list[dict], schema: dict) -> str:
    if not configured():
        raise CloudflareUnavailable("auth")
    payload = {"messages": messages, "stream": False, "temperature": 0,
               "max_tokens": MAX_OUTPUT_TOKENS,
               "response_format": {"type": "json_schema", "json_schema": schema}}
    if MODEL == "@cf/zai-org/glm-4.7-flash":
        payload["response_format"]["json_schema"] = {"name": "triallens_answer", "strict": True, "schema": schema}
        # Cloudflare's documented chat-template option keeps this conversational
        # profile within its final-answer budget instead of emitting reasoning.
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    identifier = _reserve(payload)
    url = "https://api.cloudflare.com/client/v4/accounts/" + os.environ["CLOUDFLARE_ACCOUNT_ID"] + "/ai/run/" + MODEL
    try:
        response = httpx.post(url, headers={"Authorization": "Bearer " + os.environ["CLOUDFLARE_API_TOKEN"].strip()},
                              json=payload, timeout=180, trust_env=False)
    except httpx.HTTPError:
        raise CloudflareUnavailable("provider") from None
    if response.status_code in {401, 403}:
        raise CloudflareUnavailable("auth")
    if response.status_code == 429:
        raise CloudflareUnavailable("quota")
    if not 200 <= response.status_code < 300:
        raise CloudflareUnavailable("provider")
    try:
        body = response.json()
        if not isinstance(body, dict) or body.get("success") is not True or body.get("errors"):
            raise ValueError()
        result = body.get("result")
        if not isinstance(result, dict) or any(result.get(key) for key in ("errors", "error", "refusal", "tool_calls", "function_call", "incomplete", "incomplete_details")):
            raise ValueError()
        if result.get("finish_reason") not in (None, "stop") or result.get("status") in {"incomplete", "failed", "cancelled"}:
            raise ValueError()
        usage = result.get("usage")
        if isinstance(usage, dict) and type(usage.get("completion_tokens")) is int and usage["completion_tokens"] >= MAX_OUTPUT_TOKENS:
            raise ValueError()
        answer = response_content(result)
        if isinstance(answer, dict):
            text = json.dumps(answer, ensure_ascii=False, allow_nan=False)
        elif isinstance(answer, str) and answer.strip():
            # Schema/grounding validation stays with the existing Ask pipeline.
            # Reject malformed JSON here rather than returning provider prose.
            if not isinstance(json.loads(answer, parse_constant=_reject_constant), dict):
                raise ValueError()
            text = answer
        else:
            raise ValueError()
    except (ValueError, TypeError):
        raise CloudflareUnavailable("invalidresponse") from None
    if _valid_usage(usage):
        performance.provider_usage({"prompt_eval_count": usage["prompt_tokens"], "eval_count": usage["completion_tokens"]})
    _settle(identifier, usage)
    return text
