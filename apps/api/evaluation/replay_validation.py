"""Replay retained public-fixture outputs through current Ask validation, offline.

This measures acceptance by deterministic safeguards, not semantic correctness or
the performance of a one-pass pipeline. No provider requests or usage writes run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
from m0 import benchmark
from triallens import cloudflare, conversation, main
from triallens.models import Answer, AskRequest
from triallens.usage import UsageLedger


def run(input_path: Path, output_path: Path):
    if output_path.exists() or input_path.resolve() == output_path.resolve():
        raise ValueError("Choose a new output path; retained observations are immutable")
    inventory = json.loads(benchmark.INVENTORY.read_text())
    cases = {case["id"]: case for case in inventory["cases"]}
    originals = json.loads(input_path.read_text())
    by_case = {item["case_id"]: item for item in originals}
    if len(by_case) != len(originals) or not by_case.keys() <= cases.keys():
        raise ValueError("Unknown or duplicate case ID")
    observations = []
    with tempfile.TemporaryDirectory(prefix="triallens-validation-replay-") as temporary:
        directory = Path(temporary)
        store, ids = benchmark.frozen_store(directory / "workspaces.json", inventory)
        for item in originals:
            store.save_answer(Answer.model_validate(item["answer"]))
        settings = {"TRIALLENS_CHAT_PROVIDER": "cloudflare", "TRIALLENS_USAGE_PATH": str(directory / "usage.sqlite3")}
        with (patch.dict(os.environ, settings), patch.object(main, "store", store),
              patch.object(conversation, "chat_configured", return_value=True),
              patch.object(UsageLedger, "free_answer", return_value=None),
              patch.object(conversation.httpx, "post", side_effect=AssertionError("Offline replay forbids HTTP"))):
            for item in originals:
                case = cases[item["case_id"]]
                for index, candidate in enumerate(item.get("provider_outputs", [])):
                    content = candidate.get("response")
                    if content is None:
                        continue
                    content = json.dumps(content) if isinstance(content, dict) else content
                    previous = by_case.get(case.get("history_case_id"), {}).get("answer")
                    if case.get("history_case_id") and previous is None:
                        raise ValueError("Missing retained predecessor")
                    payload = AskRequest(question=case["question"], source_types=case.get("source_types"),
                                         previous_answer_id=previous["id"] if previous else None)
                    # Returning the same recorded output twice exercises current
                    # final validation without manufacturing a new model revision.
                    with patch.object(cloudflare, "completion", return_value=content) as completion:
                        answer = main.ask(ids[case["snapshot_id"]], payload)
                    observations.append({"case_id": case["id"], "stage": "draft" if index == 0 else "revision",
                                         "accepted": answer.generation_mode == "conversational",
                                         "generation_note": answer.generation_note,
                                         "mock_completion_calls": completion.call_count})
        if (directory / "usage.sqlite3").exists():
            raise AssertionError("Offline replay unexpectedly wrote usage")
    result = {"schema_version": 1, "method": "Deterministic final-validation replay, not a new generation or semantic adjudication",
              "input_sha256": benchmark.sha256(input_path), "inventory_sha256": benchmark.sha256(benchmark.INVENTORY),
              "validation_code_sha256": hashlib.sha256((API_ROOT / "triallens/conversation.py").read_bytes()).hexdigest(),
              "provider_requests": 0, "local_model_calls": 0, "production_mutations": 0,
              "observations": observations,
              "summary": {stage: {"n": sum(row["stage"] == stage for row in observations),
                                   "accepted": sum(row["stage"] == stage and row["accepted"] for row in observations)}
                          for stage in ("draft", "revision")}}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output)["summary"]))
