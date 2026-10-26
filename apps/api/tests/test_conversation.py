import json

import httpx
import pytest

from triallens.conversation import ConversationService, retrieval_question
from triallens.models import Answer, EvidenceSource, SourceType, Workspace


@pytest.fixture
def context(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("TRIALLENS_CHAT_MODEL", "gpt-4.1-mini")
    workspace = Workspace(condition="diabetes", source_types=[SourceType.pubmed])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
                            external_id="123", title="Trial results", abstract="The intervention reduced HbA1c by 0.5 percentage points versus placebo at 12 weeks.")
    fallback = Answer(workspace_id=workspace.id, question="What changed?", short_answer="Extracted result",
                      evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    return workspace, source, fallback


def mock_generation(monkeypatch, output, status="completed"):
    captured = []
    def post(url, **kwargs):
        captured.append(kwargs["json"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={"status": status,
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(output)}]}]})
    monkeypatch.setattr("triallens.conversation.httpx.post", post)
    return captured


def test_conversational_generation_preserves_history_and_provenance(monkeypatch, context):
    workspace, source, fallback = context
    captured = mock_generation(monkeypatch, {"paragraphs": ["At 12 weeks, HbA1c was 0.5 percentage points lower than with placebo [PubMed:123]."], "cited_sources": ["PubMed:123"], "uncertainty": ["Longer-term outcomes are not available."]})
    result = ConversationService().generate(workspace, "Explain that result", [fallback], [source], fallback)
    assert result.generation_mode == "conversational"
    assert result.citations == ["PubMed:123"]
    assert captured[0]["store"] is False
    payload = json.loads(captured[0]["input"])
    assert payload["history"][0]["question"] == "What changed?"
    assert payload["evidence"][0]["citation"] == "PubMed:123"


@pytest.mark.parametrize("abstain", [False, True])
def test_final_attribution_replaces_extractive_support_judgments(monkeypatch, context, abstain):
    from triallens.models import AnswerTraceItem, RetrievedChunk
    workspace, source, fallback = context
    other = source.model_copy(update={"id": "other", "external_id": "456", "title": "Other retrieved record"})
    stale = "STALE extractive claim: PubMed:456 directly supported the answer"
    for field in ("evidence", "supporting_evidence", "evidence_synthesis", "reasoning_summary", "evidence_map", "source_readouts", "evidence_quality", "facet_coverage", "safety_limitations", "limitations"):
        setattr(fallback, field, [stale])
    fallback.answer_trace = [AnswerTraceItem(label="Old selection", value=stale)]
    fallback.citations = ["PubMed:456"]
    fallback.retrieved_chunks = [RetrievedChunk(chunk_id=item.id, source_id=item.id, source_type=item.source_type, citation=f"PubMed:{item.external_id}", text=item.abstract, score=0.9) for item in (source, other)]
    mock_generation(monkeypatch, {
        "paragraphs": ["The supplied evidence does not provide enough information to answer." if abstain else "At 12 weeks, HbA1c was 0.5 percentage points lower than with placebo [PubMed:123]."],
        "cited_sources": [] if abstain else ["PubMed:123"], "uncertainty": [],
    })
    answer = ConversationService().generate(workspace, "Explain that result", [], [source, other], fallback)
    assert answer.generation_mode == "conversational"
    assert "STALE" not in answer.model_dump_json()
    assert answer.evidence == answer.supporting_evidence == answer.evidence_synthesis == answer.facet_coverage == []
    assert len(answer.retrieved_chunks) == 2
    assert answer.source_readouts[1].startswith("CONTEXT ONLY · PubMed:456")
    assert answer.source_readouts[0].startswith("CONTEXT ONLY" if abstain else "CITED IN ANSWER · PubMed:123")
    assert "do not independently verify" in answer.evidence_quality[0]
    if abstain:
        assert not any(item.startswith("CITED") for item in answer.source_readouts)


