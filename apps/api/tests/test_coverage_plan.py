"""Coverage experiment boundaries and omissions, without hosted inference."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))
from coverage_plan import (CoveragePlan, coverage_plan_experiment, render_answer,
                           validate_plan)
from triallens import cloudflare, conversation
from triallens.models import Answer, EvidenceSource, SourceType, Workspace


QUOTE = "In 240 randomized adults, HbA1c differed by 0.5 percentage points versus placebo at 12 weeks."
SAFETY = "Voluntary reports cannot establish an event's frequency or a causal relationship."


def payload():
    return {"question": "Explain the numerical comparison and report limitations.", "history": [],
            "evidence": [{"citation": "PubMed:trial", "text": QUOTE, "matched_passages": []},
                         {"citation": "openFDA label:safety", "text": SAFETY, "matched_passages": []}]}


def plan_dict():
    return {"needs": [
        {"question_part": "Numerical comparison", "status": "supported", "support": [
            {"citation": "PubMed:trial", "quote": QUOTE, "required_values": ["240", "0.5", "12"]}]},
        {"question_part": "Report limitations", "status": "supported", "support": [
            {"citation": "openFDA label:safety", "quote": SAFETY, "required_values": []}]}]}


def answer_dict():
    return {"paragraphs": [
        "Among 240 adults randomly assigned, the reported HbA1c comparison with placebo was 0.5 percentage points at 12 weeks [PubMed:trial].",
        "Those voluntary reports cannot tell us how often an event occurs or whether the drug caused it [openFDA label:safety]."],
        "cited_sources": ["PubMed:trial", "openFDA label:safety"], "uncertainty": [],
        "coverage": [{"need_index": 0, "paragraph_indices": [0]},
                     {"need_index": 1, "paragraph_indices": [1]}]}


def test_preserves_both_question_parts_and_strips_private_mapping():
    plan = validate_plan(json.dumps(plan_dict()), payload())
    rendered = json.loads(render_answer(json.dumps(answer_dict()), plan))
    assert "coverage" not in rendered
    assert rendered["paragraphs"] == answer_dict()["paragraphs"]


@pytest.mark.parametrize("mutation,error", [
    (lambda p: p["needs"][0]["support"][0].update(citation="openFDA label:safety"), "own source"),
    (lambda p: p["needs"][0]["support"][0].update(quote=QUOTE + " Extra claim."), "own source"),
    (lambda p: p["needs"][0]["support"][0].update(required_values=["999"]), "numeric value"),
    (lambda p: p["needs"][0]["support"][0].update(required_values=["12 weeks"]), "numeric value"),
    (lambda p: p["needs"][0].update(support=[]), "requires evidence"),
    (lambda p: p["needs"][0].update(status="gap"), "Gap cannot"),
    (lambda p: p["needs"][1].update(question_part="Numerical comparison"), "duplicate"),
    (lambda p: p["needs"][1].update(question_part="     "), "Empty"),
])
def test_rejects_wrong_source_fabricated_quote_and_unreported_requirement(mutation, error):
    plan = plan_dict()
    mutation(plan)
    with pytest.raises(ValueError, match=error):
        validate_plan(json.dumps(plan), payload())


@pytest.mark.parametrize("mutation,error", [
    (lambda a: a["coverage"].pop(), "every question part"),
    (lambda a: a["coverage"].append(a["coverage"][0]), "every question part"),
    (lambda a: a["coverage"][0].update(paragraph_indices=[2]), "invalid paragraph"),
    (lambda a: a["coverage"][0].update(paragraph_indices=[0, 0]), "invalid paragraph"),
    (lambda a: a["coverage"][0].update(paragraph_indices=[1]), "supporting citation"),
    (lambda a: a["paragraphs"].__setitem__(0, "The result differs at 12 weeks [PubMed:trial]."), "required numeric"),
])
def test_rejects_missing_parts_bad_mapping_and_dropped_numbers(mutation, error):
    answer = answer_dict()
    mutation(answer)
    with pytest.raises(ValueError, match=error):
        render_answer(json.dumps(answer), CoveragePlan.model_validate(plan_dict()))


def test_value_from_another_paragraph_or_citation_does_not_fill_a_need():
    answer = answer_dict()
    answer["paragraphs"][0] = "For 240 adults the difference was 0.5 points [PubMed:trial]."
    answer["paragraphs"][1] += " Follow-up lasted 12 weeks."
    with pytest.raises(ValueError, match="required numeric"):
        render_answer(json.dumps(answer), CoveragePlan.model_validate(plan_dict()))
    answer["coverage"][0]["paragraph_indices"] = [0, 1]
    with pytest.raises(ValueError, match="required numeric"):
        render_answer(json.dumps(answer), CoveragePlan.model_validate(plan_dict()))


def test_numeric_citation_identifier_cannot_supply_missing_measurement():
    plan = plan_dict()
    plan["needs"][0]["support"][0]["citation"] = "PubMed:240"
    answer = answer_dict()
    answer["paragraphs"][0] = "The difference was 0.5 points at 12 weeks [PubMed:240]."
    with pytest.raises(ValueError, match="required numeric"):
        render_answer(json.dumps(answer), CoveragePlan.model_validate(plan))


def test_scoped_gap_can_be_planned_without_inventing_support():
    plan = {"needs": [{"question_part": "Mortality evidence", "status": "gap", "support": []}]}
    validated = validate_plan(json.dumps(plan), payload())
    answer = {"paragraphs": ["The supplied excerpts do not provide a mortality result [PubMed:trial]."],
              "cited_sources": ["PubMed:trial"], "uncertainty": [],
              "coverage": [{"need_index": 0, "paragraph_indices": [0]}]}
    assert json.loads(render_answer(json.dumps(answer), validated))["paragraphs"]
    # This does not establish the gap semantically. Final validators and a
    # source-based reviewer must still assess the statement and citation.


def test_exact_quote_in_matched_passage_is_accepted_but_combined_fragments_are_not():
    data = payload()
    data["evidence"][0]["text"] = "Other text."
    data["evidence"][0]["matched_passages"] = [QUOTE]
    validate_plan(json.dumps(plan_dict()), data)
    data["evidence"][0]["matched_passages"] = [QUOTE[:30], QUOTE[30:]]
    with pytest.raises(ValueError, match="own source"):
        validate_plan(json.dumps(plan_dict()), data)


def test_support_budget_and_schema_boundaries():
    plan = plan_dict()
    quote = "x" * 850
    plan["needs"] = [{"question_part": f"Question part {i}", "status": "supported", "support": [
        {"citation": "PubMed:trial", "quote": quote, "required_values": []} for _ in range(3)]} for i in range(3)]
    data = payload()
    data["evidence"][0]["text"] = quote
    with pytest.raises(ValueError, match="budget"):
        validate_plan(json.dumps(plan), data)
    plan = plan_dict()
    plan["needs"][0]["support"][0]["required_values"] = [240]
    with pytest.raises(ValueError):
        validate_plan(json.dumps(plan), payload())


def test_wrapper_two_calls_original_context_and_restoration(monkeypatch):
    calls = []
    def provider(messages, schema):
        calls.append((messages, schema))
        return json.dumps(plan_dict() if len(calls) == 1 else answer_dict())
    monkeypatch.setattr(cloudflare, "completion", provider)
    messages = [{"role": "system", "content": "Original system"},
                {"role": "user", "content": json.dumps(payload())}]
    with coverage_plan_experiment():
        draft = cloudflare.completion(messages, {})
        rendered = cloudflare.completion([*messages, {"role": "assistant", "content": draft},
                                         {"role": "user", "content": "Revise"}], {})
    assert cloudflare.completion is provider
    assert len(calls) == 2
    assert all(c[0][1] == messages[1] for c in calls)
    assert "coverage" not in json.loads(rendered)
    assert calls[0][1]["$defs"]["Support"]["properties"]["citation"]["enum"] == ["PubMed:trial", "openFDA label:safety"]


def test_context_mismatch_and_provider_failure_never_trigger_an_extra_call(monkeypatch):
    calls = []
    def provider(*args):
        calls.append(args)
        return json.dumps(plan_dict())
    monkeypatch.setattr(cloudflare, "completion", provider)
    messages = [{"role": "system", "content": "System"}, {"role": "user", "content": json.dumps(payload())}]
    with pytest.raises(ValueError, match="context mismatch"):
        with coverage_plan_experiment():
            draft = cloudflare.completion(messages, {})
            changed = [{**messages[0]}, {**messages[1], "content": "{}"},
                       {"role": "assistant", "content": draft}, {"role": "user", "content": "Write"}]
            cloudflare.completion(changed, {})
    assert len(calls) == 1 and cloudflare.completion is provider
    def failed(*args):
        raise cloudflare.CloudflareUnavailable("provider")
    monkeypatch.setattr(cloudflare, "completion", failed)
    with pytest.raises(cloudflare.CloudflareUnavailable):
        with coverage_plan_experiment():
            cloudflare.completion(messages, {})
    assert cloudflare.completion is failed


@pytest.mark.parametrize("bad_final", [False, True])
def test_normal_service_keeps_final_validation_and_fallback(monkeypatch, tmp_path, bad_final):
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(conversation, "chat_configured", lambda: True)
    workspace = Workspace(condition="test", source_types=[SourceType.pubmed])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
                            external_id="trial", title="Test study", abstract=QUOTE)
    fallback = Answer(workspace_id=workspace.id, question="Explain the comparison", short_answer="Excerpt",
                      evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    plan = plan_dict()
    plan["needs"] = plan["needs"][:1]
    answer = answer_dict()
    answer["paragraphs"] = answer["paragraphs"][:1]
    answer["coverage"] = answer["coverage"][:1]
    answer["cited_sources"] = ["PubMed:trial"]
    if bad_final:
        answer["paragraphs"][0] += " A further finding [PubMed:unknown]."
        answer["cited_sources"].append("PubMed:unknown")
    responses = iter([json.dumps(plan), json.dumps(answer)])
    calls = []
    def provider(*args):
        calls.append(args)
        return next(responses)
    monkeypatch.setattr(cloudflare, "completion", provider)
    with coverage_plan_experiment():
        result = conversation.ConversationService().generate(workspace, fallback.question, [], [source], fallback)
    assert len(calls) == 2
    assert result.generation_mode == ("extractive" if bad_final else "conversational")
    assert cloudflare.completion is provider
