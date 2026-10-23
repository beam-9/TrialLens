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
    source = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed, external_id="audit", title="Trial", abstract=abstract)
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
    assert record["content_truncated"] is truncated
    if not truncated:
        assert record["text"] == abstract and record["matched_passages"] == []
