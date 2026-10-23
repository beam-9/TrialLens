"""Frozen public-fixture HTTP evaluation for the explicit hosted candidate.

Never invokes Ollama or OpenAI, never refreshes evidence, never uses production
workspace history/counters. Provider-account quotas still apply. No .env contents
or raw HTTP errors are printed; answers are explicit public-fixture artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import httpx
from dotenv import load_dotenv

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))
from m0 import benchmark
from triallens import cloudflare, conversation


def run(output, answer_path, case_ids=None):
    inventory = json.loads(benchmark.INVENTORY.read_text())
    selected = [c for c in inventory["cases"] if not case_ids or c["id"] in case_ids]
    if not selected or (case_ids and (len(case_ids) != len(set(case_ids)) or len(selected) != len(case_ids))):
        raise ValueError("Unknown or duplicate case ID")
    available = set()
    for case in selected:
        if case.get("history_case_id") and case["history_case_id"] not in available:
            raise ValueError("Include predecessor: " + case["history_case_id"])
        available.add(case["id"])
    if not cloudflare.configured():
        raise RuntimeError("Hosted setup is incomplete")
    if output.resolve() == answer_path.resolve():
        raise ValueError("Metrics and answers need different paths")
    if output.exists() or answer_path.exists():
        raise ValueError("Choose new result paths; existing observations are immutable")
    for path in (output, answer_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    protected = [API_ROOT / "data/triallens.json", Path(os.getenv("TRIALLENS_USAGE_PATH", str(API_ROOT / "data/usage.sqlite3")))]
    original_hashes = {p: benchmark.sha256(p) for p in protected if p.exists()}
    records, answers, history = [], [], {}
    result = {"schema_version": 1, "provider": "cloudflare", "model": cloudflare.MODEL,
              "pipeline_variant": "two_pass", "status": "HOSTED CANDIDATE; not pilot verified", "complete": False,
              "fixture_inventory_sha256": benchmark.sha256(benchmark.INVENTORY),
              "code_sha256": hashlib.sha256(b"".join((API_ROOT / "triallens" / name).read_bytes() for name in ("cloudflare.py", "conversation.py", "main.py", "performance.py", "rag.py", "store.py"))).hexdigest(),
              "method": {"boundary": "loopback HTTP Ask API including serialization; hosted inference",
                         "cold_warm": "provider cache/residency unknown; no cold/warm classification",
                         "paid_provider_fallbacks": 0, "local_model_calls": 0,
                         "tokens": "provider reported only; distinct tokenizer from native baseline",
                         "store": "isolated frozen public fixtures and temporary SQLite ledger",
                         "quota": "temporary evaluation ledger; free provider account hard quota still applies"},
              "requests": records, "summary": {}}
    native_post = conversation.httpx.post
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    endpoint = "https://api.cloudflare.com/client/v4/accounts/" + account + "/ai/run/" + cloudflare.MODEL
    def hosted_only(url, *args, **kwargs):
        if url != endpoint:
            raise RuntimeError("Evaluation blocked unexpected provider destination")
        return native_post(url, *args, **kwargs)
    with tempfile.TemporaryDirectory(prefix="triallens-cloudflare-") as temporary:
        # Reuse the proven frozen HTTP/store isolation seam, never its native
        # model metadata or cold-start controls. Override provider BEFORE Ask.
        with benchmark.isolated_server(Path(temporary), inventory, "") as (base, ids, handler):
            os.environ["TRIALLENS_CHAT_PROVIDER"] = "cloudflare"
            os.environ.pop("TRIALLENS_PERF_MODEL_DIGEST", None)
            conversation.httpx.post = hosted_only
            def persist():
                model_rows = [r for r in records if r["trace"]["result_kind"] == "model_answer"]
                result["summary"] = {"n": len(records), "model_answers": len(model_rows),
                                     "model_answer_p50_ms": benchmark.percentile([r["trace"]["total_wall_ms"] for r in model_rows], .5),
                                     "model_answer_p95_ms": benchmark.percentile([r["trace"]["total_wall_ms"] for r in model_rows], .95),
                                     "result_counts": {kind: sum(r["trace"]["result_kind"] == kind for r in records) for kind in sorted({r["trace"]["result_kind"] for r in records})}}
                result["quota"] = cloudflare.quota_status()
                output.write_text(json.dumps(result, indent=2) + "\n")
                answer_path.write_text(json.dumps(answers, indent=2) + "\n")
            with httpx.Client(base_url=base, trust_env=False, timeout=400) as client:
                for case in selected:
                    previous = case.get("history_case_id")
                    started = time.monotonic()
                    trace_index = len(handler.records)
                    response = client.post(f'/workspaces/{ids[case["snapshot_id"]]}/ask', json={"question": case["question"], "source_types": case.get("source_types"), "previous_answer_id": history.get(previous)})
                    client_ms = (time.monotonic() - started) * 1000
                    response.raise_for_status()
                    deadline = time.monotonic() + 2
                    while len(handler.records) == trace_index and time.monotonic() < deadline:
                        time.sleep(.001)
                    if len(handler.records) != trace_index + 1:
                        raise RuntimeError("Expected exactly one request-scoped trace")
                    trace = handler.records[-1]
                    answer = response.json()
                    history[case["id"]] = answer["id"]
                    records.append({"case_id": case["id"], "snapshot_id": case["snapshot_id"], "client_wall_ms": client_ms, "trace": trace})
                    answers.append({"case_id": case["id"], "snapshot_id": case["snapshot_id"], "answer": answer})
                    persist()
                    print(json.dumps({"case_id": case["id"], "wall_s": round(client_ms / 1000, 2), "result_kind": trace["result_kind"], "fallback_reason": trace["fallback_reason"]}), flush=True)
                    # Do not spend the rest of the allowance repeating setup/provider
                    # failures. Keep the failed output and report before retrying.
                    if str(trace.get("fallback_reason", "")).startswith("cloudflare_"):
                        result["stop_reason"] = trace["fallback_reason"]
                        break
                else:
                    result["complete"] = True
                result["isolation_verified"] = all(p.exists() and benchmark.sha256(p) == digest for p, digest in original_hashes.items())
                persist()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    load_dotenv(API_ROOT / ".env", override=False)
    result = run(args.output, args.answers, args.case)
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