@pytest.mark.parametrize("question", ["Should I take metformin?", "Compare the other one"])
def test_boundary_responses_clear_source_based_fallback_metadata(monkeypatch, context, question):
    workspace, source, fallback = context
    workspace.intervention = "metformin"
    fallback.source_readouts = ["CITED · PubMed:123"]
    fallback.evidence = fallback.supporting_evidence = ["Old study finding"]
    fallback.evidence_quality = ["Directness high: study supports answer"]
    fallback.reasoning_summary = ["Old answer cites one row"]
    monkeypatch.setattr("triallens.conversation.httpx.post", lambda *args, **kwargs: pytest.fail("No inference expected"))
    answer = ConversationService().generate(workspace, question, [], [source], fallback)
    assert answer.citations == answer.source_readouts == answer.evidence == answer.supporting_evidence == answer.evidence_quality == []
    assert "No source-based answer was generated" in answer.reasoning_summary[0]


@pytest.mark.parametrize("output,status", [
    ({"paragraphs": ["It works [PubMed:999]."], "cited_sources": ["PubMed:999"], "uncertainty": []}, "completed"),
    ({"paragraphs": ["It works."], "cited_sources": ["PubMed:123"], "uncertainty": []}, "completed"),
    ({"paragraphs": ["It works."], "cited_sources": [], "uncertainty": []}, "completed"),
    ({"paragraphs": ["The trial reports a result [PubMed:123].", "It is safe for everyone."], "cited_sources": ["PubMed:123"], "uncertainty": []}, "completed"),
    ({"paragraphs": ["The trial reports a result [PubMed:123].\n\nIt is safe for everyone."], "cited_sources": ["PubMed:123"], "uncertainty": []}, "completed"),
    ({"paragraphs": ["It works [PubMed:123]."], "cited_sources": ["PubMed:123"], "uncertainty": []}, "incomplete"),
    ({"paragraphs": ["   "], "cited_sources": [], "uncertainty": []}, "completed"),
])
def test_invalid_generation_falls_back(monkeypatch, context, output, status):
    workspace, source, fallback = context
    mock_generation(monkeypatch, output, status)
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert result.generation_mode == "extractive"
    assert result.short_answer == "Extracted result"
    assert "failed validation" in result.generation_note


def test_long_copied_passage_rejected(monkeypatch, context):
    workspace, source, fallback = context
    source.abstract = " ".join(f"word{i}" for i in range(35))
    mock_generation(monkeypatch, {"paragraphs": [source.abstract + " [PubMed:123]"], "cited_sources": ["PubMed:123"], "uncertainty": []})
    assert ConversationService().generate(workspace, "What changed?", [], [source], fallback).generation_mode == "extractive"


def test_missing_config_does_not_call_provider(monkeypatch, context):
    workspace, source, fallback = context
    monkeypatch.delenv("OPENAI_API_KEY")
    def unexpected(*args, **kwargs):
        pytest.fail("Provider must not be called without configuration")
    monkeypatch.setattr("triallens.conversation.httpx.post", unexpected)
    assert "not connected" in ConversationService().generate(workspace, "What changed?", [], [source], fallback).generation_note


def test_timeout_falls_back(monkeypatch, context):
    workspace, source, fallback = context
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("test timeout")
    monkeypatch.setattr("triallens.conversation.httpx.post", timeout)
    assert ConversationService().generate(workspace, "What changed?", [], [source], fallback).generation_mode == "extractive"


def test_follow_up_retrieval_keeps_original_referent(context):
    _, _, first = context
    first.question = "What is the HbA1c result?"
    second = first.model_copy(update={"question": "Explain that more simply"})
    query = retrieval_question("Why is that important?", [first, second])
    assert "HbA1c" in query
    assert first.short_answer not in query
    assert retrieval_question("What safety concerns exist?", [first]) == "What safety concerns exist?"


def test_budget_rejection_never_calls_provider(monkeypatch, context):
    from triallens.usage import BudgetUnavailable
    workspace, source, fallback = context
    def reject(*args):
        raise BudgetUnavailable("Budget reached")
    monkeypatch.setattr("triallens.conversation.UsageLedger.reserve", reject)
    def unexpected(*args, **kwargs):
        pytest.fail("No request should be sent after budget rejection")
    monkeypatch.setattr("triallens.conversation.httpx.post", unexpected)
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert result.generation_note == "Budget reached"


