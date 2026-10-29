"""Real public packet pipeline and hostile context controls; no inference."""
import asyncio
import json
from pathlib import Path

import httpx

from triallens.conversation import build_evidence_records
from triallens.models import EvidenceSource, RetrievedChunk, SourceType, Workspace
from triallens.rag import AnswerService, Retriever, build_chunks, document_content_scope
from triallens.sources import ClinicalTrialsClient
from triallens.text import normalize
from triallens.trial_results import MAX_PACKET_CHARS

FIXTURE = Path(__file__).resolve().parents[1] / "evaluation/answer_coverage/fixtures/ctgov-NCT01563029-2026-10-28.json"


def load_source(monkeypatch):
    study = json.loads(FIXTURE.read_text())
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"studies": [study]})), **kwargs))
    workspace = Workspace(condition="asthma", intervention="fluticasone furoate", source_types=[SourceType.clinical_trials])
    sources = asyncio.run(ClinicalTrialsClient().fetch(workspace))
    return workspace, sources[0]


def test_real_posted_outcomes_survive_index_retrieve_context(monkeypatch):
    workspace, source = load_source(monkeypatch)
    assert source.metadata["indexed_content"] == "protocol_and_outcome_measurements"
    assert source.metadata["outcome_packet_version"] == 1
    chunks = build_chunks([source])
    packets = [c for c in chunks if c.section.startswith("Results outcome ")]
    assert len(packets) == 8
    for chunk in packets:
        assert chunk.text == normalize(source.metadata["sections"][chunk.section])
        assert len(chunk.text) <= MAX_PACKET_CHARS
    question = "What is the numerical morning PEF result for FF 50 versus placebo over 12 weeks, including confidence interval and group sizes?"
    retrieved = Retriever().retrieve_conversation(workspace, question, chunks, [source])
    assert any(c.section == "Results outcome 001" for c in retrieved)
    records = build_evidence_records([source], retrieved)
    context = records[0]
    primary = next(c.text for c in packets if c.section == "Results outcome 001")
    assert primary in context["matched_passages"]
    assert "118" in primary and "119" in primary and "19.5" in primary
    assert "12.1" in primary and "26.9" in primary
    assert "not the full results record" in document_content_scope(source)
    assert sum(len(r["text"]) + sum(map(len, r["matched_passages"])) for r in records) <= 28000
    fallback = AnswerService().answer(workspace, question, retrieved, [])
    assert "Posted numerical trial outcomes" in fallback.direct_answer
    assert "numerical results were not extracted" not in fallback.direct_answer


def test_atomic_packet_borrows_budget_without_splitting_or_losing_citation(monkeypatch):
    workspace, source = load_source(monkeypatch)
    full = normalize(source.metadata["sections"]["Results outcome 001"])
    chunk = RetrievedChunk(chunk_id="primary", source_id=source.id, source_type=source.source_type,
        citation=f"ClinicalTrials.gov:{source.external_id}", text=full, section="Results outcome 001", score=1)
    backgrounds = [EvidenceSource(id=f"other-{i}", workspace_id=workspace.id, source_type=SourceType.pubmed,
        external_id=str(i), title="Other evidence", abstract="Background. " * 1000) for i in range(7)]
    records = build_evidence_records([*backgrounds, source], [chunk])
    assert records[0]["citation"] == chunk.citation
    assert full in records[0]["matched_passages"]
    assert len(records) == 8
    assert records[0]["content_truncated"]  # Other indexed outcomes are not all included.
    assert sum(len(r["text"]) + sum(map(len, r["matched_passages"])) for r in records) <= 28000


def test_invalid_or_oversized_atomic_fragments_are_not_sent(monkeypatch):
    _, source = load_source(monkeypatch)
    for text in ["value=19", "z" * (MAX_PACKET_CHARS + 1)]:
        fragment = RetrievedChunk(chunk_id="bad", source_id=source.id, source_type=source.source_type,
            citation=f"ClinicalTrials.gov:{source.external_id}", text=text, section="Results outcome 001", score=1)
        record = build_evidence_records([source], [fragment])[0]
        assert record["matched_passages"] == []
        assert record["content_truncated"]
    source.metadata["sections"]["Results outcome 001"] = "z" * (MAX_PACKET_CHARS + 1)
    assert all(c.section != "Results outcome 001" for c in build_chunks([source]))


def test_atomic_result_keeps_priority_after_ordinary_matches(monkeypatch):
    _, source = load_source(monkeypatch)
    packet = normalize(source.metadata["sections"]["Results outcome 001"])
    ordinary = [RetrievedChunk(chunk_id=f"normal-{i}", source_id=source.id, source_type=source.source_type,
        citation=f"ClinicalTrials.gov:{source.external_id}", text=("Ordinary protocol details. " * 30) + str(i),
        section="Brief summary", score=1) for i in range(4)]
    atomic = RetrievedChunk(chunk_id="atomic", source_id=source.id, source_type=source.source_type,
        citation=f"ClinicalTrials.gov:{source.external_id}", text=packet, section="Results outcome 001", score=0.9)
    others = [EvidenceSource(id=f"other-{i}", workspace_id=source.workspace_id, source_type=SourceType.pubmed,
        external_id=str(i), title="Background", abstract="Background. " * 300) for i in range(7)]
    records = build_evidence_records([source, *others], [*ordinary, atomic])
    assert records[0]["matched_passages"][0] == packet
    assert sum(len(r["text"]) + sum(map(len, r["matched_passages"])) for r in records) <= 28000


def test_duplicate_passage_space_is_reclaimed_for_later_abstract_fact():
    beginning = "Background words. " * 30
    text = beginning + "x" * (3300-len(beginning)) + " Later fact retained. " + "y" * 2000
    source = EvidenceSource(id="first", workspace_id="w", source_type=SourceType.pubmed,
        external_id="first", title="First source", abstract=text)
    passage = RetrievedChunk(chunk_id="first", source_id="first", source_type=SourceType.pubmed,
        citation="PubMed:first", text=beginning, score=1)
    others = [source.model_copy(update={"id": str(i), "external_id": str(i)}) for i in range(7)]
    record = build_evidence_records([source, *others], [passage])[0]
    assert record["matched_passages"] == []
    assert "Later fact retained" in record["text"]


def test_statistics_gap_does_not_claim_index_wide_absence():
    from triallens.rag import statistics_abstention_answer
    workspace = Workspace(condition="asthma", source_types=[SourceType.clinical_trials])
    answer = statistics_abstention_answer(workspace, "Give outcome statistics", [], [], [])
    assert "passages selected" in answer.direct_answer
    assert "Other indexed passages" in answer.direct_answer
    assert "indexed sources mention" not in answer.direct_answer
    assert "not establish" in answer.limitations[0]
