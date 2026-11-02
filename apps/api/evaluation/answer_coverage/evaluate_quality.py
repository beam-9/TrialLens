"""Explicit, quota-bounded evaluation of frozen quality cohorts; never production stores."""
from __future__ import annotations
import argparse
from contextlib import contextmanager, nullcontext
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
API_ROOT = ROOT.parents[1]
sys.path.insert(0, str(API_ROOT / 'evaluation'))
sys.path.insert(0, str(API_ROOT))
from dotenv import load_dotenv
import cloudflare_run
from revision_feedback import revision_feedback_experiment



@contextmanager
def reasoning_effort_experiment(effort: str | None):
    """Temporarily vary native GPT-OSS reasoning before its exact reservation.

    This standalone evaluation seam mutates only a request-local payload. The
    same payload then reaches the real reserve function and HTTP capture seam;
    production defaults and source/prompt/validation behavior stay unchanged.
    """
    if effort is None:
        yield
        return
    if effort not in ("low", "medium", "high"):
        raise ValueError("Reasoning experiment must be low, medium or high")
    cloudflare = cloudflare_run.cloudflare
    if cloudflare.MODEL != "@cf/openai/gpt-oss-120b":
        raise ValueError("Reasoning experiment requires native GPT-OSS-120B")
    original = cloudflare._reserve

    def reserve(payload):
        if (cloudflare.MODEL != "@cf/openai/gpt-oss-120b"
                or not isinstance(payload, dict) or not isinstance(payload.get("input"), list)
                or "messages" in payload or "max_tokens" in payload or "response_format" in payload
                or type(payload.get("max_output_tokens")) is not int or payload["max_output_tokens"] <= 0
                or not isinstance(payload.get("reasoning"), dict)
                or payload["reasoning"].get("effort") not in ("low", "medium", "high")):
            raise ValueError("Reasoning experiment requires the native Responses request profile")
        payload["reasoning"] = {**payload["reasoning"], "effort": effort}
        return original(payload)

    with patch.object(cloudflare, "_reserve", reserve):
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=cloudflare_run.benchmark.INVENTORY)
    parser.add_argument('--cases-file', type=Path)
    parser.add_argument('--case', action='append')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--answers', type=Path, required=True)
    parser.add_argument('--prompt-file', type=Path)
    parser.add_argument('--revision-feedback', action='store_true')
    parser.add_argument('--numeric-checks', action='store_true')
    parser.add_argument('--model-experiment', choices=sorted(cloudflare_run.MODEL_EXPERIMENTS))
    parser.add_argument('--reasoning-effort', choices=('low', 'medium', 'high'))
    parser.add_argument('--strategy-experiment', choices=('verified-quotes', 'reviewed-claims', 'repaired-claims', 'outcome-claims'))
    args = parser.parse_args()
    if args.numeric_checks and args.strategy_experiment:
        parser.error('--numeric-checks applies to the prose writer, not a claim-review schema')
    load_dotenv(API_ROOT / '.env', override=False)
    experiment = revision_feedback_experiment(numeric_guard=args.numeric_checks) if args.revision_feedback or args.numeric_checks else nullcontext()
    # Wrapping restores both the inventory and provider seam even on failures.
    with patch.object(cloudflare_run.benchmark, 'INVENTORY', args.inventory.resolve()), experiment, cloudflare_run.candidate_model(args.model_experiment), reasoning_effort_experiment(args.reasoning_effort):
        result = cloudflare_run.run(args.output, args.answers, args.case,
            quota_path=API_ROOT / 'data/evaluation-usage.sqlite3',
            prompt_path=args.prompt_file, cases_path=args.cases_file, strategy=args.strategy_experiment)
    result['quality_experiment'] = {
        'revision_feedback': args.revision_feedback,
        'numeric_checks': args.numeric_checks,
        'numeric_checks_sha256': hashlib.sha256((API_ROOT / 'evaluation/numeric_checks.py').read_bytes()).hexdigest() if args.numeric_checks else None,
        'strategy_experiment': args.strategy_experiment,
        'model_experiment': args.model_experiment,
        'reasoning_effort': args.reasoning_effort,
        'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'feedback_sha256': hashlib.sha256((ROOT / 'revision_feedback.py').read_bytes()).hexdigest(),
        'inventory_path': str(args.inventory),
    }
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