def test_credit_exhaustion_releases_reservation(monkeypatch, context):
    from triallens.usage import UsageLedger
    workspace, source, fallback = context
    def reject(url, **kwargs):
        return httpx.Response(429, request=httpx.Request("POST", url), json={"error": {"code": "credit_balance_exhausted"}})
    monkeypatch.setattr("triallens.conversation.httpx.post", reject)
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert "credits are exhausted" in result.generation_note
    status = UsageLedger().status()
    assert status["used_or_reserved_usd"] == 0
    assert status["generated_answers"] == 0
    assert status["pending_requests"] == 0


def test_local_generation_needs_no_key_and_never_sends_auth(monkeypatch, context):
    from triallens.usage import UsageLedger
    workspace, source, fallback = context
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    monkeypatch.delenv("OPENAI_API_KEY")
    requests = []
    def local(url, **kwargs):
        requests.append(url)
        assert url == "http://127.0.0.1:11434/api/chat"
        assert "headers" not in kwargs
        assert kwargs["json"]["think"] is False
        assert kwargs["json"]["format"]["type"] == "object"
        content = json.dumps({"paragraphs": ["HbA1c was lower at 12 weeks with the intervention [PubMed:123]."], "cited_sources": ["PubMed:123"], "uncertainty": []})
        return httpx.Response(200, request=httpx.Request("POST", url), json={"done": True, "done_reason": "stop", "message": {"content": content}})
    monkeypatch.setattr("triallens.conversation.httpx.post", local)
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert result.generation_mode == "conversational"
    assert len(requests) == 2
    assert UsageLedger().status()["used_or_reserved_usd"] == 0
    assert UsageLedger().status()["generated_answers"] == 1


def test_local_failure_never_falls_back_to_paid_provider(monkeypatch, context):
    workspace, source, fallback = context
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    requests = []
    def offline(url, **kwargs):
        requests.append(url)
        raise httpx.ConnectError("Ollama is stopped")
    monkeypatch.setattr("triallens.conversation.httpx.post", offline)
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert result.generation_mode == "extractive"
    assert "local model" in result.generation_note
    assert requests == ["http://127.0.0.1:11434/api/chat"]


def test_cloud_tag_is_rejected_in_local_mode(monkeypatch, context):
    from triallens.conversation import chat_configured
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    monkeypatch.setenv("TRIALLENS_LOCAL_MODEL", "some-model:cloud")
    assert not chat_configured()


def test_unknown_citation_in_limitations_is_rejected(monkeypatch, context):
    workspace, source, fallback = context
    mock_generation(monkeypatch, {"paragraphs": ["HbA1c was lower than placebo [PubMed:123]."],
        "cited_sources": ["PubMed:123"], "uncertainty": ["Long-term results are unclear [PubMed:999]."]})
    assert ConversationService().generate(workspace, "What changed?", [], [source], fallback).generation_mode == "extractive"


def test_copied_retrieved_passage_outside_abstract_prefix_is_rejected(monkeypatch, context):
    from triallens.models import RetrievedChunk
    workspace, source, fallback = context
    passage = " ".join(f"word{i}" for i in range(35))
    fallback.retrieved_chunks = [RetrievedChunk(chunk_id="late", source_id=source.id,
        source_type=source.source_type, citation="PubMed:123", text=passage, score=1)]
    captured = mock_generation(monkeypatch, {"paragraphs": [passage + " [PubMed:123]"],
        "cited_sources": ["PubMed:123"], "uncertainty": []})
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert passage in json.loads(captured[0]['input'])['evidence'][0]['matched_passages']
    assert result.generation_mode == "extractive"


