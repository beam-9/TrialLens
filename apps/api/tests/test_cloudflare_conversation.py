"""Hosted two-pass integration, with HTTP mocked: no paid or local inference."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from triallens import cloudflare, main
from triallens.conversation import ConversationService, GeneratedAnswer, INSTRUCTIONS, REVISION_INSTRUCTIONS, _LOCAL_GENERATION_LOCK, chat_configured, chat_model
from triallens.models import Answer, EvidenceSource, SourceType, Workspace
from triallens.usage import UsageLedger


@pytest.fixture
def context(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token-not-a-secret")
    monkeypatch.setenv("TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED", "true")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("TRIALLENS_CHAT_MODEL", "gpt-4.1-mini")
    workspace = Workspace(condition="diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed, external_id="123", title="Adult trial", abstract="Adults receiving add-on treatment had HbA1c 0.5 percentage points lower than placebo at 12 weeks.")
    fallback = Answer(workspace_id=workspace.id, question="What changed?", short_answer="Extracted result", evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    return workspace, source, fallback


def provider(monkeypatch, *, reject_pass=None, bad_citation=False, copied=None):
    calls = []
    def post(url, **kwargs):
        assert url == "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/run/" + cloudflare.MODEL
        calls.append(kwargs["json"])
        if len(calls) == reject_pass:
            return httpx.Response(429, request=httpx.Request("POST", url), json={"secret": "must never surface"})
        marker = "PubMed:999" if bad_citation else "PubMed:123"
        wording = copied or ("The draft should be replaced" if len(calls) == 1 else "In adults, the add-on treatment lowered HbA1c by 0.5 percentage points versus placebo at 12 weeks")
        answer = {"paragraphs": [wording + f" [{marker}]."], "cited_sources": [marker], "uncertainty": []}
        return httpx.Response(200, request=httpx.Request("POST", url), json={"success": True, "result": {"response": answer, "usage": {"prompt_tokens": 100, "completion_tokens": 50}}})
    monkeypatch.setattr("triallens.cloudflare.httpx.post", post)
    return calls


def generate(context, question="Explain the result", history=None):
    workspace, source, fallback = context
    return ConversationService().generate(workspace, question, history or [], [source], fallback)


def test_two_pass_keeps_schema_history_citations_and_counts_once(monkeypatch, context):
    calls = provider(monkeypatch)
    previous = context[2].model_copy(update={"direct_answer": "Prior answer is not evidence", "question": "Earlier question"})
    answer = generate(context, history=[previous])
    assert chat_configured() and chat_model() == cloudflare.MODEL
    assert answer.generation_mode == "conversational"
    assert "draft" not in answer.direct_answer and "12 weeks" in answer.direct_answer
    assert "Cloudflare" in answer.generation_note
    assert answer.citations == ["PubMed:123"]
    assert len(calls) == 2
    assert calls[0]["messages"][0]["content"] == INSTRUCTIONS
    assert calls[1]["messages"][-1]["content"].startswith(REVISION_INSTRUCTIONS)
    payload = json.loads(calls[0]["messages"][1]["content"])
    assert payload["history"][0]["question"] == "Earlier question"
    assert payload["evidence"][0]["citation"] == "PubMed:123"
    assert calls[0]["response_format"]["json_schema"] == GeneratedAnswer.model_json_schema()
    status = UsageLedger().status()
    assert status["generated_answers"] == 1 and status["used_or_reserved_usd"] == 0
    assert cloudflare.quota_status()["requests"] == 2


@pytest.mark.parametrize('bad_citation', [False, True])
def test_gemma_binds_citation_schema_but_keeps_final_provenance_checks(monkeypatch, context, bad_citation):
    monkeypatch.setattr(cloudflare, 'MODEL', '@cf/google/gemma-4-26b-a4b-it')
    calls = provider(monkeypatch, bad_citation=bad_citation)
    answer = generate(context)
    schema = calls[0]['response_format']['json_schema']['schema']
    assert schema['properties']['cited_sources']['items']['enum'] == ['PubMed:123']
    assert 'pattern' in schema['properties']['paragraphs']['items']
    assert schema == calls[1]['response_format']['json_schema']['schema']
    assert (answer.generation_mode == 'conversational') == (not bad_citation)
    assert len(calls) == 2


def test_bound_schema_accepts_only_exact_citation_spellings_and_escapes_identifiers():
    import re
    from triallens.conversation import citation_bound_schema
    ids = {'PubMed:123', 'openFDA label:LABEL-1', 'doi:10.5/a+b'}
    schema = citation_bound_schema(ids)
    pattern = schema['properties']['paragraphs']['items']['pattern']
    for text in ('No answer is available.', 'A finding [PubMed:123].',
                 'Two sources [openFDA label:LABEL-1] [doi:10.5/a+b].'):
        assert re.fullmatch(pattern, text)
    for text in ('A finding [demo].', 'A finding [1].', 'A finding [PubMed:999].',
                 'A finding [doi:10X5/ab].', 'A finding 【PubMed:123】.'):
        assert not re.fullmatch(pattern, text)
    assert citation_bound_schema(set()) == GeneratedAnswer.model_json_schema()
    assert 'enum' not in GeneratedAnswer.model_json_schema()['properties']['cited_sources']['items']


@pytest.mark.parametrize("reject_pass", [1, 2])
def test_quota_failure_never_exposes_draft_or_falls_back_to_another_provider(monkeypatch, context, reject_pass):
    calls = provider(monkeypatch, reject_pass=reject_pass)
    answer = generate(context)
    assert answer.generation_mode == "extractive" and answer.short_answer == "Extracted result"
    assert "allowance" in answer.generation_note and "no local model or paid fallback" in answer.generation_note
    assert "secret" not in answer.generation_note
    assert len(calls) == reject_pass and UsageLedger().status()["generated_answers"] == 0
    assert _LOCAL_GENERATION_LOCK.acquire(False)
    _LOCAL_GENERATION_LOCK.release()


def test_unknown_citation_and_copy_guard_still_apply(monkeypatch, context):
    provider(monkeypatch, bad_citation=True)
    assert generate(context).generation_mode == "extractive"
    phrase = " ".join(f"unique{i}" for i in range(40))
    context[1].abstract = phrase
    provider(monkeypatch, copied=phrase)
    assert generate(context).generation_mode == "extractive"
    assert UsageLedger().status()["generated_answers"] == 0


def test_missing_config_guards_and_busy_never_invoke_inference(monkeypatch, context):
    def unexpected(*args, **kwargs):
        pytest.fail("No provider should be called")
    monkeypatch.setattr("triallens.cloudflare.httpx.post", unexpected)
    assert "Individual treatment decision" in generate(context, "Should I stop metformin?").generation_note
    assert "Clarification needed" in generate(context, "Compare the other one").generation_note
    assert _LOCAL_GENERATION_LOCK.acquire(False)
    try:
        assert "answering another question" in generate(context).generation_note
    finally:
        _LOCAL_GENERATION_LOCK.release()
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN")
    assert not chat_configured()
    assert "setup is incomplete" in generate(context).generation_note
    assert UsageLedger().status()["generated_answers"] == 0


def test_health_and_usage_never_expose_cloudflare_credentials(context):
    client = TestClient(main.app)
    health = client.get("/health").json()
    usage = client.get("/usage").json()
    assert health["provider"] == usage["provider"] == "cloudflare"
    assert health["model"] == cloudflare.MODEL
    assert "test-token-not-a-secret" not in json.dumps([health, usage])
    assert "a" * 32 not in json.dumps([health, usage])


def test_single_pass_experiment_calls_provider_once_per_question_and_restores(monkeypatch, context):
    from evaluation.single_pass import single_pass_experiment
    from triallens import conversation

    calls = provider(monkeypatch)
    message_counts = []
    original_post = conversation.httpx.post

    def capture_message_count(url, **kwargs):
        message_counts.append(len(kwargs['json']['messages']))
        return original_post(url, **kwargs)

    monkeypatch.setattr(conversation.httpx, 'post', capture_message_count)
    original = conversation.cloudflare.completion
    with single_pass_experiment(True):
        first = generate(context)
        second = generate(context)
        assert first.generation_mode == second.generation_mode == 'conversational'
    assert len(calls) == 2
    assert message_counts == [2, 2]
    assert conversation.cloudflare.completion is original


def test_single_pass_preserves_final_citation_rejection_without_retry(monkeypatch, context):
    from evaluation.single_pass import single_pass_experiment

    calls = provider(monkeypatch, bad_citation=True)
    with single_pass_experiment(True):
        answer = generate(context)
    assert len(calls) == 1
    assert answer.generation_mode != 'conversational'
    assert 'failed validation' in answer.generation_note
    assert UsageLedger().status()['generated_answers'] == 0


def test_single_pass_replay_rejects_changed_source_context(monkeypatch):
    from evaluation.single_pass import single_pass_experiment
    from triallens import conversation

    calls = []
    monkeypatch.setattr(conversation.cloudflare, 'completion', lambda messages, schema: calls.append(messages) or 'draft')
    original = conversation.cloudflare.completion
    first = [{'role': 'system', 'content': 'instructions'}, {'role': 'user', 'content': 'first evidence'}]
    with pytest.raises(ValueError, match='context differs'), single_pass_experiment(True):
        conversation.cloudflare.completion(first, {})
        changed = [first[0], {'role': 'user', 'content': 'different evidence'},
                   {'role': 'assistant', 'content': 'draft'}, {'role': 'user', 'content': 'revise'}]
        conversation.cloudflare.completion(changed, {})
    assert len(calls) == 1
    assert conversation.cloudflare.completion is original


@pytest.mark.parametrize(("draft", "revision", "expected"), [
    (
        {"paragraphs": [{"text": "The 0.5 percentage-point difference favored treatment.", "source_indices": [0]}], "uncertainty": []},
        {"paragraphs": [{"text": "HbA1c was 0.5 percentage points lower than placebo.", "source_indices": [0]}], "uncertainty": []},
        "HbA1c was 0.5 percentage points lower than placebo. [PubMed:123]",
    ),
    (
        {"paragraphs": [{"text": "The first draft used an unknown source.", "source_indices": [12]}], "uncertainty": []},
        {"paragraphs": [{"text": "That outcome is not reported in the excerpts.", "source_indices": []}], "uncertainty": []},
        "I couldn't verify a sourced answer",
    ),
    (
        {"paragraphs": [{"text": "That outcome is not reported in the excerpts.", "source_indices": []}], "uncertainty": []},
        {"paragraphs": [{"text": "The treatment improved HbA1c by 80%.", "source_indices": [0]}], "uncertainty": []},
        None,
    ),
])
def test_structured_attribution_keeps_two_pass_context_and_production_validation(monkeypatch, context, draft, revision, expected):
    from evaluation.structured_attribution import structured_attribution_experiment

    monkeypatch.setattr(cloudflare, "MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
    context[1].abstract += " At baseline, mean HbA1c was 7.2%."
    calls = []
    original = cloudflare.completion

    def post(url, **kwargs):
        calls.append(kwargs["json"])
        answer = draft if len(calls) == 1 else revision
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "success": True, "result": {"response": answer, "usage": {"prompt_tokens": 100, "completion_tokens": 50}},
        })

    monkeypatch.setattr(cloudflare.httpx, "post", post)
    with structured_attribution_experiment(True):
        answer = generate(context)
    assert cloudflare.completion is original
    assert len(calls) == 2
    assert calls[0]["messages"][1] == calls[1]["messages"][1]
    payload = json.loads(calls[0]["messages"][1]["content"])
    assert payload["evidence"][0]["citation"] == "PubMed:123"
    assert "zero-based" in calls[0]["messages"][0]["content"]
    assert "zero-based" in calls[1]["messages"][-1]["content"]
    for call in calls:
        schema = call["response_format"]["json_schema"]
        props = schema["properties"]["paragraphs"]["items"]["properties"]
        assert props["source_indices"]["items"]["enum"] == [0]
    forwarded_draft = json.loads(calls[1]["messages"][2]["content"])
    if draft["paragraphs"][0]["source_indices"] == [12]:
        assert forwarded_draft == {}
    elif draft["paragraphs"][0]["source_indices"] == [0]:
        assert forwarded_draft["cited_sources"] == ["PubMed:123"]
    if expected is None:
        assert answer.generation_mode == "extractive"
    else:
        assert answer.generation_mode == "conversational"
        assert answer.direct_answer.startswith(expected)


@pytest.mark.parametrize(("paragraphs", "uncertainty"), [
    ([{"text": "A result", "source_indices": [True]}], []),
    ([{"text": "A result", "source_indices": ["0"]}], []),
    ([{"text": "A result", "source_indices": [0, 0]}], []),
    ([{"text": "A result", "source_indices": [2]}], []),
    ([{"text": "A result [PubMed:123].", "source_indices": [0]}], []),
    ([{"text": "The interval was [0.2, 0.8].", "source_indices": [0]}], []),
    ([{"text": "First paragraph.\n\nSecond paragraph.", "source_indices": [0]}], []),
    ([{"text": "A result", "source_indices": [0]}, {"text": "Another result", "source_indices": []}], []),
    ([{"text": "A result", "source_indices": [0]}], [{"text": "A limitation", "source_indices": [1]}]),
])
def test_structured_attribution_rejects_malformed_or_unowned_citations(paragraphs, uncertainty):
    from evaluation.structured_attribution import render_answer

    with pytest.raises(ValueError):
        render_answer(json.dumps({"paragraphs": paragraphs, "uncertainty": uncertainty}), ["PubMed:123", "PubMed:456"])


def test_structured_attribution_renders_exact_markers_per_block():
    from evaluation.structured_attribution import render_answer

    raw = json.dumps({
        "paragraphs": [
            {"text": "First finding (95% CI 0.2 to 0.8).", "source_indices": [1]},
            {"text": "Second finding.", "source_indices": [0, 1]},
        ],
        "uncertainty": [{"text": "Limited to 95% intervals.", "source_indices": [1]}],
    })
    assert json.loads(render_answer(raw, ["PubMed:123", "openFDA label:LABEL-1"])) == {
        "paragraphs": [
            "First finding (95% CI 0.2 to 0.8). [openFDA label:LABEL-1]",
            "Second finding. [PubMed:123] [openFDA label:LABEL-1]",
        ],
        "cited_sources": ["openFDA label:LABEL-1", "PubMed:123"],
        "uncertainty": ["Limited to 95% intervals. [openFDA label:LABEL-1]"],
    }


def test_passage_attribution_binds_percentages_to_selected_passages():
    from evaluation.structured_attribution import render_answer

    citations = ["PubMed:123", "PubMed:123", "PubMed:456"]
    passages = ["The treatment changed HbA1c by -0.94%.", "The second outcome changed by 2%.", "A correction reports 3%."]
    answer = {"paragraphs": [{"text": "The change was -0.94%.", "passage_indices": [0]}], "uncertainty": []}
    assert json.loads(render_answer(json.dumps(answer), citations, passages=passages))["cited_sources"] == ["PubMed:123"]
    for wrong_index in (1, 2, 3, True):
        answer["paragraphs"][0]["passage_indices"] = [wrong_index]
        with pytest.raises(ValueError):
            render_answer(json.dumps(answer), citations, passages=passages)


def test_passage_attribution_catalog_keeps_exact_evidence_and_final_validation(monkeypatch, context):
    from evaluation.structured_attribution import structured_attribution_experiment

    monkeypatch.setattr(cloudflare, "MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
    context[1].abstract += " At baseline, HbA1c was 7.2%."
    calls = []
    original = cloudflare.completion

    def post(url, **kwargs):
        calls.append(kwargs["json"])
        request = json.loads(calls[-1]["messages"][1]["content"])
        source = request["evidence"][0]
        index = request["passage_catalog"].index({"source_index": 0, "field": "text"})
        assert "HbA1c" in source["text"]
        text = "HbA1c was 80%." if len(calls) == 1 else "HbA1c was 0.5 percentage points lower than placebo."
        entry = {"text": text, "passage_indices": [index]}
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "success": True, "result": {"response": {"paragraphs": [entry], "uncertainty": []},
                                         "usage": {"prompt_tokens": 100, "completion_tokens": 50}},
        })

    monkeypatch.setattr(cloudflare.httpx, "post", post)
    with structured_attribution_experiment(True, passage_attribution=True):
        answer = generate(context)
    assert cloudflare.completion is original
    assert len(calls) == 2
    assert calls[0]["messages"][1] == calls[1]["messages"][1]
    draft_feedback = json.loads(calls[1]["messages"][2]["content"])
    assert "inconsistent with its selected passage" in draft_feedback["draft_validation"]
    assert "80%" not in calls[1]["messages"][2]["content"]
    properties = calls[0]["response_format"]["json_schema"]["properties"]["paragraphs"]["items"]["properties"]
    assert properties["passage_indices"]["items"]["enum"]
    assert "source_indices" not in properties
    assert answer.direct_answer.startswith("HbA1c was 0.5 percentage points lower than placebo. [PubMed:123]")
