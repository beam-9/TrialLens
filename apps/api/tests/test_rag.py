from triallens.models import EvidenceSource, SourceType, Workspace
from triallens.rag import AnswerService, Retriever, build_chunks, build_extractions


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


def test_statistics_question_does_not_invent_numbers_from_topical_sources():
    workspace = Workspace(condition="acne", intervention="azelaic acid", source_types=[SourceType.pubmed])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="topical",
        title="Azelaic acid and acne",
        abstract="Azelaic acid is used to treat acne and is discussed as a topical therapy in dermatology.",
    )
    chunks = build_chunks([source])
    retrieved = Retriever().retrieve(
        workspace,
        "What statistics back up the effectiveness of azelaic acid on acne?",
        chunks,
        [source],
    )
    answer = AnswerService().answer(workspace, "What statistics back up the effectiveness of azelaic acid on acne?", retrieved)
    assert "did not find quantitative effectiveness statistics" in answer.direct_answer
    assert "does not invent statistics" in answer.limitations[0]


def test_statistics_question_surfaces_numeric_outcome_passages():
    workspace = Workspace(condition="acne", intervention="azelaic acid", source_types=[SourceType.pubmed])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="stats",
        title="Azelaic acid acne efficacy trial",
        abstract="Azelaic acid improved acne lesion counts by 42% at 12 weeks, with a response rate of 65% compared with 40% for vehicle.",
    )
    chunks = build_chunks([source])
    retrieved = Retriever().retrieve(
        workspace,
        "What statistics back up the effectiveness of azelaic acid on acne?",
        chunks,
        [source],
    )
    answer = AnswerService().answer(workspace, "What statistics back up the effectiveness of azelaic acid on acne?", retrieved)
    assert "42%" in " ".join(answer.supporting_evidence)
    assert "65%" in " ".join(answer.supporting_evidence)


def test_extractions_preserve_source_links_and_citations():
    workspace = Workspace(condition="acne", intervention="azelaic acid", source_types=[SourceType.pubmed])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="12345",
        title="Azelaic acid acne efficacy trial",
        abstract="Patients with acne used azelaic acid. Azelaic acid improved acne lesion counts by 42% at 12 weeks.",
        url="https://pubmed.ncbi.nlm.nih.gov/12345/",
        publication_date="2015",
        metadata={"authors": ["Thomas AB", "Nguyen CD"]},
    )
    extraction = build_extractions([source], workspace)[0]
    assert extraction.citation == "PubMed:12345"
    assert extraction.source_url == "https://pubmed.ncbi.nlm.nih.gov/12345/"
    assert extraction.publication_date == "2015"
    assert extraction.authors == ["Thomas AB", "Nguyen CD"]
    assert extraction.has_quantitative_result
    assert "42%" in extraction.outcome_result
    assert extraction.source_overview
    assert extraction.methods_context
    assert extraction.key_findings
    assert extraction.evidence_limitations
    assert extraction.source_understanding
    assert any("Source profile:" in note for note in extraction.source_understanding)
    assert any("Outcome/result understood:" in note for note in extraction.source_understanding)
    assert extraction.source_passages
    assert any("Outcome/result:" in passage for passage in extraction.source_passages)
    assert extraction.field_evidence["Population / context"]
    assert extraction.field_evidence["Outcome / result"]
    assert "42%" in extraction.field_evidence["Outcome / result"]


def test_sectioned_sources_create_section_chunks_and_extractions():
    workspace = Workspace(condition="type 2 diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="sectioned",
        title="Metformin sectioned abstract",
        abstract="Background adults used metformin. Results HbA1c improved by 1.2%.",
        metadata={
            "sections": {
                "Background": "Adults with type 2 diabetes used metformin in routine care.",
                "Results": "HbA1c improved by 1.2% after 24 weeks.",
            }
        },
    )
    chunks = build_chunks([source])
    extraction = build_extractions([source], workspace)[0]
    assert {chunk.section for chunk in chunks} == {"Background", "Results"}
    assert any(section.startswith("Background:") for section in extraction.source_sections)
    assert any(section.startswith("Results:") for section in extraction.source_sections)
    assert any("Design/context understood:" in note for note in extraction.source_understanding)
    assert any("Source section:" in passage for passage in extraction.source_passages)
    assert "Results:" in extraction.field_evidence["Outcome / result"]