def test_local_revision_replaces_draft_and_preserves_demo_notice(monkeypatch, context):
    from triallens.usage import UsageLedger
    workspace, source, fallback = context
    source.metadata['demo'] = True
    monkeypatch.setenv('TRIALLENS_CHAT_PROVIDER', 'ollama')
    calls = []
    def local(url, **kwargs):
        messages = kwargs['json']['messages']
        calls.append(len(messages))
        if len(calls) == 1:
            assert json.loads(messages[1]['content'])['evidence'][0]['demo'] is True
            answer = 'Unsupported draft [PubMed:123].'
        else:
            assert 'Unsupported draft' in messages[-2]['content']
            assert 'Check the draft' in messages[-1]['content']
            answer = 'The supplied result is lower than placebo [PubMed:123].'
        content = json.dumps({'paragraphs':[answer], 'cited_sources':['PubMed:123'], 'uncertainty':[]})
        return httpx.Response(200, request=httpx.Request('POST',url), json={'done':True,'message':{'content':content}})
    monkeypatch.setattr('triallens.conversation.httpx.post',local)
    result = ConversationService().generate(workspace,'What changed?',[],[source],fallback)
    assert result.generation_mode == 'conversational'
    assert 'Unsupported draft' not in result.direct_answer
    assert 'demo evidence' in result.generation_note
    assert calls == [2,4]
    assert UsageLedger().status()['generated_answers'] == 1


def test_failed_local_revision_does_not_show_or_count_draft(monkeypatch, context):
    from triallens.usage import UsageLedger
    workspace, source, fallback = context
    monkeypatch.setenv('TRIALLENS_CHAT_PROVIDER','ollama')
    calls = []
    def local(url, **kwargs):
        calls.append(url)
        if len(calls) == 2:
            raise httpx.ReadTimeout('revision timeout')
        content = json.dumps({'paragraphs':['Unrevised draft [PubMed:123].'], 'cited_sources':['PubMed:123'], 'uncertainty':[]})
        return httpx.Response(200,request=httpx.Request('POST',url),json={'done':True,'message':{'content':content}})
    monkeypatch.setattr('triallens.conversation.httpx.post',local)
    result = ConversationService().generate(workspace,'What changed?',[],[source],fallback)
    assert result.generation_mode == 'extractive'
    assert result.short_answer == 'Extracted result'
    assert calls == ['http://127.0.0.1:11434/api/chat'] * 2
    assert UsageLedger().status()['generated_answers'] == 0


def test_citation_format_repair_requires_exact_known_ids():
    from triallens.conversation import normalize_citations
    allowed = {'PubMed:A', 'PubMed:B'}
    assert normalize_citations('Finding [citation: PubMed:A, citation: PubMed:B].', allowed) == 'Finding [PubMed:A] [PubMed:B].'
    unknown = 'Finding [citation: PubMed:A, citation: PubMed:UNKNOWN].'
    assert normalize_citations(unknown, allowed) == unknown
    assert normalize_citations('Finding [PubMed:AB].', allowed) == 'Finding [PubMed:AB].'


def test_conversational_abstention_accepts_contracted_negative(monkeypatch, context):
    workspace, source, fallback = context
    mock_generation(monkeypatch, {"paragraphs": ["The supplied evidence doesn't answer who won that football match. It only covers this research workspace."], "cited_sources": [], "uncertainty": []})
    answer = ConversationService().generate(workspace, "Who won the football match?", [], [source], fallback)
    assert answer.generation_mode == "conversational"


def test_ambiguous_comparator_without_history_asks_for_clarification(monkeypatch, context):
    workspace, source, fallback = context
    def unexpected(*args, **kwargs):
        pytest.fail("An unresolved comparator should be clarified before generating a comparison")
    monkeypatch.setattr("triallens.conversation.httpx.post", unexpected)
    answer = ConversationService().generate(workspace, "Is it better than the other one?", [], [source], fallback)
    assert answer.generation_mode == "conversational"
    assert "Which" in answer.direct_answer
    assert answer.citations == []


