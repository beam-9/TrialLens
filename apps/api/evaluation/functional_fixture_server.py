"""Isolated browser integration fixture API. Never loads .env or calls a model.

Run with the API virtualenv, then serve the built frontend with
TRIALLENS_API_BASE=http://127.0.0.1:8002 on port 3002. Set
TRIALLENS_FUNCTIONAL_TESTS=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3002
for the browser test suite. Ctrl-C cleans up this server's temporary data/ledger.
The deterministic response tests application plumbing, not answer quality.
"""
import sys, os, json, tempfile, pathlib, copy
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'apps/api'))
sys.path.insert(0,str(ROOT/'apps/api/evaluation/m0'))
TEMP_DIRECTORY=tempfile.TemporaryDirectory(prefix='triallens-functional-')
TEMP=pathlib.Path(TEMP_DIRECTORY.name)
os.environ.update(TRIALLENS_CHAT_PROVIDER='cloudflare', CLOUDFLARE_ACCOUNT_ID='0'*32,CLOUDFLARE_API_TOKEN='mock-only',TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED='true',TRIALLENS_USAGE_PATH=str(TEMP/'usage.sqlite3'))
from triallens import main, conversation
from triallens.models import EvidenceSource
from benchmark import frozen_store, INVENTORY
main.store, ids=frozen_store(TEMP/'data.json',json.loads(INVENTORY.read_text()))
fixture=json.loads((INVENTORY.parent/'snapshots/filtered-control.json').read_text())
async def fetch(workspace, diagnostics=None):
    if diagnostics is not None: diagnostics.update({t.value:'ok' for t in workspace.source_types})
    records=[]
    for s in fixture['sources']:
        if s['source_type'] in [t.value for t in workspace.source_types]:
            s=copy.deepcopy(s); s['id']=workspace.id+'-'+s['source_type']; s['workspace_id']=workspace.id
            records.append(EvidenceSource(**s))
    return records
main.fetch_sources=fetch

def completion(messages,schema):
    payload=json.loads(messages[1]['content'])
    evidence=payload['evidence']; citation=evidence[0]['citation']
    with (TEMP/'provider-calls.jsonl').open('a') as f:
        f.write(json.dumps({'question':payload['question'],'citations':[e['citation'] for e in evidence],'history_count':len(payload['history']),'pass':'draft' if len(messages)==2 else 'revision'})+'\n')
    # A purpose-labelled deterministic plumbing response, never quality evidence.
    return json.dumps({'paragraphs':['This is a deterministic browser integration response using the selected evidence ['+citation+'].'],'cited_sources':[citation],'uncertainty':['Browser plumbing fixture only; no live inference was run.']})
conversation.cloudflare.completion=completion
# Fail closed: no provider or source network can be used accidentally.
def blocked(*a,**k): raise RuntimeError('Functional browser harness blocked outbound inference')
conversation.httpx.post=blocked
print(json.dumps({'temp':str(TEMP),'workspaces':ids}),flush=True)
import uvicorn
try:
    uvicorn.run(main.app,host='127.0.0.1',port=8002,log_level='warning')
finally:
    TEMP_DIRECTORY.cleanup()
