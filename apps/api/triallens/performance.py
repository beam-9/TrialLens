"""Opt-in, text-free Ask timing. Never changes the response or provider request."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
import math
import os
import re
import sys
from time import perf_counter_ns
from uuid import uuid4

LOGGER = logging.getLogger("triallens.performance")
_CURRENT: ContextVar[Trace | None] = ContextVar("triallens_performance", default=None)
PHASES = ("storage_read", "retrieval", "extractive_synthesis", "context_build", "draft", "revision", "validation", "store")
USAGE = ("load_duration", "prompt_eval_duration", "eval_duration", "total_duration", "prompt_eval_count", "eval_count")
META = {"model_name", "model_digest_or_version", "pipeline_variant", "source_count_selected", "retrieved_passage_count", "context_char_count", "revision_ran", "revision_reason", "fallback_reason", "busy_response", "result_kind", "error_kind", "provider_status", "http_status"}


class Trace:
    def __init__(self):
        self.started = perf_counter_ns()
        self.route_finished = None
        self.active_pass = None
        self.data = {"trace_id": str(uuid4()), "pipeline_variant": "two_pass", "revision_ran": False,
                     "revision_reason": "not_reached", "fallback_reason": None, "busy_response": False,
                     "result_kind": "request_rejected", "error_kind": None,
                     "model_digest_or_version": (os.getenv("TRIALLENS_PERF_MODEL_DIGEST") or "")[:160] or None,
                     "source_count_selected": 0, "retrieved_passage_count": 0, "context_char_count": 0,
                     "phases_ms": {name: 0.0 for name in PHASES}, "model_calls": []}

    def snapshot(self):
        now = perf_counter_ns()
        return {**self.data, "total_wall_ms": (now - self.started) / 1e6,
                "serialization_ms": (now - self.route_finished) / 1e6 if self.route_finished else None}


def current_trace():
    return _CURRENT.get()


def annotate(**values):
    trace = _CURRENT.get()
    if trace:
        # Deliberately exclude arbitrary fields and complex values (especially text).
        for key, value in values.items():
            if key in META and (value is None or type(value) in (str, bool, int, float)):
                trace.data[key] = value[:160] if isinstance(value, str) else value


@contextmanager
def phase(name, messages=None):
    trace = _CURRENT.get()
    if trace is None:
        yield
        return
    start = perf_counter_ns()
    previous = trace.active_pass
    call = None
    if name in {"draft", "revision"}:
        call = {"pass": name, "prompt_char_count": sum(len(m.get("content", "")) for m in messages or []),
                "message_count": len(messages or []), "serialized_messages_char_count": len(json.dumps(messages or [])), "wall_ms": None,
                **{key + ("_ns" if key.endswith("duration") else ""): None for key in USAGE}}
        trace.data["model_calls"].append(call)
        trace.active_pass = call
    try:
        yield
    except Exception as error:
        if name in {"storage_read", "store"} and isinstance(error, (OSError, ValueError)):
            annotate(error_kind="storage_error", result_kind="storage_error")
        raise
    finally:
        duration = (perf_counter_ns() - start) / 1e6
        if name in PHASES:
            trace.data["phases_ms"][name] += duration
        if call is not None:
            call["wall_ms"] = duration
        trace.active_pass = previous


def provider_usage(body):
    trace = _CURRENT.get()
    if trace is None or trace.active_pass is None or not isinstance(body, dict):
        return
    trace.active_pass["done"] = body.get("done") if type(body.get("done")) is bool else None
    reason = body.get("done_reason")
    trace.active_pass["done_reason"] = reason if isinstance(reason, str) and reason in {"stop", "length", "load", "unload"} else None
    for key in USAGE:
        value = body.get(key)
        # Zero is observed data; missing/invalid is unknown, never a token estimate.
        if type(value) in (int, float) and value >= 0 and value <= 2**63 - 1 and (type(value) is int or math.isfinite(value)):
            trace.active_pass[key + ("_ns" if key.endswith("duration") else "")] = value


def route_finished():
    trace = _CURRENT.get()
    if trace:
        trace.route_finished = perf_counter_ns()


def _emit(payload):
    """Honor a configured INFO sink, otherwise make the opt-in flag usable alone.

    No global logging configuration or persistent handler is installed. This also
    avoids duplicating benchmark/caplog handlers when they already accept INFO.
    """
    logger = LOGGER
    if LOGGER.isEnabledFor(logging.INFO):
        while logger is not None:
            if any(handler.level <= logging.INFO for handler in logger.handlers):
                LOGGER.info(payload)
                return
            logger = logger.parent if logger.propagate else None
    sys.stderr.write(payload + "\n")


class AskPerformanceMiddleware:
    """Pure ASGI: includes FastAPI serialization; context propagates into sync workers."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        enabled = os.getenv("TRIALLENS_PERF_TELEMETRY", "").strip().lower() in {"1", "true"}
        if not enabled or scope.get("type") != "http" or scope.get("method") != "POST" or not re.fullmatch(r"/workspaces/[^/]+/ask", scope.get("path", "")):
            return await self.app(scope, receive, send)
        trace = Trace()
        token = _CURRENT.set(trace)
        async def observed_receive():
            message = await receive()
            if message["type"] == "http.disconnect":
                annotate(error_kind="client_disconnect")
            return message
        async def observed_send(message):
            if message["type"] == "http.response.start":
                annotate(http_status=message["status"])
            try:
                await send(message)
            except OSError:
                annotate(error_kind="client_disconnect")
                raise
        try:
            await self.app(scope, observed_receive, observed_send)
        except BaseException as error:
            if "http_status" not in trace.data:
                annotate(http_status=500)
            if not trace.data["error_kind"]:
                annotate(error_kind="cancelled" if type(error).__name__ == "CancelledError" else "application_error")
            raise
        finally:
            try:
                # No question, path, source ID, exception message, prompt or response text.
                _emit(json.dumps(trace.snapshot(), allow_nan=False, separators=(",", ":")))
            except Exception:
                pass  # Profiling must never make a successful answer fail.
            _CURRENT.reset(token)