def test_local_busy_does_not_queue_or_count(monkeypatch, context):
    from triallens.conversation import _LOCAL_GENERATION_LOCK
    from triallens.usage import UsageLedger
    workspace, source, fallback = context
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    def unexpected(*args, **kwargs):
        pytest.fail("Busy local model must not queue another provider request")
    monkeypatch.setattr("triallens.conversation.httpx.post", unexpected)
    assert _LOCAL_GENERATION_LOCK.acquire(blocking=False)
    try:
        answer = ConversationService().generate(workspace, "Explain the result", [], [source], fallback)
        assert "another question" in answer.generation_note
        assert UsageLedger().status()["generated_answers"] == 0
    finally:
        _LOCAL_GENERATION_LOCK.release()


def test_local_lock_released_after_provider_failure(monkeypatch, context):
    from triallens.conversation import _LOCAL_GENERATION_LOCK
    workspace, source, fallback = context
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    def offline(*args, **kwargs):
        raise httpx.ConnectError("test offline")
    monkeypatch.setattr("triallens.conversation.httpx.post", offline)
    ConversationService().generate(workspace, "Explain the result", [], [source], fallback)
    assert _LOCAL_GENERATION_LOCK.acquire(blocking=False)
    _LOCAL_GENERATION_LOCK.release()


def test_generation_context_has_total_budget_and_preserves_retrieved_passage(monkeypatch, context):
    from triallens.models import RetrievedChunk
    workspace, first, fallback = context
    sources = [first.model_copy(update={"id": f"source-{i}", "external_id": str(i), "abstract": "Long context. " * 2000}) for i in range(8)]
    fallback.retrieved_chunks = [RetrievedChunk(chunk_id="selected", source_id=sources[0].id,
        source_type=SourceType.pubmed, citation="PubMed:0", text="Critical outcome near the end of the source.", score=1)]
    captured = mock_generation(monkeypatch, {"paragraphs": ["I cannot establish the requested result from this evidence."], "cited_sources": [], "uncertainty": []})
    ConversationService().generate(workspace, "What does the evidence establish?", [], sources, fallback)
    records = json.loads(captured[0]["input"])["evidence"]
    assert sum(len(r["text"]) + sum(map(len, r["matched_passages"])) for r in records) <= 28000
    assert "Critical outcome near the end of the source." in records[0]["matched_passages"]
    assert all(record["content_truncated"] for record in records)


@pytest.mark.parametrize("question", ["I am pregnant and have kidney disease. Should I start intervention A today?", "Should I stop taking metformin?", "Should I increase my dose?"])
def test_personal_treatment_decision_does_not_infer_population_or_suitability(monkeypatch, context, question):
    from triallens.usage import UsageLedger
    workspace, source, fallback = context
    def unexpected(*args, **kwargs):
        pytest.fail("Personal treatment decisions should not be inferred by the model")
    monkeypatch.setattr("triallens.conversation.httpx.post", unexpected)
    workspace.intervention = "metformin"
    answer = ConversationService().generate(workspace, question, [], [source], fallback)
    assert answer.generation_mode == "conversational"
    assert "individual" in answer.direct_answer
    assert "clinician" in answer.direct_answer
    assert answer.citations == [] and answer.uncertainty == []
    assert UsageLedger().status()["generated_answers"] == 0


@pytest.mark.parametrize("question,include_combination", [("What are the benefits and limitations of metformin?", False), ("What does the ZITUVIMET combination label say?", True)])
def test_single_ingredient_synthesis_does_not_mix_combination_label(monkeypatch, context, question, include_combination):
    from triallens.models import RetrievedChunk
    workspace, source, fallback = context
    workspace.intervention = "metformin"
    source.source_type = SourceType.fda_label
    source.title = "FDA label: Metformin hydrochloride"
    source.abstract = "Metformin hydrochloride is indicated to improve glycemic control in adults with type 2 diabetes."
    combination = source.model_copy(update={"id": "combo", "external_id": "combo", "title": "FDA label: ZITUVIMET", "abstract": "ZITUVIMET is a combination of sitagliptin and metformin. ZITUVIMET has not been studied in patients with a history of pancreatitis."})
    fallback.retrieved_chunks = [RetrievedChunk(chunk_id="combo-chunk", source_id=combination.id, source_type=combination.source_type, citation="openFDA label:combo", text=combination.abstract, score=0.9)]
    fallback.source_readouts = ["CITED · openFDA label:combo · Old extractive selection"]
    captured = mock_generation(monkeypatch, {"paragraphs": ["The excerpt does not establish individual suitability."], "cited_sources": [], "uncertainty": []})
    answer = ConversationService().generate(workspace, question, [], [combination, source], fallback)
    records = json.loads(captured[0]["input"])["evidence"]
    assert any(r["citation"] == "openFDA label:combo" for r in records) is include_combination
    assert any(chunk.source_id == combination.id for chunk in answer.retrieved_chunks) is include_combination
    assert any("openFDA label:combo" in item for item in answer.source_readouts) is include_combination
    assert not any(item.startswith("CITED") for item in answer.source_readouts)


