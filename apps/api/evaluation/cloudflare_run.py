"""Frozen public-fixture HTTP evaluation for the explicit hosted candidate.

Never invokes Ollama or OpenAI, never refreshes evidence, never uses production
workspace history/counters. CLI experiments share a persistent evaluation ledger;
provider-account quotas still apply. No .env contents
or raw HTTP errors are printed; answers are explicit public-fixture artifacts.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
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

# Evaluation-only allowlist. Rates are integer micro-neurons per token, from
# https://developers.cloudflare.com/workers-ai/platform/pricing/ (2026-10-24).
# All candidates share the existing daily ledger; no provider/paid fallback.
MODEL_EXPERIMENTS = {
    "@cf/qwen/qwen3-30b-a3b-fp8": (4625, 30475),
    "@cf/openai/gpt-oss-120b": (31818, 68182),
    "@cf/zai-org/glm-4.7-flash": (5500, 36400),
}


@contextmanager
def candidate_model(name):
    previous = cloudflare.MODEL, cloudflare.INPUT_RATE, cloudflare.OUTPUT_RATE, cloudflare.MAX_OUTPUT_TOKENS
    try:
        if name is not None:
            if name not in MODEL_EXPERIMENTS:
                raise ValueError("Model experiment is not allowlisted")
            cloudflare.MODEL = name
            cloudflare.INPUT_RATE, cloudflare.OUTPUT_RATE = MODEL_EXPERIMENTS[name]
            # This model's output budget includes reasoning. Retain truncation
            # rejection; reserve its larger bounded allowance before dispatch.
            if name == "@cf/openai/gpt-oss-120b":
                cloudflare.MAX_OUTPUT_TOKENS = 4096
        yield
    finally:
        cloudflare.MODEL, cloudflare.INPUT_RATE, cloudflare.OUTPUT_RATE, cloudflare.MAX_OUTPUT_TOKENS = previous


@contextmanager
def candidate_instructions(path):
    previous = conversation.INSTRUCTIONS, conversation.REVISION_INSTRUCTIONS
    try:
        if path is not None:
            candidate = json.loads(path.read_text())
            if (not isinstance(candidate, dict) or set(candidate) != {"instructions", "revision_instructions"}
                    or any(not isinstance(value, str) or not value.strip() or len(value) > 20000 for value in candidate.values())):
                raise ValueError("Candidate must supply two nonempty instruction strings")
            conversation.INSTRUCTIONS = candidate["instructions"]
            conversation.REVISION_INSTRUCTIONS = candidate["revision_instructions"]
        yield
    finally:
        conversation.INSTRUCTIONS, conversation.REVISION_INSTRUCTIONS = previous


def run(output, answer_path, case_ids=None, quota_path=None, prompt_path=None, cases_path=None):
    inventory = json.loads(benchmark.INVENTORY.read_text())
    if cases_path is not None:
        # New questions share the original hash-checked source snapshots. Never
        # rewrite the frozen benchmark or replace evidence to fit a candidate.
        extra = json.loads(cases_path.read_text())
        cases = extra.get("cases") if isinstance(extra, dict) else None
        snapshots = {item["id"] for item in inventory["snapshots"]}
        if (not isinstance(cases, list) or not cases
                or any(not isinstance(case, dict)
                       or not isinstance(case.get("id"), str) or not case["id"].strip()
                       or not isinstance(case.get("snapshot_id"), str)
                       or case.get("snapshot_id") not in snapshots
                       or not isinstance(case.get("question"), str) or not 3 <= len(case["question"].strip()) <= 500
                       for case in cases)
                or len({case["id"] for case in cases}) != len(cases)):
            raise ValueError("Question inventory must use unique IDs and existing frozen snapshots")
        inventory = {**inventory, "cases": cases}
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
    if quota_path is not None:
        quota_path = quota_path.resolve()
        if quota_path in {p.resolve() for p in protected} or quota_path in {output.resolve(), answer_path.resolve()}:
            raise ValueError("Evaluation quota ledger must be separate from production data and outputs")
    records, answers, history = [], [], {}
    result = {"schema_version": 1, "provider": "cloudflare", "model": cloudflare.MODEL,
              "pipeline_variant": "two_pass", "status": "HOSTED CANDIDATE; not pilot verified", "complete": False,
              "fixture_inventory_sha256": benchmark.sha256(benchmark.INVENTORY),
              "runner_sha256": benchmark.sha256(Path(__file__)),
              "question_inventory_sha256": benchmark.sha256(cases_path) if cases_path else None,
              "candidate_prompt_sha256": benchmark.sha256(prompt_path) if prompt_path else None,
              "code_sha256": hashlib.sha256(b"".join((API_ROOT / "triallens" / name).read_bytes() for name in ("cloudflare.py", "conversation.py", "main.py", "performance.py", "rag.py", "store.py"))).hexdigest(),
              "model_rates": {"input_micro_neurons_per_token": cloudflare.INPUT_RATE,
                              "output_micro_neurons_per_token": cloudflare.OUTPUT_RATE,
                              "max_output_tokens": cloudflare.MAX_OUTPUT_TOKENS},
              "method": {"boundary": "loopback HTTP Ask API including serialization; hosted inference",
                         "cold_warm": "provider cache/residency unknown; no cold/warm classification",
                         "paid_provider_fallbacks": 0, "local_model_calls": 0,
                         "tokens": "provider reported only; distinct tokenizer from native baseline",
                         "store": "isolated frozen public fixtures; separate evaluation SQLite ledger",
                         "quota": "persistent evaluation ledger" if quota_path else "temporary test ledger; not for repeated live experiments"},
              "requests": records, "summary": {}}
    native_post = conversation.httpx.post
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    endpoint = "https://api.cloudflare.com/client/v4/accounts/" + account + "/ai/run/" + cloudflare.MODEL
    case_outputs = []
    case_context = {}
    def hosted_only(url, *args, **kwargs):
        if url != endpoint:
            raise RuntimeError("Evaluation blocked unexpected provider destination")
        # This seam runs only with a hash-checked public frozen store. Capture
        # the exact evidence/history object sent, never URL/auth/header values.
        context_text = kwargs["json"]["messages"][1]["content"]
        context_digest = hashlib.sha256(context_text.encode("utf-8")).hexdigest()
        if not case_context:
            case_context.update(value=json.loads(context_text), sha256=context_digest)
        elif context_digest != case_context["sha256"]:
            raise RuntimeError("Evaluation source context unexpectedly changed between passes")
        response = native_post(url, *args, **kwargs)
        # Public frozen fixtures only: retain draft/revision text to diagnose
        # validation failures without logging credentials or HTTP headers.
        try:
            body = response.json()
            candidate = body.get("result", {}) if isinstance(body, dict) else {}
            try:
                final_content = cloudflare.response_content(candidate)
            except (ValueError, TypeError, AttributeError):
                final_content = None
            case_outputs.append({"response": final_content, "usage": candidate.get("usage"),
                                 "generation_context_sha256": context_digest,
                                 "request_options": {key: kwargs["json"][key] for key in ("max_tokens", "chat_template_kwargs") if key in kwargs["json"]},
                                 "response_shape": {"result_keys": sorted(candidate),
                                                    "finish_reason": candidate.get("finish_reason"),
                                                    "status": candidate.get("status"),
                                                    "choice_finish_reasons": [c.get("finish_reason") for c in candidate.get("choices", []) if isinstance(c, dict)],
                                                    "output_types": [c.get("type") for c in candidate.get("output", []) if isinstance(c, dict)]}})
        except (ValueError, TypeError, AttributeError):
            case_outputs.append({"response": None, "usage": None})
        return response
    with candidate_instructions(prompt_path), tempfile.TemporaryDirectory(prefix="triallens-cloudflare-") as temporary:
        # Reuse the proven frozen HTTP/store isolation seam, never its native
        # model metadata or cold-start controls. Override provider BEFORE Ask.
        with benchmark.isolated_server(Path(temporary), inventory, "") as (base, ids, handler):
            os.environ["TRIALLENS_CHAT_PROVIDER"] = "cloudflare"
            if quota_path is not None:
                os.environ["TRIALLENS_USAGE_PATH"] = str(quota_path)
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
                    case_outputs.clear()
                    case_context.clear()
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
                    answers.append({"case_id": case["id"], "snapshot_id": case["snapshot_id"], "answer": answer,
                                    "provider_outputs": list(case_outputs),
                                    "generation_context": case_context.get("value"),
                                    "generation_context_sha256": case_context.get("sha256")})
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
    parser.add_argument("--quota-ledger", type=Path, default=API_ROOT / "data/evaluation-usage.sqlite3",
                        help="Persistent evaluation-only daily allowance shared across experiments")
    parser.add_argument("--prompt-file", type=Path, help="Evaluate a candidate without changing production instructions")
    parser.add_argument("--cases-file", type=Path, help="Independent questions using the unchanged frozen source snapshots")
    parser.add_argument("--model-experiment", choices=sorted(MODEL_EXPERIMENTS), help="Isolated Cloudflare model experiment; production default is unchanged")
    args = parser.parse_args()
    load_dotenv(API_ROOT / ".env", override=False)
    with candidate_model(args.model_experiment):
        result = run(args.output, args.answers, args.case, args.quota_ledger, args.prompt_file, args.cases_file)
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
