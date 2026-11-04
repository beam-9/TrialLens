import json

import httpx
import pytest

from triallens.conversation import ConversationService, normalize_citations
from triallens.models import Answer, EvidenceSource, SourceType, Workspace


@pytest.mark.parametrize(("text", "expected"), [
    ("Finding 【PubMed:A】.", "Finding [PubMed:A]."),
    ("Label ［openFDA label:drug-1］.", "Label [openFDA label:drug-1]."),
    ("Finding 【PubMed:A, PubMed:B】.", "Finding [PubMed:A] [PubMed:B]."),
    ("Finding 【PubMed:A, PubMed:UNKNOWN】.", "Finding [PubMed:A, PubMed:UNKNOWN]."),
    ("Finding 【PubMed:A】 [PubMed:UNKNOWN].", "Finding [PubMed:A] [PubMed:UNKNOWN]."),
    ("Prose [unchanged] and citation【PubMed:unknown】.",
     "Prose [unchanged] and citation[PubMed:unknown]."),
])
def test_unicode_brackets_canonicalize_without_changing_ids(text, expected):
    assert normalize_citations(text, {"PubMed:A", "PubMed:B", "openFDA label:drug-1"}) == expected


def test_unknown_ascii_marker_keeps_its_existing_output():
    text = "Finding [PubMed:UNKNOWN]."
    assert normalize_citations(text, {"PubMed:A"}) == text


def test_normal_prose_and_absent_citations_are_unchanged():
    text = "The source describes a result. No marker was supplied."
    assert normalize_citations(text, {"PubMed:A"}) == text


def _mock_completion(monkeypatch, output):
    def post(url, **kwargs):
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(output)}]}],
        })
    monkeypatch.setattr("triallens.conversation.httpx.post", post)


@pytest.fixture
def conversation_context(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("TRIALLENS_CHAT_MODEL", "gpt-4.1-mini")
    workspace = Workspace(condition="diabetes", source_types=[SourceType.pubmed, SourceType.fda_label])
    study = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
                           external_id="A", title="Trial results", abstract="Trial outcome excerpt.")
    label = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.fda_label,
                           external_id="drug-1", title="FDA label: Drug", abstract="Label dosing excerpt.")
    fallback = Answer(workspace_id=workspace.id, question="Explain the sources", short_answer="Excerpt",
                      evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    return workspace, [study, label], fallback


def test_conversation_accepts_exact_pubmed_and_fda_unicode_markers(monkeypatch, conversation_context):
    workspace, sources, fallback = conversation_context
    study_id, label_id = "PubMed:A", "openFDA label:drug-1"
    _mock_completion(monkeypatch, {
        "paragraphs": [f"The study reports an outcome 【{study_id}】 and the label describes dosing ［{label_id}］."],
        "cited_sources": [study_id, label_id], "uncertainty": [],
    })

    answer = ConversationService().generate(workspace, fallback.question, [], sources, fallback)

    assert answer.generation_mode == "conversational"
    assert answer.citations == [study_id, label_id]
    assert f"[{study_id}]" in answer.direct_answer
    assert f"[{label_id}]" in answer.direct_answer


def test_conversation_rejects_unknown_unicode_marker_even_with_valid_ascii_marker(monkeypatch, conversation_context):
    workspace, sources, fallback = conversation_context
    _mock_completion(monkeypatch, {
        "paragraphs": ["The study reports an outcome [PubMed:A], while this claim uses 【PubMed:UNKNOWN】."],
        "cited_sources": ["PubMed:A"], "uncertainty": [],
    })

    answer = ConversationService().generate(workspace, fallback.question, [], sources, fallback)

    assert answer.generation_mode != "conversational"
    assert answer.citations == []


def test_conversation_restores_unique_exact_external_id(monkeypatch, conversation_context):
    workspace, sources, fallback = conversation_context
    _mock_completion(monkeypatch, {
        "paragraphs": ["The label describes dosing [drug-1]."],
        "cited_sources": ["drug-1"],
        "uncertainty": [],
    })
    answer = ConversationService().generate(workspace, fallback.question, [], sources, fallback)
    assert answer.generation_mode == "conversational"
    assert answer.citations == ["openFDA label:drug-1"]
    assert "[openFDA label:drug-1]" in answer.direct_answer


def test_short_ids_cannot_resolve_collisions_or_ordinals():
    from triallens.conversation import citation_aliases

    allowed = {"PubMed:example", "ClinicalTrials.gov:example", "PubMed:12345", "PubMed:known-id"}
    aliases = citation_aliases(allowed)
    assert aliases == {"known-id": "PubMed:known-id"}
    text = "[example] [12345] [KNOWN-ID] [known-id]"
    assert normalize_citations(text, allowed, aliases) == (
        "[example] [12345] [KNOWN-ID] [PubMed:known-id]"
    )
