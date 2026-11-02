"""No-inference integration for narrow, complete registry count answers."""
import json
from pathlib import Path
import pytest
from triallens import conversation
from triallens.models import Answer,EvidenceSource,RetrievedChunk,SourceType,Workspace
from triallens.trial_results import parse_outcome_measures
from triallens.trial_design import parse_registry_design
from triallens.text import normalize

QUESTION='For NCT00545844, what were the Asthma Control results at baseline and week 8? Give counts and denominators, explain which treatment was studied and what the comparison can tell us.'


def context():
    study=json.loads((Path(__file__).resolve().parents[1]/'evaluation/answer_coverage/fixtures/ctgov-NCT00545844-2026-10-31.json').read_text())
    packets,_=parse_outcome_measures(study['resultsSection'])
    w=Workspace(condition='asthma',intervention='inhaled corticosteroids',source_types=[SourceType.clinical_trials])
    s=EvidenceSource(workspace_id=w.id,source_type=SourceType.clinical_trials,external_id='NCT00545844',title=study['protocolSection']['identificationModule']['briefTitle'],
        abstract=study['protocolSection']['descriptionModule']['briefSummary'],metadata={'outcome_packet_version':1,'registry_design':parse_registry_design(study['protocolSection']['designModule']),
        'sections':{'Brief summary':study['protocolSection']['descriptionModule']['briefSummary'],**packets}})
    c=RetrievedChunk(chunk_id='primary',source_id=s.id,source_type=s.source_type,citation='ClinicalTrials.gov:NCT00545844',text=normalize(packets['Results outcome 001']),section='Results outcome 001',score=1)
    return w,s,c


def fallback(w,c,q):
    return Answer(workspace_id=w.id,question=q,short_answer='fallback',evidence=[],limitations=[],citations=[],retrieved_chunks=[c])


@pytest.fixture
def no_provider(monkeypatch):
    monkeypatch.setenv('TRIALLENS_CHAT_PROVIDER','cloudflare')
    monkeypatch.setattr(conversation,'chat_configured',lambda:False)
    monkeypatch.setattr(conversation.cloudflare,'completion',lambda *args:pytest.fail('Reported data must not invoke inference'))
    monkeypatch.setattr(conversation,'UsageLedger',lambda:pytest.fail('No inference budget should be touched'))


def test_complete_count_answer_without_model_or_configuration(no_provider):
    w,s,c=context()
    answer=conversation.ConversationService().generate(w,QUESTION,[],[s],fallback(w,c,QUESTION))
    assert answer.generation_mode=='extractive' and 'No AI inference' in answer.generation_note
    assert all(value in answer.direct_answer for value in ('312','313','72','301','229','Missing: 1','Controlled: 0'))
    assert 'nonrandomized' in answer.direct_answer and 'do not establish' in answer.direct_answer
    assert answer.citations==[c.citation] and answer.retrieved_chunks==[c]
    assert any(item.value=='Reported statistics' for item in answer.answer_trace)


def test_simplify_preserves_counts_and_source_scope(no_provider):
    w,s,c=context()
    first=conversation.ConversationService().generate(w,QUESTION,[],[s],fallback(w,c,QUESTION))
    q='Can you explain that more simply, keeping the key numbers and main limitation?'
    simple=conversation.ConversationService().generate(w,q,[first],[s],fallback(w,c,q))
    assert 'No AI inference' in simple.generation_note
    assert all(value in simple.direct_answer for value in ('312','313','72','301','229','Missing: 1'))
    assert len(simple.direct_answer)<len(first.direct_answer)


@pytest.mark.parametrize('q',['What about mortality?', 'Explain that more simply for NCT01563029.', 'Give those counts by race.', 'Explain those counts for younger children more simply.',
    'Give Asthma Control counts at baseline and week 8 for children in NCT00545844.',
    'Explain Asthma Control Questionnaire (ACQ) counts at baseline and week 8 in NCT00545844.'])
def test_new_outcome_or_population_does_not_inherit_table(no_provider,q):
    w,s,c=context()
    previous=conversation.ConversationService().generate(w,QUESTION,[],[s],fallback(w,c,QUESTION))
    answer=conversation.ConversationService().generate(w,q,[previous],[s],fallback(w,c,q))
    assert answer.direct_answer!='' or answer.short_answer=='fallback'
    assert 'No AI inference' not in answer.generation_note
    assert '312' not in answer.direct_answer


def test_personal_decision_guard_precedes_reported_data(no_provider):
    w,s,c=context();q='Should I start inhaled corticosteroids? '+QUESTION
    answer=conversation.ConversationService().generate(w,q,[],[s],fallback(w,c,q))
    assert 'as an individual' in answer.direct_answer and not answer.citations


def test_repeated_simple_followups_keep_validated_original_request(no_provider):
    w,s,c=context()
    first=conversation.ConversationService().generate(w,QUESTION,[],[s],fallback(w,c,QUESTION))
    q='Explain that more simply, keeping the numbers.'
    second=conversation.ConversationService().generate(w,q,[first],[s],fallback(w,c,q))
    third=conversation.ConversationService().generate(w,q,[first,second],[s],fallback(w,c,q))
    assert 'No AI inference' in third.generation_note
    assert 'Missing: 1' in third.direct_answer
