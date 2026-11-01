"""Build a public paired design diagnostic without touching production or M0."""
import asyncio, hashlib, json, sys
from pathlib import Path
from unittest.mock import patch
import httpx
API = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(API))
from triallens.models import Workspace, SourceType
from triallens.rag import build_chunks, build_extractions
from triallens.sources import ClinicalTrialsClient
ROOT = Path(__file__).resolve().parent
STAMP = '2026-10-31T00:00:00+00:00'


def build(directory):
    directory.mkdir(exist_ok=False)
    fixture=ROOT/'fixtures/ctgov-NCT00545844-2026-10-31.json'
    study=json.loads(fixture.read_text())
    snapshots,cases=[],[]
    for kind in ('without-design','with-design'):
        w=Workspace(id='design-'+kind,condition='asthma',intervention='inhaled corticosteroids',source_types=[SourceType.clinical_trials],created_at=STAMP,updated_at=STAMP)
        native=httpx.AsyncClient
        with patch('triallens.sources.httpx.AsyncClient',lambda **kwargs:native(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'studies':[study]})),**kwargs)):
            s=asyncio.run(ClinicalTrialsClient().fetch(w))[0]
        s.id,s.created_at='source-'+kind,STAMP
        if kind=='without-design':
            s.metadata.pop('registry_design',None);s.metadata['sections'].pop('Study design',None)
        chunks,rows=build_chunks([s]),build_extractions([s],w)
        for i,c in enumerate(chunks):c.id=f'{kind}-chunk-{i}'
        for i,r in enumerate(rows):r.id=f'{kind}-row-{i}'
        data={'workspace':w.model_dump(mode='json'),'sources':[s.model_dump(mode='json')],'chunks':[c.model_dump(mode='json') for c in chunks],'extractions':[r.model_dump(mode='json') for r in rows]}
        path=directory/(kind+'.json');path.write_text(json.dumps(data,indent=2)+'\n')
        snapshots.append({'id':kind,'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        cases.extend([{'id':kind+'-statistics','snapshot_id':kind,'question':'For NCT00545844, what were the asthma control results at baseline and week 8? Give the counts and denominators, explain which treatment was studied and what the comparison can tell us.','must_include':['Baseline uncontrolled312/313, controlled0, missing1; week8 uncontrolled72/301, controlled229, missing0','Montelukast add-on, not an isolated ICS effect','Different denominators and visit comparison; design claims require explicit design evidence'],'must_not_claim':['ACQ pvalue applies to categorical counts','Calculated percentages are reported values','Source-wide control absence without explicit design'],'expected_route':'generated'}, {'id':kind+'-followup','snapshot_id':kind,'history_case_id':kind+'-statistics','question':'Explain that more simply. Keep the key numbers and the main limitation.','must_include':['Same counts/denominators','Treatment and comparison limitation','Simpler than prior answer'],'must_not_claim':['Invented percentages','Causal proof','Drop key numbers or limitation'],'expected_route':'generated'}])
    inventory={'schema_version':1,'purpose':'Paired design availability diagnostic; not clinical validation or M0 replacement','public_payload_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'snapshots':snapshots,'cases':cases}
    (directory/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    (directory/'README.md').write_text('# Paired study-design diagnostic\n\nSame public NCT00545844 payload; only explicit registry design metadata and its indexed section differ. Outcome values are identical. IDs are aliases; no saved researcher answers/briefs/reviews copied. Existing cohorts are unchanged.\n\nRegistered enrollment is not necessarily an outcome denominator. N/A allocation alone does not establish no control; this payload explicitly reports NON_RANDOMIZED and SINGLE_GROUP. Small authored diagnostic, not clinical validation.\n')
    return inventory

if __name__=='__main__':
    result=build(Path(sys.argv[1]));print({'snapshots':len(result['snapshots']),'cases':len(result['cases'])})
