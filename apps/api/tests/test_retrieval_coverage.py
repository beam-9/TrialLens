"""Passage-level retrieval coverage; no model, provider or production store."""
import json
from pathlib import Path

from triallens.models import EvidenceChunk, EvidenceSource, SourceType, Workspace
from triallens.rag import Retriever, stable_embedding


def test_benefit_limitations_questions_do_not_lose_completed_benefit_evidence():
    workspace = Workspace(condition="migraine", intervention="sumatriptan", source_types=list(SourceType))
    label = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.fda_label,
        external_id="label", title="Sumatriptan migraine safety warnings and limitations",
        abstract="Sumatriptan safety risks include myocardial ischemia and stroke.")
    benefit = EvidenceSource(workspace_id=workspace.id, source_type=SourceType.pubmed,
        external_id="benefit", title="Sumatriptan migraine completed trial",
        abstract="Sumatriptan improved migraine pain relief compared with placebo in a completed trial.")
    chunks = [EvidenceChunk(workspace_id=workspace.id, source_id=source.id,
        source_type=source.source_type, citation=source.external_id,
        text=source.abstract, embedding=stable_embedding(source.abstract))
        for source, count in [(label, 12), (benefit, 1)] for _ in range(count)]
    retriever = Retriever()
    for question in ("What are the benefits and main limitations?",
                     "Explain the efficacy and limitations of sumatriptan for migraine."):
        result = retriever.retrieve_conversation(workspace, question, chunks, [label, benefit])
        assert {label.id, benefit.id} <= {chunk.source_id for chunk in result}
        assert len(result) <= 8
        assert len(result) == len({chunk.chunk_id for chunk in result})
        filtered = retriever.retrieve_conversation(workspace, question, chunks, [label, benefit], [SourceType.pubmed])
        assert filtered and all(chunk.source_id == benefit.id for chunk in filtered)


def test_frozen_real_broad_question_retrieves_standalone_indication_and_safety_passages():
    fixture = Path(__file__).resolve().parents[1] / "evaluation/m0/snapshots/real-metformin.json"
    data = json.loads(fixture.read_text())
    workspace = Workspace.model_validate(data["workspace"])
    sources = [EvidenceSource.model_validate(source) for source in data["sources"]]
    chunks = [EvidenceChunk.model_validate(chunk) for chunk in data["chunks"]]
    result = Retriever().retrieve_conversation(workspace,
        "What do these sources tell us about the benefits and main limitations of metformin for type 2 diabetes?",
        chunks, sources)
    # Manually curated relevant passages: the standalone indication includes
    # adjunct diet/exercise + age >=10; trial safety includes GI limitations.
    required = {"m0-real-chunk-006", "m0-real-chunk-019"}
    assert required <= {chunk.chunk_id for chunk in result}
    # These remain available when the generator excludes the ZITUVIMET label.
    assert all(chunk.source_id == "m0-real-source-07" for chunk in result if chunk.chunk_id in required)
    assert len({chunk.source_id for chunk in result}) > 3
    assert len(result) <= 8