def test_answer_prefers_extraction_rows_over_raw_chunks():
    workspace = Workspace(condition="acne", intervention="azelaic acid", source_types=[SourceType.pubmed])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="stats",
        title="Azelaic acid acne efficacy trial",
        abstract="Patients with acne used azelaic acid. Azelaic acid improved acne lesion counts by 42% at 12 weeks, with a response rate of 65%.",
    )
    chunks = build_chunks([source])
    retrieved = Retriever().retrieve(workspace, "What statistics support effectiveness?", chunks, [source])
    extractions = build_extractions([source], workspace)
    answer = AnswerService().answer(workspace, "What statistics support effectiveness?", retrieved, extractions)
    joined = " ".join(answer.supporting_evidence)
    evidence_map = " ".join(answer.evidence_map)
    reasoning = " ".join(answer.reasoning_summary)
    synthesis = " ".join(answer.evidence_synthesis)
    readouts = " ".join(answer.source_readouts)
    quality = " ".join(answer.evidence_quality)
    assert "extraction" in answer.limitations[0].lower()
    assert "42%" in joined
    assert "65%" in joined
    assert "42%" in answer.direct_answer
    assert "[PubMed:stats]" in answer.direct_answer
    assert "extraction table found" not in answer.direct_answer.lower()
    assert "considered 1 extracted source rows" in evidence_map
    assert "1 rows matched" in evidence_map
    assert "statistics question" in reasoning
    assert "Selection basis" in reasoning
    assert "Whole-workspace read" in synthesis
    assert "Literature view" in synthesis
    assert len(answer.source_readouts) == 1
    assert "CITED" in readouts
    assert "Quantitative support" in quality
    assert "Source strength" in quality


def test_direct_answer_excludes_protocol_only_context_and_cites_the_supported_claim():
    workspace = Workspace(
        condition="type 2 diabetes",
        intervention="metformin",
        source_types=[SourceType.clinical_trials, SourceType.fda_label],
    )
    protocol = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.clinical_trials,
        external_id="NCT-addon",
        title="Sitagliptin added to metformin",
        abstract="This study will assess sitagliptin added to metformin in adults with type 2 diabetes.",
    )
    label = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.fda_label,
        external_id="metformin-label",
        title="FDA label for metformin hydrochloride",
        abstract="Metformin hydrochloride tablets are indicated as an adjunct to diet and exercise to improve glycemic control in adults with type 2 diabetes.",
    )
    sources = [protocol, label]
    question = "What are the main benefits of metformin for type 2 diabetes?"
    answer = AnswerService().answer(
        workspace,
        question,
        Retriever().retrieve(workspace, question, build_chunks(sources), sources),
        build_extractions(sources, workspace),
    )

    assert "improve glycemic control" in answer.direct_answer.lower()
    assert "[openFDA label:metformin-label]" in answer.direct_answer
    assert "NCT-addon" not in answer.direct_answer
    assert "ClinicalTrials.gov:NCT-addon" not in answer.citations
    assert "cannot quantify the benefit" in answer.direct_answer


