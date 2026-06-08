from triallens.models import EvidenceSource, SourceType, Workspace
from triallens.rag import AnswerService, Retriever, build_chunks


def test_retrieval_preserves_source_metadata():
    workspace = Workspace(condition="type 2 diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="123",
        title="Metformin evidence in type 2 diabetes",
        abstract="Metformin is studied in type 2 diabetes and is commonly evaluated for glycemic outcomes.",
        url="https://pubmed.ncbi.nlm.nih.gov/123/",
    )
    chunks = build_chunks([source])
    retrieved = Retriever().retrieve(workspace, "What evidence exists for metformin in diabetes?", chunks, [source])
    assert retrieved
    assert retrieved[0].citation == "PubMed:123"
    assert retrieved[0].title == "Metformin evidence in type 2 diabetes"
    assert retrieved[0].url == "https://pubmed.ncbi.nlm.nih.gov/123/"
    assert "metformin" in retrieved[0].matched_terms


def test_topic_relevance_beats_generic_overlap():
    workspace = Workspace(condition="migraine", intervention="sumatriptan", source_types=[SourceType.pubmed])
    relevant = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="rel",
        title="Sumatriptan treatment for migraine",
        abstract="Sumatriptan is indicated for acute migraine and is evaluated for treatment response.",
    )
    generic = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="gen",
        title="General clinical safety",
        abstract="Clinical treatment evidence discusses safety and benefits for adults in broad care settings.",
    )
    sources = [generic, relevant]
    retrieved = Retriever().retrieve(
        workspace,
        "What are the main benefits for sumatriptan in migraine?",
        build_chunks(sources),
        sources,
    )
    assert retrieved
    assert retrieved[0].citation == "PubMed:rel"


def test_safety_question_prioritizes_fda_label():
    workspace = Workspace(condition="migraine", intervention="sumatriptan", source_types=[SourceType.pubmed, SourceType.fda_label])
    pubmed = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="paper",
        title="Sumatriptan migraine efficacy",
        abstract="Sumatriptan is used for acute migraine treatment and response outcomes.",
    )
    label = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.fda_label,
        external_id="label",
        title="FDA label for sumatriptan migraine warnings",
        abstract="Sumatriptan migraine labeling describes warnings, adverse reactions, myocardial ischemia, and stroke risks.",
    )
    sources = [pubmed, label]
    retrieved = Retriever().retrieve(
        workspace,
        "What safety warnings matter for sumatriptan in migraine?",
        build_chunks(sources),
        sources,
    )
    assert retrieved
    assert retrieved[0].source_type == SourceType.fda_label


def test_answer_abstains_without_direct_evidence():
    workspace = Workspace(condition="asthma", source_types=[SourceType.pubmed])
    answer = AnswerService().answer(workspace, "What should I take?", [])
    assert "do not have enough" in answer.short_answer
    assert answer.citations == []
    assert answer.uncertainty

