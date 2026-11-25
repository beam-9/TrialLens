"""A pure paper rewrite gets verified prior packets in both generation passes."""
import json

import pytest
from fastapi.testclient import TestClient

from triallens import conversation, main
from triallens.models import Answer, EvidenceSource, SourceType, Workspace
from triallens.provenance import source_revision
from triallens.rag import build_chunks
from triallens.store import JsonStore

CAPTION = "Full text figure caption 001"
REWRITE = "Explain that more simply, keeping the treatment groups, 16-week numbers and their limits."


@pytest.mark.parametrize(
    ("variant", "carries", "accepted"),
    [
        ("rewrite", True, True),
        ("document", True, True),
        ("unsupported", True, False),
        ("stale", False, False),
        ("tampered", False, False),
        ("outside_scope", False, False),
        ("new_outcome", False, False),
        ("new_timepoint", False, False),
    ],
)
def test_ask_carries_current_paper_packet_for_a_pure_rewrite(monkeypatch, tmp_path, variant, carries, accepted):
    store = JsonStore(tmp_path / "triallens.json")
    workspace = store.create_workspace(Workspace(
        condition="diabetes", intervention="Drug A", source_types=[SourceType.pubmed, SourceType.fda_label],
    ))
    paper = EvidenceSource(
        workspace_id=workspace.id, source_type=SourceType.pubmed, external_id="123", title="Drug A trial",
        abstract="Drug A and placebo were compared for 16 weeks. The groups differed by -0.6%.",
        metadata={
            "paper_packet_version": 1,
            "sections": {CAPTION: "Figure 2. Adjusted week-16 HbA1c change from baseline, Drug A minus placebo: -0.6%, 95% CI -1.0 to -0.2."},
            "full_text": {"status": "available", "caption_sections": [CAPTION], "partial_indexing": True},
        },
    )
    label = EvidenceSource(
        workspace_id=workspace.id, source_type=SourceType.fda_label, external_id="456",
        title="Drug A label", abstract="Drug A is a therapy for diabetes.",
    )
    sources = [paper, label]
    kwargs = {}
    if variant == "outside_scope":
        kwargs = {"source_types": ["fda_label"]}
    if variant == "document":
        kwargs = {"mode": "document", "source_id": paper.id}
    previous_chunks = main.retriever.retrieve(workspace, "Drug A HbA1c", build_chunks(sources), sources)
    packet = next(chunk for chunk in previous_chunks if chunk.section == CAPTION)
    revision = source_revision(paper)
    if variant == "tampered":
        packet = packet.model_copy(update={"text": packet.text.replace("-1.0", "-1.1")})
    parent = store.save_answer(Answer(
        workspace_id=workspace.id, question="Compare Drug A and placebo at 16 weeks for HbA1c.",
        generation_mode="conversational", short_answer="A study estimate.",
        direct_answer="At 16 weeks the adjusted difference was -0.6%, 95% CI -1.0 to -0.2 [PubMed:123].",
        citations=["PubMed:123"], retrieved_chunks=[packet], evidence=[], limitations=[],
        source_revisions={"PubMed:123": revision}, **kwargs,
    ))
    if variant == "stale":
        paper = paper.model_copy(update={"abstract": paper.abstract + " An updated abstract."})
        sources = [paper, label]
    # Rebuild current chunks, which gives them different IDs from the saved answer.
    store.replace_workspace_evidence(workspace.id, sources, build_chunks(sources))
    monkeypatch.setattr(main, "store", store)
    retrieve = main.retriever.retrieve_conversation

    def rerank(workspace, question, chunks, sources, source_types):
        return retrieve(workspace, question, [c for c in chunks if c.section != CAPTION], sources, source_types)

    monkeypatch.setattr(main.retriever, "retrieve_conversation", rerank)
    monkeypatch.setenv("TRIALLENS_CHAT_PROVIDER", "cloudflare")
    monkeypatch.setenv("TRIALLENS_USAGE_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(conversation, "chat_configured", lambda: True)
    calls = []

    def complete(messages, schema):
        records = json.loads(messages[1]["content"])["evidence"]
        calls.append(records)
        level = "96%" if variant == "unsupported" else "95%"
        return json.dumps({
            "paragraphs": [f"After 16 weeks, HbA1c changed by -0.6% more with Drug A than with placebo ({level} CI -1.0 to -0.2) [PubMed:123]."],
            "cited_sources": ["PubMed:123"],
            "uncertainty": ["The indexed excerpts cover 16 weeks [PubMed:123]."],
        })

    monkeypatch.setattr(conversation.cloudflare, "completion", complete)
    question = REWRITE
    if variant == "new_outcome":
        question = "Explain that more simply and tell me about mortality."
    if variant == "new_timepoint":
        question = REWRITE.replace("16-week", "24-week")
    response = TestClient(main.app).post(f"/workspaces/{workspace.id}/ask", json={
        "question": question, "previous_answer_id": parent.id, **kwargs,
    })

    assert response.status_code == 200
    assert len(calls) == 2 and calls[0] == calls[1]
    for records in calls:
        links = [link["section"] for record in records for link in record.get("paper_passage_links", [])]
        assert (CAPTION in links) is carries
        if variant == "outside_scope":
            assert all(record["source_type"] == "fda_label" for record in records)
        if variant == "document":
            assert [record["citation"] for record in records] == ["PubMed:123"]
    answer = response.json()
    assert (answer["generation_mode"] == "conversational") is accepted
    if accepted:
        assert "95% CI -1.0 to -0.2" in answer["direct_answer"]
        assert any(chunk["section"] == CAPTION for chunk in answer["retrieved_chunks"])