def test_safety_answer_synthesizes_reactions_and_excludes_administrative_text():
    workspace = Workspace(
        condition="acne",
        intervention="azelaic acid",
        source_types=[SourceType.pubmed, SourceType.clinical_trials, SourceType.fda_label],
    )
    label = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.fda_label,
        external_id="azelaic-label",
        title="FDA label for azelaic acid gel 15%",
        abstract=(
            "The most common adverse reactions were burning, stinging, or tingling (29%), pruritus (11%), "
            "dry skin (8%), and erythema or irritation (4%). Hypersensitivity reactions including angioedema, "
            "eye or facial swelling, and urticaria have been reported. To report suspected adverse reactions, "
            "contact the manufacturer or FDA at 1-800-FDA-1088 or www.fda.gov/medwatch."
        ),
        url="https://example.test/azelaic-label",
        metadata={
            "sections": {
                "Adverse reactions": "The most common adverse reactions were burning, stinging, or tingling (29%), pruritus (11%), dry skin (8%), and erythema or irritation (4%).",
                "Warnings": "Hypersensitivity reactions including angioedema, eye or facial swelling, and urticaria have been reported.",
            }
        },
    )
    study = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="azelaic-study",
        title="Azelaic acid tolerability in blemish-prone skin",
        abstract=(
            "Twenty-three participants used a retinal and azelaic acid formulation for eight weeks. "
            "Adverse events were few, mild and transient. The combination had good tolerability, but the "
            "study cannot isolate the contribution of azelaic acid."
        ),
        url="https://pubmed.ncbi.nlm.nih.gov/999/",
        publication_date="2015",
        metadata={"authors": ["Thomas AB", "Nguyen CD"]},
    )
    protocol = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.clinical_trials,
        external_id="NCT-protocol",
        title="Azelaic acid maintenance protocol",
        abstract="The purpose of this study is to assess azelaic acid, which has potential in maintenance therapy due to its good tolerability and safety.",
    )
    animal = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="dairy-cows",
        title="Azelaic acid for teat keratosis in dairy cows",
        abstract="Azelaic acid was evaluated for safety in dairy cows with teat keratosis.",
    )
    sources = [label, study, protocol, animal]
    question = "What are the main safety concerns?"
    answer = AnswerService().answer(
        workspace,
        question,
        Retriever().retrieve(workspace, question, build_chunks(sources), sources),
        build_extractions(sources, workspace),
    )

    normalized = answer.direct_answer.lower()
    assert normalized.startswith("according to 2 directly relevant indexed sources")
    assert "burning" in normalized
    assert "pruritus" in normalized
    assert "angioedema" in normalized
    assert "few, mild and transient" in normalized
    assert "fda-1088" not in normalized
    assert "medwatch" not in normalized
    assert "contact the manufacturer" not in normalized
    assert "purpose of this study" not in normalized
    assert "dairy cows" not in normalized
    assert answer.citations == ["openFDA label:azelaic-label", "PubMed:azelaic-study"]


def test_document_answer_uses_only_selected_source_content():
    workspace = Workspace(condition="type 2 diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    selected = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="selected",
        title="Metformin gastrointestinal tolerability",
        abstract="Adults with type 2 diabetes used metformin. Gastrointestinal tolerability affected adherence and persistence with metformin therapy.",
    )
    other = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="other",
        title="Other source with liver toxicity",
        abstract="This other source discusses liver toxicity, hepatic enzymes, and unrelated safety outcomes.",
    )
    chunks = build_chunks([selected, other])
    selected_chunks = [chunk for chunk in chunks if chunk.source_id == selected.id]
    retrieved = Retriever().retrieve(workspace, "What does this document say about adherence?", selected_chunks, [selected])
    answer = AnswerService().answer_document(workspace, selected, "What does this document say about adherence?", selected_chunks, retrieved)
    joined = " ".join(answer.supporting_evidence + answer.uncertainty + answer.limitations)
    assert answer.citations == ["PubMed:selected"]
    assert "adherence" in joined.lower()
    assert "liver toxicity" not in joined.lower()
    assert "Single document" in " ".join(item.value for item in answer.answer_trace)


def test_document_answer_abstains_when_selected_source_does_not_cover_question():
    workspace = Workspace(condition="type 2 diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="abstract",
        title="Metformin adherence abstract",
        abstract="Adults with type 2 diabetes used metformin. The abstract discusses adherence and gastrointestinal tolerability.",
    )
    chunks = build_chunks([source])
    answer = AnswerService().answer_document(workspace, source, "What does this document say about liver toxicity?", chunks, [])
    joined = " ".join(answer.direct_answer for _ in [0])
    assert "does not cover" in joined
    assert answer.supporting_evidence == []
    assert answer.citations == ["PubMed:abstract"]
    assert "Workspace" not in joined


def test_document_answer_keeps_faers_causality_caveat():
    workspace = Workspace(condition="migraine", intervention="sumatriptan", source_types=[SourceType.fda_adverse_event])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.fda_adverse_event,
        external_id="FDA-AE-sumatriptan",
        title="openFDA adverse event report counts for sumatriptan",
        abstract="Top reported reactions in openFDA for sumatriptan: nausea (80 reports); dizziness (30 reports). These are spontaneous reports and cannot establish causality or incidence.",
    )
    chunks = build_chunks([source])
    answer = AnswerService().answer_document(workspace, source, "What reactions are reported?", chunks, [])
    joined = " ".join([answer.direct_answer] + answer.limitations + answer.uncertainty + answer.safety_limitations)
    assert "spontaneous" in joined.lower()
    assert "cannot establish causality" in joined.lower()
    assert "80 reports" in " ".join(answer.supporting_evidence)


