"""Exercise follow-ups against a copy of an existing workspace, without changing it."""
from pathlib import Path
import argparse
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['TRIALLENS_CHAT_PROVIDER'] = 'ollama'
from triallens import main
from triallens.models import AskRequest
from triallens.store import JsonStore
from triallens.conversation import chat_model


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--intervention', default='metformin')
    parser.add_argument('--output', default='/tmp/triallens-workspace-evaluation.json')
    parser.add_argument('--question', action='append', help='Question to run; repeat for a follow-up chain')
    args = parser.parse_args()
    candidates = [w for w in main.store.list_workspaces() if w.intervention == args.intervention]
    if not candidates:
        parser.error('No matching existing workspace')
    workspace = max(candidates, key=lambda w: w.updated_at)
    results = []
    with tempfile.TemporaryDirectory(prefix='triallens-workspace-eval-') as directory:
        snapshot = Path(directory) / 'store.json'
        snapshot.write_bytes(main.store.path.read_bytes())
        main.store = JsonStore(snapshot)
        os.environ['TRIALLENS_USAGE_PATH'] = str(Path(directory)/'usage.sqlite3')
        previous = None
        for question in args.question or ['What does the evidence say about benefits and safety limitations?', 'Explain that more simply. What can we actually conclude?', 'Does this evidence show a reduction in mortality?']:
            start = time.monotonic()
            answer = main.ask(workspace.id, AskRequest(question=question, previous_answer_id=previous))
            result = {'workspace_id':workspace.id, 'condition':workspace.condition, 'intervention':workspace.intervention, 'model':chat_model(), 'question':question, 'seconds':round(time.monotonic()-start,1), 'mode':answer.generation_mode, 'answer':answer.direct_answer, 'uncertainty':answer.uncertainty, 'citations':answer.citations, 'note':answer.generation_note, 'semantic_verdict':'not_reviewed'}
            results.append(result)
            Path(args.output).write_text(json.dumps(results,indent=2))
            print(json.dumps(result),flush=True)
            previous = answer.id
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
