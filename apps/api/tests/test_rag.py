from triallens.models import EvidenceSource, SourceType, Workspace
from triallens.rag import AnswerService, Retriever, build_chunks


def test_retrieval_returns_citations():
    workspace = Workspace(condition="type 2 diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="123",
        title="Metformin evidence",
        abstract="Metformin is studied in type 2 diabetes and is commonly evaluated for glycemic outcomes.",
    )
    chunks = build_chunks([source])
    retrieved = Retriever().retrieve("What evidence exists for metformin in diabetes?", chunks)
    assert retrieved
    assert retrieved[0].citation == "PubMed:123"


def test_answer_abstains_without_evidence():
    workspace = Workspace(condition="asthma", source_types=[SourceType.pubmed])
    answer = AnswerService().answer(workspace, "What should I take?", [])
    assert "do not have enough" in answer.short_answer
    assert answer.citations == []

