"""Explicit, quota-bounded evaluation of frozen quality cohorts; never production stores."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=cloudflare_run.benchmark.INVENTORY)
    parser.add_argument('--cases-file', type=Path)
    parser.add_argument('--case', action='append')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--answers', type=Path, required=True)
    parser.add_argument('--prompt-file', type=Path)
    parser.add_argument('--revision-feedback', action='store_true')
    parser.add_argument('--model-experiment', choices=sorted(cloudflare_run.MODEL_EXPERIMENTS))
    args = parser.parse_args()
    load_dotenv(API_ROOT / '.env', override=False)
    experiment = revision_feedback_experiment() if args.revision_feedback else nullcontext()
    # Wrapping restores both the inventory and provider seam even on failures.
    with patch.object(cloudflare_run.benchmark, 'INVENTORY', args.inventory.resolve()), experiment, cloudflare_run.candidate_model(args.model_experiment):
        result = cloudflare_run.run(args.output, args.answers, args.case,
            quota_path=API_ROOT / 'data/evaluation-usage.sqlite3',
            prompt_path=args.prompt_file, cases_path=args.cases_file)
    result['quality_experiment'] = {
        'revision_feedback': args.revision_feedback,
        'model_experiment': args.model_experiment,
        'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'feedback_sha256': hashlib.sha256((ROOT / 'revision_feedback.py').read_bytes()).hexdigest(),
        'inventory_path': str(args.inventory),
    }
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
