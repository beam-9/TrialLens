"""Run a small, explicitly adjudicated local-generation regression set.

Run from the repository root with apps/api/.venv/bin/python apps/api/evaluation/run.py.
No workspaces or production usage counts are changed. Results require semantic review;
conversational mode is a structural check, never an accuracy score.
"""
from pathlib import Path
import argparse
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from triallens.conversation import ConversationService, chat_model
from triallens.models import Answer, EvidenceSource, SourceType, Workspace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', help='Run one case id')
    parser.add_argument('--output', default='/tmp/triallens-generation-evaluation.json')
    args = parser.parse_args()
    cases = json.loads(Path(__file__).with_name('cases.json').read_text())
    if args.case:
        cases = [case for case in cases if case['id'] == args.case]
        if not cases:
            parser.error('Unknown case id')
    os.environ['TRIALLENS_CHAT_PROVIDER'] = 'ollama'
    results = []
    with tempfile.TemporaryDirectory(prefix='triallens-eval-') as directory:
        os.environ['TRIALLENS_USAGE_PATH'] = str(Path(directory) / 'usage.sqlite3')
        for case in cases:
            workspace = Workspace(condition=case['condition'], intervention=case['intervention'], source_types=list(SourceType))
            sources = [EvidenceSource(workspace_id=workspace.id, **source) for source in case['sources']]
            for source in sources:
                if source.external_id.startswith('EVAL-'):
                    source.metadata['demo'] = True
            history = []
            for question in [case['question']] + ([case['follow_up']] if case.get('follow_up') else []):
                fallback = Answer(workspace_id=workspace.id, question=question, short_answer='Generation failed validation.', evidence=[], limitations=[], citations=[], retrieved_chunks=[])
                start = time.monotonic()
                answer = ConversationService().generate(workspace, question, history, sources, fallback)
                result = {'case':case['id'], 'model':chat_model(), 'question':question, 'seconds':round(time.monotonic()-start,1), 'mode':answer.generation_mode, 'answer':answer.direct_answer, 'uncertainty':answer.uncertainty, 'note':answer.generation_note, 'rubric':case['rubric'], 'semantic_verdict':'not_reviewed'}
                results.append(result)
                Path(args.output).write_text(json.dumps(results, indent=2))
                print(json.dumps(result), flush=True)
                history.append(answer)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