def test_combination_followup_keeps_named_product_from_user_history(monkeypatch, context):
    workspace, source, fallback = context
    workspace.intervention = "metformin"
    source.source_type = SourceType.fda_label
    source.title = "FDA label: Metformin hydrochloride"
    combination = source.model_copy(update={"id": "combo", "external_id": "combo", "title": "FDA label: ZITUVIMET", "metadata": {"substance_names": ["SITAGLIPTIN", "METFORMIN HYDROCHLORIDE"]}})
    prior = fallback.model_copy(update={"question": "What does the ZITUVIMET label say?"})
    captured = mock_generation(monkeypatch, {"paragraphs": ["The excerpt does not establish individual suitability."], "cited_sources": [], "uncertainty": []})
    answer = ConversationService().generate(workspace, "Explain that more simply", [prior], [combination, source], fallback)
    records = json.loads(captured[0]["input"])["evidence"]
    assert any(r["citation"] == "openFDA label:combo" for r in records)
    assert "excluded" not in answer.generation_note


def test_combination_brand_alias_keeps_product_when_title_lists_multiple_brands(monkeypatch, context):
    workspace, source, fallback = context
    workspace.intervention = "metformin"
    source.source_type = SourceType.fda_label
    source.title = "FDA label: Metformin hydrochloride"
    combination = source.model_copy(update={"id": "combo", "external_id": "combo", "title": "FDA label: ZITUVIMET, ZITUVIMET XR", "metadata": {"substance_names": ["SITAGLIPTIN", "METFORMIN HYDROCHLORIDE"], "brand_names": ["ZITUVIMET", "ZITUVIMET XR"]}})
    captured = mock_generation(monkeypatch, {"paragraphs": ["The excerpt does not establish individual suitability."], "cited_sources": [], "uncertainty": []})
    ConversationService().generate(workspace, "What does ZITUVIMET's label say?", [], [combination, source], fallback)
    records = json.loads(captured[0]["input"])["evidence"]
    assert any(r["citation"] == "openFDA label:combo" for r in records)


def test_each_evidence_paragraph_can_repeat_its_source(monkeypatch, context):
    workspace, source, fallback = context
    mock_generation(monkeypatch, {"paragraphs": [
        "The endpoint was lower than placebo at 12 weeks [PubMed:123].",
        "The excerpt does not establish an effect beyond that period [PubMed:123]."],
        "cited_sources": ["PubMed:123"], "uncertainty": []})
    result = ConversationService().generate(workspace, "What changed?", [], [source], fallback)
    assert result.generation_mode == "conversational"
    assert result.direct_answer.count("[PubMed:123]") == 2


def test_uncited_abstention_cannot_smuggle_clinical_claims(monkeypatch, context):
    workspace, source, fallback = context
    mock_generation(monkeypatch, {"paragraphs": [
        "I can't assess the study fully, but this treatment is safe for everyone."],
        "cited_sources": [], "uncertainty": ["It has no serious adverse effects."]})
    result = ConversationService().generate(workspace, "What does the evidence say about safety?", [], [source], fallback)
    assert result.generation_mode == "conversational"
    assert "safe for everyone" not in result.direct_answer
    assert "no serious adverse effects" not in result.model_dump_json()
    assert result.citations == [] and result.uncertainty == []
    assert "verify" in result.direct_answer