def test_answer_uses_source_understanding_fields_for_relevance():
    workspace = Workspace(condition="type 2 diabetes", intervention="metformin", source_types=[SourceType.pubmed])
    relevant = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="relevant",
        title="Metformin adherence and gastrointestinal tolerability",
        abstract=(
            "Adults with type 2 diabetes using metformin were followed in a prospective cohort. "
            "The study found gastrointestinal tolerability affected adherence and persistence with therapy. "
            "No numerical outcome table was available in the indexed abstract."
        ),
    )
    shallow = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="shallow",
        title="General diabetes care",
        abstract="Diabetes care includes many drug and lifestyle options for adult patients.",
    )
    context = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.fda_adverse_event,
        external_id="context",
        title="openFDA adverse event report counts for unrelated therapy",
        abstract="Top reported reactions in openFDA for unrelated therapy: headache (12 reports). These are spontaneous reports and cannot establish causality or incidence.",
    )
    sources = [shallow, relevant, context]
    extractions = build_extractions(sources, workspace)
    question = "What does the evidence say about metformin benefits, safety, tolerability, and adherence?"
    retrieved = Retriever().retrieve(workspace, question, build_chunks(sources), sources)
    answer = AnswerService().answer(workspace, question, retrieved, extractions)
    joined = " ".join(answer.supporting_evidence)
    evidence_map = " ".join(answer.evidence_map)
    reasoning = " ".join(answer.reasoning_summary)
    synthesis = " ".join(answer.evidence_synthesis)
    readouts = " ".join(answer.source_readouts)
    quality = " ".join(answer.evidence_quality)
    facets = " ".join(answer.facet_coverage)
    trace = " ".join(f"{item.label} {item.value} {item.detail}" for item in answer.answer_trace)
    assert "adherence" in joined.lower()
    assert "tolerability" in joined.lower()
    assert "relevant" in " ".join(answer.citations)
    assert "context" not in " ".join(answer.citations)
    assert "considered 3 extracted source rows" in evidence_map
    assert "Question fit:" in evidence_map
    assert "Question anchors:" in reasoning
    assert "Synthesis scope:" in reasoning
    assert "Whole-workspace read" in synthesis
    assert "Shared signal:" in synthesis
    assert len(answer.source_readouts) == len(extractions)
    assert "CITED" in readouts
    assert "FDA adverse-event signal" in readouts
    assert "Benefit/outcome:" in facets
    assert "Safety/limitations:" in facets
    assert "Question read" in trace
    assert "Workspace scan" in trace
    assert "Cited rows" in trace
    assert any("Methods/context:" in passage for row in extractions for passage in row.source_passages)


def test_extraction_abstention_reasoning_does_not_mark_rows_as_matched():
    workspace = Workspace(condition="acne", intervention="azelaic acid", source_types=[SourceType.pubmed])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.pubmed,
        external_id="no-stats",
        title="Azelaic acid acne context",
        abstract="Azelaic acid is discussed as a topical treatment option for acne without reporting numerical effectiveness outcomes.",
    )
    extractions = build_extractions([source], workspace)
    answer = AnswerService().answer(workspace, "What exact response rate statistics support azelaic acid?", [], extractions)
    evidence_map = " ".join(answer.evidence_map)
    reasoning = " ".join(answer.reasoning_summary)
    synthesis = " ".join(answer.evidence_synthesis)
    readouts = " ".join(answer.source_readouts)
    quality = " ".join(answer.evidence_quality)
    facets = " ".join(answer.facet_coverage)
    trace = " ".join(f"{item.label} {item.value} {item.detail}" for item in answer.answer_trace)
    assert "0 rows matched" in evidence_map
    assert "no extraction row met" in reasoning.lower()
    assert "no row was strong enough" in synthesis.lower()
    assert "CONTEXT" in readouts
    assert "Directness: low" in quality
    assert "Statistics:" in facets
    assert "0 rows cited" in trace


def test_fda_adverse_extraction_keeps_causality_caveat():
    workspace = Workspace(condition="migraine", intervention="sumatriptan", source_types=[SourceType.fda_adverse_event])
    source = EvidenceSource(
        workspace_id=workspace.id,
        source_type=SourceType.fda_adverse_event,
        external_id="FDA-AE-sumatriptan",
        title="openFDA adverse event report counts for sumatriptan",
        abstract="Top reported reactions in openFDA for sumatriptan: nausea (80 reports). These are spontaneous reports and cannot establish causality or incidence.",
    )
    extraction = build_extractions([source], workspace)[0]
    assert "cannot establish causality" in extraction.safety_note.lower()
