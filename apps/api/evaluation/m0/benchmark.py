"""M0 only: frozen evidence + actual HTTP Ask + native Ollama; isolated data/usage.

No prompts/settings/strategies are changed. Numeric telemetry and explicit public
fixture answer artifacts are separate. Never imports the developer .env file.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

import httpx
import uvicorn

API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))
INVENTORY = Path(__file__).with_name("inventory.json")
MODEL = "qwen3.5:9b"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def percentile(values, quantile):
    """Nearest-rank percentile; no claim that a small-sample p95 is stable."""
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * quantile) - 1)] if values else None


def rates(call):
    def rate(count, ns):
        return count / (ns / 1e9) if count is not None and ns is not None and ns > 0 else None
    return {"generation_tokens_per_second": rate(call.get("eval_count"), call.get("eval_duration_ns")),
            "prompt_tokens_per_second": rate(call.get("prompt_eval_count"), call.get("prompt_eval_duration_ns"))}


def summarize(records):
    groups = {}
    for group in ("cold_two_pass", "warm_two_pass", "non_model", "incomplete_pipeline"):
        rows = [r for r in records if r["sample_group"] == group]
        walls = [r["trace"]["total_wall_ms"] for r in rows]
        phases = {name: percentile([r["trace"]["phases_ms"][name] for r in rows], .5)
                  for name in ("storage_read", "retrieval", "extractive_synthesis", "context_build", "draft", "revision", "validation", "store")}
        groups[group] = {"n": len(rows), "p50_ms": percentile(walls, .5), "p95_ms": percentile(walls, .95),
                         "phase_p50_ms": phases,
                         "successful_model_answers": sum(r["trace"].get("result_kind") == "model_answer" for r in rows),
                         "result_counts": {kind: sum(r["trace"].get("result_kind") == kind for r in rows)
                                           for kind in sorted({r["trace"].get("result_kind", "unknown") for r in rows})}}
    return groups


def memory_sample():
    """Numerical host observations, not patient/research data or a RAM estimate."""
    def command(args):
        try:
            return subprocess.check_output(args, text=True, timeout=3, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.SubprocessError):
            return None
    return {"at_monotonic_s": time.monotonic(),
            "pressure_level": command(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"]),
            "swap_usage": command(["sysctl", "-n", "vm.swapusage"]),
            "vm_stat": command(["vm_stat"])}


def frozen_store(path, inventory):
    from triallens.store import JsonStore
    data = {key: {} for key in ("workspaces", "sources", "chunks", "extractions", "answers", "briefs")}
    workspace_ids = {}
    for snapshot in inventory["snapshots"]:
        snapshot_path = INVENTORY.parent / snapshot["path"]
        if sha256(snapshot_path) != snapshot["sha256"]:
            raise ValueError("Frozen snapshot hash mismatch: " + snapshot["id"])
        content = json.loads(snapshot_path.read_text())
        workspace = content["workspace"]
        workspace_ids[snapshot["id"]] = workspace["id"]
        data["workspaces"][workspace["id"]] = workspace
        for key in ("sources", "chunks", "extractions"):
            data[key].update({item["id"]: item for item in content[key]})
    store = JsonStore(path)
    store._write(data)  # Offline fixture seeding only, before serving requests.
    return store, workspace_ids


class MetricsHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
    def emit(self, record):
        self.records.append(json.loads(record.getMessage()))


@contextmanager
def isolated_server(directory, inventory, digest, port=0):
    from triallens import main, conversation
    from triallens.performance import LOGGER
    settings = {"TRIALLENS_CHAT_PROVIDER": "ollama", "TRIALLENS_LOCAL_MODEL": MODEL,
                "TRIALLENS_USAGE_PATH": str(directory / "usage.sqlite3"),
                "TRIALLENS_PERF_TELEMETRY": "1", "TRIALLENS_PERF_MODEL_DIGEST": digest}
    previous_env = {key: os.environ.get(key) for key in settings}
    os.environ.update(settings)
    old_store = main.store
    old_post = conversation.httpx.post
    def local_only(url, *args, **kwargs):
        if url != "http://127.0.0.1:11434/api/chat":
            raise RuntimeError("Benchmark blocked unexpected provider destination")
        return old_post(url, *args, **kwargs)
    conversation.httpx.post = local_only
    handler = MetricsHandler()
    old_level, old_propagate = LOGGER.level, LOGGER.propagate
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    LOGGER.addHandler(handler)
    server = None
    thread = None
    sock = socket.socket()
    try:
        main.store, ids = frozen_store(directory / "workspaces.json", inventory)
        sock.bind(("127.0.0.1", port))
        config = uvicorn.Config(main.app, host="127.0.0.1", port=sock.getsockname()[1], access_log=False, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Isolated benchmark API did not start")
            time.sleep(.02)
        yield "http://127.0.0.1:" + str(config.port), ids, handler
    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=5)
        sock.close()
        if thread and thread.is_alive():
            # Never switch a still-running sync Ask back onto real data or billing.
            # The standalone benchmark must be stopped/drained before cleanup.
            raise RuntimeError("Isolated worker still running; real store/provider configuration was not restored")
        main.store = old_store
        conversation.httpx.post = old_post
        LOGGER.removeHandler(handler)
        LOGGER.setLevel(old_level)
        LOGGER.propagate = old_propagate
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def model_metadata():
    with httpx.Client(base_url="http://127.0.0.1:11434", trust_env=False, timeout=10) as client:
        version = client.get("/api/version").raise_for_status().json()["version"]
        models = client.get("/api/tags").raise_for_status().json()["models"]
        selected = next((m for m in models if m["name"] == MODEL), None)
        if not selected:
            raise RuntimeError("Required local baseline model is not installed")
        return {"ollama_version": version, "model_name": MODEL, "digest": selected["digest"], "details": selected.get("details", {})}


def model_cold_start():
    # Unload this model only; do not download, change settings, or clear OS caches.
    with httpx.Client(base_url="http://127.0.0.1:11434", trust_env=False, timeout=30) as client:
        client.post("/api/generate", json={"model": MODEL, "keep_alive": 0}).raise_for_status()
        loaded = client.get("/api/ps").raise_for_status().json().get("models", [])
        if loaded:
            raise RuntimeError("Models still loaded; cannot claim an uncontended cold baseline")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "docs/performance/results/baseline.json")
    parser.add_argument("--answers", type=Path, default=INVENTORY.parent / "results/baseline-answers.json")
    parser.add_argument("--case", action="append", help="Ordered case IDs; full inventory by default")
    parser.add_argument("--no-cold", action="store_true", help="Explicitly mark every model request warm/unknown rather than cold")
    parser.add_argument("--serve", type=int, metavar="PORT", help="Serve isolated fixture API for an additional browser/proxy timing check")
    args = parser.parse_args()
    inventory = json.loads(INVENTORY.read_text())
    selected = [case for case in inventory["cases"] if not args.case or case["id"] in args.case]
    if not selected or (args.case and (len(selected) != len(args.case) or len(args.case) != len(set(args.case)))):
        parser.error("Unknown or duplicate case ID")
    metadata = model_metadata()
    result = {"schema_version": 1, "release_status": "LOCAL BASELINE", "baseline_commit": "031ff95daa553d874a8c2ef36ab7b18ec96e0e0f",
              "fixture_inventory_sha256": sha256(INVENTORY), "pipeline_variant": "two_pass", "environment": metadata,
              "python_version": sys.version.split()[0],
              "instrumented_code_sha256": hashlib.sha256(b"".join((API_ROOT / "triallens" / name).read_bytes() for name in ["conversation.py", "main.py", "performance.py", "rag.py", "store.py"])).hexdigest(),
              "settings": {"think": False, "temperature": 0, "num_ctx": 16384, "num_predict": 1800, "keep_alive": "10m", "httpx_timeout_per_operation_s": 180},
              "method": {"boundary": "loopback HTTP API through actual FastAPI route, serialization and isolated persistence",
                         "p95": "nearest rank; small-sample estimate", "cold": "model unloaded; native Ollama server and OS file caches not restarted",
                         "token_counts": "Ollama final-response counts; no character-to-token conversion",
                         "context_truncation": "unknown until provider counts and native log observations are reviewed; character caps are not proof",
                         "store": "only frozen public snapshots, no production histories; smaller than developer store",
                         "paid_inference_api_calls": 0}, "requests": [], "summary": {}, "complete": False}
    answers, history_ids = [], {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.answers.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="triallens-m0-") as temporary:
        with isolated_server(Path(temporary), inventory, metadata["digest"], args.serve or 0) as (base, ids, handler):
            if args.serve:
                print(json.dumps({"event": "isolated_api_ready", "url": base, "case_workspace_ids": ids}), flush=True)
                try:
                    while True:
                        time.sleep(.2)
                        if handler.records:
                            args.output.write_text(json.dumps({"environment": metadata, "traces": handler.records}, indent=2))
                except KeyboardInterrupt:
                    return 0
            if not args.no_cold:
                model_cold_start()
            with httpx.Client(base_url=base, timeout=400, trust_env=False) as client:
                for index, case in enumerate(selected):
                    parent = case.get("history_case_id")
                    if parent and parent not in history_ids:
                        raise ValueError("Run predecessor case first: " + parent)
                    before_memory = memory_sample()
                    if before_memory["pressure_level"] == "4":
                        raise RuntimeError("Critical memory pressure; baseline stopped without tuning runtime")
                    start = time.monotonic()
                    count = len(handler.records)
                    response = client.post(f'/workspaces/{ids[case["snapshot_id"]]}/ask', json={
                        "question": case["question"], "source_types": case.get("source_types"), "previous_answer_id": history_ids.get(parent)})
                    client_ms = (time.monotonic() - start) * 1000
                    response.raise_for_status()
                    deadline = time.monotonic() + 2
                    while len(handler.records) == count and time.monotonic() < deadline:
                        time.sleep(.001)
                    if len(handler.records) != count + 1:
                        raise RuntimeError("Expected exactly one request-scoped trace")
                    trace = handler.records[-1]
                    for call in trace["model_calls"]:
                        call.update(rates(call))
                    answer = response.json()
                    history_ids[case["id"]] = answer["id"]
                    two_pass = len(trace["model_calls"]) == 2
                    group = ("cold_two_pass" if index == 0 and not args.no_cold else "warm_two_pass") if two_pass else "non_model" if not trace["model_calls"] else "incomplete_pipeline"
                    record = {"case_id": case["id"], "snapshot_id": case["snapshot_id"], "sample_group": group,
                              "client_wall_ms": client_ms, "trace": trace, "memory_before": before_memory, "memory_after": memory_sample()}
                    result["requests"].append(record)
                    result["summary"] = summarize(result["requests"])
                    answers.append({"case_id": case["id"], "snapshot_id": case["snapshot_id"], "answer": answer,
                                    "engineering_verdict": "not_reviewed", "critical_errors": [], "review_notes": []})
                    args.output.write_text(json.dumps(result, indent=2))
                    args.answers.write_text(json.dumps(answers, indent=2))
                    print(json.dumps({"case_id": case["id"], "sample_group": group, "wall_s": round(client_ms/1000, 2),
                                      "result_kind": trace["result_kind"], "fallback_reason": trace["fallback_reason"]}), flush=True)
            result["complete"] = True
            args.output.write_text(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
