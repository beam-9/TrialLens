"""Build an isolated before/after cohort from the frozen public trial payload.

No network, inference, production store or existing M0 snapshot is touched.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

API_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(API_ROOT))
import httpx
from triallens.models import Workspace, SourceType
from triallens.rag import build_chunks, build_extractions
from triallens.sources import ClinicalTrialsClient

ROOT = Path(__file__).resolve().parent
STAMP = '2026-10-29T00:00:00+00:00'


def build(directory):
    directory.mkdir(exist_ok=False)
    fixture = ROOT / 'fixtures/ctgov-NCT01563029-2026-10-28.json'
    study = json.loads(fixture.read_text())
    snapshots = []
    for kind in ('protocol', 'posted-results'):
        workspace = Workspace(id='packet-' + kind, condition='asthma', intervention='fluticasone furoate',
                              source_types=[SourceType.clinical_trials], created_at=STAMP, updated_at=STAMP)
        original = httpx.AsyncClient
        with patch('triallens.sources.httpx.AsyncClient', lambda **kwargs: original(
                transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'studies': [study]})), **kwargs)):
            source = asyncio.run(ClinicalTrialsClient().fetch(workspace))[0]
        source.id, source.created_at = 'source-' + kind, STAMP
        if kind == 'protocol':
            source.metadata['sections'] = {k: v for k, v in source.metadata['sections'].items() if not k.startswith('Results outcome ')}
            source.metadata['indexed_content'] = 'protocol_descriptions'
            source.metadata.pop('outcome_packet_version', None)
            source.metadata.pop('results_indexing', None)
        chunks = build_chunks([source])
        for index, chunk in enumerate(chunks):
            chunk.id = f'{kind}-chunk-{index:03}'
        extractions = build_extractions([source], workspace)
        for index, extraction in enumerate(extractions):
            extraction.id = f'{kind}-extraction-{index:03}'
        data = {'workspace': workspace.model_dump(), 'sources': [source.model_dump()],
                'chunks': [c.model_dump() for c in chunks], 'extractions': [e.model_dump() for e in extractions]}
        path = directory / (kind + '.json')
        path.write_text(json.dumps(data, indent=2) + '\n')
        snapshots.append({'id': kind, 'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    question = ('For FF 50 micrograms once daily versus placebo in this trial, give the primary morning PEF '
                'result over 12 weeks, including each group\'s change, analyzed group sizes and the reported '
                'between-group estimate and confidence interval. Explain what the comparison means.')
    cases = [
        {'id': 'protocol-statistics', 'snapshot_id': 'protocol', 'question': question,
         'must_include': ['Scoped gap: protocol description alone does not supply measured primary-outcome results'],
         'must_not_claim': ['Planned enrolment is an outcome result', 'invented values'], 'expected_route': 'generated'},
        {'id': 'posted-statistics', 'snapshot_id': 'posted-results', 'question': question,
         'must_include': ['FF50 once daily change22.8 vs placebo3.3 L/min', 'analyzed n118 vs119',
                          'reported contrast19.5 L/min CI12.1to26.9 at95%', '12-week primary AMPEF outcome',
                          'No class-wide efficacy or superiority to other doses inferred'],
         'must_not_claim': ['19.5 is within-group change', 'Pooled FF50/100 analysis used for FF50 alone',
                            'CI excludeszero means certainty or probability', 'clinical significance invented'], 'expected_route': 'generated'},
        {'id': 'posted-simplify', 'snapshot_id': 'posted-results', 'history_case_id': 'posted-statistics',
         'question': 'Explain that more simply, keeping the key numerical comparison and what it does and does not tell us.',
         'must_include': ['Same FF50/placebo primary outcome, units and12weeks', '19.5 L/min groupdifference',
                          'Retain relevant uncertainty without claiming other outcomes notmeasured'],
         'must_not_claim': ['Universal asthma improvement', 'new endpoint', 'CI as probability'], 'expected_route': 'generated'},
        {'id': 'posted-unreported', 'snapshot_id': 'posted-results',
         'question': 'Do these indexed outcome measurements establish that FF50 reduces the risk of death?',
         'must_include': ['Not established by supplied outcome measurements', 'Source/excerpt scope only'],
         'must_not_claim': ['Mortality definitely not measured in entire trial', 'Proves mortalitybenefit', 'Unrelated prescribing advice'],
         'expected_route': 'generated'},
    ]
    inventory = {'schema_version': 1, 'purpose': 'Frozen public posted-results packet diagnostic, not clinical validation',
                 'public_payload_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(), 'snapshots': snapshots, 'cases': cases}
    (directory / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    return inventory


if __name__ == '__main__':
    print(json.dumps({'cases': len(build(ROOT / 'packet-cohort-2026-10-29')['cases']), 'inference_calls': 0}))
