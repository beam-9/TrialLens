"""Context scope metadata must describe loss, not redundant text removal."""
import json

import pytest

from triallens.conversation import ConversationService
from triallens.models import Answer, EvidenceSource, RetrievedChunk, SourceType, Workspace


@pytest.mark.parametrize("abstract,passages,truncated", [
    ("Complete short source text.", ["Complete short source text."], False),
    ("word " * 2500, [], True),
    ("Short source.", ["match " * 5000], True),
    ("Short source.", ["first " * 2400, "second " * 2400, "third " * 2400], True),
])
def test_context_truncation_tracks_actual_loss(monkeypatch, tmp_path, abstract, passages, truncated):
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "ollama")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    workspace = Workspace(condition="diabetes", source_types=[SourceType.pubmed])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed, external_id="audit", title="Trial", abstract=abstract,
                            metadata={"publication_types": ["Randomized Controlled Trial"]})
    fallback = Answer(workspace_id=workspace.id, question="What changed?", short_answer="Extracted result", evidence=[], limitations=[], citations=[], retrieved_chunks=[
        RetrievedChunk(chunk_id=f"chunk-{index}", source_id=source.id, source_type=source.source_type, citation="PubMed:audit", text=passage, score=1)
        for index, passage in enumerate(passages)
    ])
    captured = []
    def completion(messages):
        captured.append(json.loads(messages[1]["content"]))
        return json.dumps({"paragraphs": ["The indexed source cannot establish individual suitability."], "cited_sources": [], "uncertainty": []})
    monkeypatch.setattr(ConversationService, "_local_completion", staticmethod(completion))
    ConversationService().generate(workspace, "What did the trial report?", [], [source], fallback)
    record = captured[0]["evidence"][0]
    assert len(captured) == 2
    assert all(item["evidence"][0]["publication_types"] == ["Randomized Controlled Trial"] for item in captured)
    assert record["content_truncated"] is truncated
    if not truncated:
        assert record["text"] == abstract and record["matched_passages"] == []


@pytest.mark.parametrize("status,phase,date", [("COMPLETED", "PHASE2", "2024-03-12"), (None, None, None)])
def test_registry_status_reaches_both_passes_without_inventing_results(monkeypatch, tmp_path, status, phase, date):
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr("triallens.conversation.chat_configured", lambda: True)
    workspace = Workspace(condition="diabetes", source_types=[SourceType.clinical_trials])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.clinical_trials,
        external_id="NCT-CONTEXT", title="Study registration", status=status, phase=phase, publication_date=date,
        abstract="The trial will evaluate glucose metabolism; this stored description has no posted results.")
    fallback = Answer(workspace_id=workspace.id, question="Is it ongoing?", short_answer="Source excerpt",
                      evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    captured = []
    def completion(messages, schema):
        captured.append(json.loads(messages[1]["content"])["evidence"][0])
        return json.dumps({"paragraphs": ["The supplied description does not establish measured treatment effects [ClinicalTrials.gov:NCT-CONTEXT]."],
                           "cited_sources": ["ClinicalTrials.gov:NCT-CONTEXT"], "uncertainty": []})
    monkeypatch.setattr("triallens.conversation.cloudflare.completion", completion)
    monkeypatch.setattr("triallens.conversation.httpx.post", lambda *a, **k: pytest.fail("No inference permitted"))
    answer = ConversationService().generate(workspace, "Is this trial ongoing and does it provide results?", [], [source], fallback)
    assert answer.generation_mode == "conversational" and len(captured) == 2
    for record in captured:
        assert record["status"] == status and record["phase"] == phase and record["publication_date"] == date
        assert record["text"] == source.abstract
        assert "not whether measured results are posted" in record["metadata_scope"]


@pytest.mark.parametrize("metadata,expected_scope", [
    ({"indexed_content": "protocol_descriptions", "api_results_section_state": "present"}, "structured results tables were not indexed"),
    ({"sections": {"Brief summary": "Will measure outcomes", "Detailed description": "Expected benefit"}}, "benefits are protocol claims, not observed effects"),
    ({"sections": {"Brief summary": "Study design", "Results": "Measured outcome"}}, "posted structured results may be incomplete unless indexed"),
    ({}, "posted structured results may be incomplete unless indexed"),
])
def test_registry_content_scope_uses_indexed_sections_not_status(metadata, expected_scope):
    from triallens.rag import document_content_scope
    source = EvidenceSource(workspace_id="scope", source_type=SourceType.clinical_trials,
                            external_id="NCT-SCOPE", title="Completed study", status="COMPLETED",
                            abstract="The trial will measure outcomes.", metadata=metadata)
    scope = document_content_scope(source)
    assert expected_scope in scope
    assert "no results exist" not in scope
    assert "still ongoing" not in scope


def test_context_exposes_section_names_without_treating_them_as_results(monkeypatch, tmp_path):
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr("triallens.conversation.chat_configured", lambda: True)
    workspace = Workspace(condition="condition", source_types=[SourceType.clinical_trials])
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.clinical_trials,
        external_id="NCT-SECTIONS", title="Protocol", status="COMPLETED", abstract="The study will measure outcomes.",
        metadata={"sections": {"Brief summary": "The study will measure outcomes.", "Detailed description": "", "Malformed": 42}})
    captured = []
    def completion(messages, schema):
        captured.append(json.loads(messages[1]["content"])["evidence"][0])
        return json.dumps({"paragraphs": ["The supplied description gives planned outcomes [ClinicalTrials.gov:NCT-SECTIONS]."],
                           "cited_sources": ["ClinicalTrials.gov:NCT-SECTIONS"], "uncertainty": []})
    monkeypatch.setattr("triallens.conversation.cloudflare.completion", completion)
    fallback = Answer(workspace_id=workspace.id, question="What did it find?", short_answer="Excerpt",
                      evidence=[], limitations=[], citations=[], retrieved_chunks=[])
    ConversationService().generate(workspace, fallback.question, [], [source], fallback)
    assert len(captured) == 2
    for record in captured:
        assert record["indexed_section_names"] == ["Brief summary"]
        assert "benefits are protocol claims, not observed effects" in record["content_scope"]
        assert record["status"] == "COMPLETED"
        assert record["text"] == source.abstract
