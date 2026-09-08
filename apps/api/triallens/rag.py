from __future__ import annotations

from collections import Counter
import re

from triallens.models import (
    Answer,
    AnswerTraceItem,
    EvidenceBrief,
    EvidenceChunk,
    EvidenceExtraction,
    EvidenceSource,
    RetrievedChunk,
    SourceType,
    Workspace,
)
from triallens.text import chunk_text, cosine, lexical_score, stable_embedding, tokenize

GENERIC_MEDICAL_TERMS = {
    "about",
    "adult",
    "adults",
    "adverse",
    "and",
    "are",
    "ask",
    "asked",
    "available",
    "benefit",
    "benefits",
    "but",
    "can",
    "care",
    "clinical",
    "concern",
    "concerns",
    "does",
    "disease",
    "dose",
    "drug",
    "effect",
    "effects",
    "evidence",
    "for",
    "from",
    "health",
    "how",
    "index",
    "indexed",
    "into",
    "label",
    "labels",
    "main",
    "medical",
    "more",
    "most",
    "not",
    "patient",
    "patients",
    "question",
    "record",
    "records",
    "risk",
    "risks",
    "safe",
    "safety",
    "say",
    "source",
    "sources",
    "study",
    "the",
    "this",
    "through",
    "to",
    "treatment",
    "trial",
    "trials",
    "use",
    "what",
    "when",
    "where",
    "which",
    "with",
}

SAFETY_TERMS = {
    "adverse",
    "contraindication",
    "contraindications",
    "harm",
    "ischemia",
    "limitation",
    "limitations",
    "myocardial",
    "reaction",
    "reactions",
    "risk",
    "risks",
    "safety",
    "stroke",
    "tolerability",
    "tolerated",
    "adherence",
    "persistence",
    "effects",
    "event",
    "events",
    "mild",
    "transient",
    "warning",
    "warnings",
}

BENEFIT_TERMS = {
    "benefit",
    "benefits",
    "efficacy",
    "effective",
    "effectiveness",
    "improve",
    "improved",
    "indicated",
    "indication",
    "outcome",
    "relief",
    "response",
    "treat",
    "treatment",
}

TRIAL_TERMS = {"trial", "trials", "phase", "recruiting", "completed", "eligibility", "protocol"}
LABEL_TERMS = {"fda", "label", "labeling", "indication", "contraindication", "warning", "dosage"}
COMPARISON_TERMS = {"against", "compare", "compared", "comparator", "comparison", "versus", "vs"}
MECHANISM_TERMS = {
    "absorption",
    "anti-inflammatory",
    "barrier",
    "delivery",
    "how",
    "mechanism",
    "permeability",
    "pharmacology",
    "receptor",
    "solubility",
    "transdermal",
    "work",
    "works",
}
STATISTIC_TERMS = {
    "absolute",
    "average",
    "back",
    "ci",
    "confidence",
    "count",
    "counts",
    "effectiveness",
    "mean",
    "median",
    "number",
    "numbers",
    "odds",
    "percent",
    "percentage",
    "pvalue",
    "rate",
    "rates",
    "ratio",
    "reduction",
    "relative",
    "result",
    "results",
    "score",
    "scores",
    "statistic",
    "statistics",
    "stats",
}
OUTCOME_TERMS = {
    "acne",
    "clearance",
    "comedones",
    "efficacy",
    "effective",
    "effectiveness",
    "improvement",
    "lesion",
    "lesions",
    "microcomedones",
    "outcome",
    "response",
    "success",
}

INTENT_TERMS = {
    "benefit": BENEFIT_TERMS | OUTCOME_TERMS,
    "comparison": COMPARISON_TERMS | BENEFIT_TERMS | OUTCOME_TERMS,
    "label": LABEL_TERMS | SAFETY_TERMS | BENEFIT_TERMS,
    "mechanism": MECHANISM_TERMS,
    "safety": SAFETY_TERMS | LABEL_TERMS,
    "statistics": STATISTIC_TERMS | OUTCOME_TERMS | BENEFIT_TERMS,
    "trial": TRIAL_TERMS | COMPARISON_TERMS | OUTCOME_TERMS,
}


def build_chunks(sources: list[EvidenceSource]) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    for source in sources:
        section_items = source_section_items(source) or [("summary", source.abstract)]
        citation = citation_for(source)
        chunk_idx = 1
        for section_label, section_text in section_items:
            source_chunks = chunk_text(section_text)
            for text in source_chunks:
                section = section_label if len(source_chunks) == 1 else f"{section_label} {chunk_idx}"
                chunks.append(
                    EvidenceChunk(
                        workspace_id=source.workspace_id,
                        source_id=source.id,
                        source_type=source.source_type,
                        text=text,
                        citation=citation,
                        section=section,
                        embedding=stable_embedding(text),
                    )
                )
                chunk_idx += 1
    return chunks


def build_extractions(sources: list[EvidenceSource], workspace: Workspace) -> list[EvidenceExtraction]:
    return [extract_source_evidence(source, workspace) for source in sources]


def extract_source_evidence(source: EvidenceSource, workspace: Workspace) -> EvidenceExtraction:
    text = normalize_passage(source.abstract)
    sentences = split_sentences(text) or [trim_sentence(text, 320)] if text else []
    source_sections = source_sections_for(source)
    topic_terms = meaningful_terms(topic_text(workspace))
    intervention_terms = meaningful_terms(workspace.intervention or "")
    source_terms = set(tokenize(f"{source.title} {text}"))

    outcome = extraction_sentence(sentences, OUTCOME_TERMS | BENEFIT_TERMS | STATISTIC_TERMS)
    safety = safety_extraction_sentence(split_safety_sentences(text))
    if source.source_type == SourceType.fda_adverse_event and "cannot establish causality" in text.lower():
        safety = "Reported reactions are spontaneous reports and cannot establish causality or incidence."
    comparator = comparator_context_for(source, text)
    population = population_context_for(source, workspace, sentences)
    intervention = intervention_context_for(source, workspace)
    overview = source_overview_for(source, workspace, sentences)
    methods = methods_context_for(source, sentences)
    key_findings = key_findings_for(source, sentences, outcome, safety)
    limitations = evidence_limitations_for(source, sentences, outcome, safety)
    source_understanding = source_understanding_for(
        source=source,
        workspace=workspace,
        overview=overview,
        methods=methods,
        population=population,
        intervention=intervention,
        comparator=comparator,
        outcome=outcome or outcome_fallback(source),
        safety=safety or safety_fallback(source),
        key_findings=key_findings,
        limitations=limitations,
    )
    quote = outcome or safety or population or (sentences[0] if sentences else source.abstract[:320])
    passages = source_passages_for(
        overview=overview,
        methods=methods,
        sections=source_sections,
        population=population,
        outcome=outcome or outcome_fallback(source),
        safety=safety or safety_fallback(source),
        key_findings=key_findings,
        limitations=limitations,
    )
    field_evidence = field_evidence_for(
        population=population,
        intervention=intervention,
        comparator=comparator,
        outcome=outcome or outcome_fallback(source),
        safety=safety or safety_fallback(source),
        passages=passages,
        sections=source_sections,
    )

    confidence = 0.42
    if topic_terms.intersection(source_terms):
        confidence += 0.18
    if intervention_terms and intervention_terms.intersection(source_terms):
        confidence += 0.16
    if outcome:
        confidence += 0.1
    if safety:
        confidence += 0.08
    if has_effectiveness_statistic(outcome or ""):
        confidence += 0.08
    review_status = "needs_review" if confidence < 0.58 else "unreviewed"

    return EvidenceExtraction(
        workspace_id=source.workspace_id,
        source_id=source.id,
        source_type=source.source_type,
        external_id=source.external_id,
        title=source.title,
        source_url=source.url,
        publication_date=source.publication_date,
        authors=[str(author) for author in source.metadata.get("authors", []) if str(author).strip()],
        citation=citation_for(source),
        population_context=population,
        intervention=intervention,
        comparator=comparator,
        outcome_result=outcome or outcome_fallback(source),
        safety_note=safety or safety_fallback(source),
        supporting_quote=quote,
        source_overview=overview,
        methods_context=methods,
        source_sections=source_sections,
        key_findings=key_findings,
        evidence_limitations=limitations,
        source_understanding=source_understanding,
        source_passages=passages,
        field_evidence=field_evidence,
        confidence=round(min(confidence, 0.95), 2),
        review_status=review_status,
        has_quantitative_result=has_effectiveness_statistic(outcome or ""),
        status=source.status,
        phase=source.phase,
    )


def source_section_items(source: EvidenceSource) -> list[tuple[str, str]]:
    raw_sections = source.metadata.get("sections") if source.metadata else None
    if isinstance(raw_sections, dict):
        return [
            (str(label), normalize_passage(str(text)))
            for label, text in raw_sections.items()
            if normalize_passage(str(text))
        ]
    return []


def source_sections_for(source: EvidenceSource) -> list[str]:
    sections = [f"{label}: {trim_sentence(text, 420)}" for label, text in source_section_items(source)]
    if sections:
        return sections[:8]
    inferred = infer_source_sections(source)
    return inferred[:8]


def infer_source_sections(source: EvidenceSource) -> list[str]:
    text = normalize_passage(source.abstract)
    sentences = split_sentences(text)
    if not sentences:
        return []
    sections = [("Overview", trim_sentence(sentences[0], 420))]
    method = extraction_sentence(sentences, {"method", "methods", "randomized", "cohort", "review", "participants", "subjects", "trial"})
    outcome = extraction_sentence(sentences, OUTCOME_TERMS | BENEFIT_TERMS | STATISTIC_TERMS)
    safety = safety_extraction_sentence(split_safety_sentences(text))
    if method:
        sections.append(("Methods/context", method))
    if outcome:
        sections.append(("Outcome/result", outcome))
    if safety:
        sections.append(("Safety", safety))
    return [f"{label}: {trim_sentence(value, 420)}" for label, value in sections if value]


def extraction_sentence(sentences: list[str], preferred_terms: set[str]) -> str:
    scored = [
        (
            len(set(tokenize(sentence)).intersection(preferred_terms)),
            quantitative_relevance(sentence),
            benefit_signal(sentence),
            sentence,
        )
        for sentence in sentences
        if sentence_quality(sentence) >= -1
    ]
    scored = [item for item in scored if item[0] > 0 or item[1] > 0]
    if not scored:
        return ""
    return trim_sentence(sorted(scored, reverse=True)[0][3], 320)


def safety_extraction_sentence(sentences: list[str]) -> str:
    candidates = []
    for index, sentence in enumerate(sentences):
        if not substantive_safety_claim(sentence):
            continue
        normalized = " ".join(sentence.lower().split())
        score = safety_claim_score(sentence)
        if starts_with_protocol_language(sentence):
            score -= 12
        if normalized.startswith(("to evaluate", "to assess", "to analyse", "to analyze")):
            score -= 12
        if "adverse events were" in normalized or "adverse reactions were" in normalized:
            score += 10
        candidates.append((score, -index, sentence))
    if not candidates:
        return ""
    return trim_sentence(sorted(candidates, reverse=True)[0][2], 320)


def source_overview_for(source: EvidenceSource, workspace: Workspace, sentences: list[str]) -> str:
    if not sentences:
        return f"{source_label_for(source.source_type, plural=False).capitalize()} record indexed for {topic_text(workspace)}."
    preferred = extraction_sentence(sentences, meaningful_terms(topic_text(workspace)) | BENEFIT_TERMS | TRIAL_TERMS | LABEL_TERMS)
    return preferred or trim_sentence(sentences[0], 320)


def source_passages_for(
    overview: str,
    methods: str,
    sections: list[str],
    population: str,
    outcome: str,
    safety: str,
    key_findings: list[str],
    limitations: list[str],
) -> list[str]:
    labeled = [
        ("Overview", overview),
        ("Methods/context", methods),
        ("Population", population),
        ("Outcome/result", outcome),
        ("Safety", safety),
    ]
    labeled.extend(("Source section", section) for section in sections)
    labeled.extend(("Finding", finding) for finding in key_findings)
    labeled.extend(("Limit", limitation) for limitation in limitations)
    passages = []
    seen: set[str] = set()
    for label, value in labeled:
        cleaned = trim_sentence(value, 360).strip()
        key = f"{label.lower()}:{cleaned.lower()}"
        if not cleaned or key in seen:
            continue
        passages.append(f"{label}: {cleaned}")
        seen.add(key)
        if len(passages) == 8:
            break
    return passages


def field_evidence_for(
    population: str,
    intervention: str,
    comparator: str,
    outcome: str,
    safety: str,
    passages: list[str],
    sections: list[str],
) -> dict[str, str]:
    candidates = sections + passages
    return {
        "Population / context": best_field_support(population, candidates, "Population context was inferred from the source profile when no exact sentence was available.", {"background", "population", "eligibility"}),
        "Intervention": best_field_support(intervention, candidates, "Intervention was inferred from the workspace query or source title when no exact sentence was available.", {"intervention", "treatment", "methods/context"}),
        "Comparator": best_field_support(comparator, candidates, "Comparator was not directly stated in the indexed source text.", {"comparator", "comparison", "methods/context"}),
        "Outcome / result": best_field_support(outcome, candidates, "Outcome/result was inferred from the strongest outcome-like passage or source fallback.", {"results", "outcomes"}),
        "Safety note": best_field_support(safety, candidates, "Safety note was inferred from available warning, label, adverse-event, or fallback context.", {"safety", "warnings", "adverse reactions"}),
    }


def best_field_support(value: str, candidates: list[str], fallback: str, preferred_labels: set[str] | None = None) -> str:
    clean_value = value.strip()
    if not clean_value:
        return fallback
    value_terms = meaningful_terms(clean_value)
    scored = []
    for index, candidate in enumerate(candidates):
        candidate_text = candidate.strip()
        if not candidate_text:
            continue
        overlap = term_overlap(value_terms, candidate_text)
        contains = 0.4 if clean_value.lower() in candidate_text.lower() or candidate_text.lower() in clean_value.lower() else 0.0
        label = candidate_text.split(":", 1)[0].strip().lower() if ":" in candidate_text else ""
        section_boost = 0.12 if label and label not in {"overview", "finding", "limit"} else 0.0
        label_boost = 1.0 if preferred_labels and label in preferred_labels else 0.0
        scored.append((overlap + contains + section_boost + label_boost, -index, candidate_text))
    if not scored:
        return fallback
    score, _, support = sorted(scored, reverse=True)[0]
    if score <= 0:
        return fallback
    return trim_sentence(support, 420)


def methods_context_for(source: EvidenceSource, sentences: list[str]) -> str:
    if source.source_type == SourceType.clinical_trials:
        details = ", ".join(item for item in [source.status, source.phase] if item)
        prefix = f"{details}. " if details else ""
        method_sentence = extraction_sentence(sentences, TRIAL_TERMS | {"randomized", "assigned", "placebo", "parallel", "primary", "subjects"})
        return prefix + (method_sentence or "ClinicalTrials.gov record; inspect the protocol for full eligibility, arms, and outcome definitions.")
    if source.source_type == SourceType.fda_label:
        return "FDA drug label record; label text may include indications, dosage, warnings, contraindications, and adverse reactions rather than trial efficacy estimates."
    if source.source_type == SourceType.fda_adverse_event:
        return "openFDA adverse-event summary; spontaneous reports are useful for signal navigation but are not a controlled study design."
    method_sentence = extraction_sentence(sentences, {"randomized", "cohort", "review", "trial", "study", "patients", "participants", "retrospective", "prospective"})
    return method_sentence or "PubMed abstract or record summary; inspect the publication for full methods and eligibility criteria."


def key_findings_for(source: EvidenceSource, sentences: list[str], outcome: str, safety: str) -> list[str]:
    candidates = []
    for item in [outcome, safety]:
        if item:
            candidates.append(item)
    candidates.extend(
        select_distinct_sentences(
            sentences,
            BENEFIT_TERMS | OUTCOME_TERMS | STATISTIC_TERMS | SAFETY_TERMS | LABEL_TERMS | COMPARISON_TERMS,
            limit=4,
        )
    )
    if source.source_type == SourceType.clinical_trials and not candidates:
        candidates.append("Trial record describes study design or planned outcomes; posted numerical results may not be available in the indexed summary.")
    if source.source_type == SourceType.fda_label and not candidates:
        candidates.append("FDA label record provides regulatory context; inspect the original label for exact indication, warning, and dosage language.")
    return unique_trimmed(candidates, limit=4, max_length=320)


def source_understanding_for(
    source: EvidenceSource,
    workspace: Workspace,
    overview: str,
    methods: str,
    population: str,
    intervention: str,
    comparator: str,
    outcome: str,
    safety: str,
    key_findings: list[str],
    limitations: list[str],
) -> list[str]:
    source_kind = source_label_for(source.source_type, plural=False).capitalize()
    topic = topic_text(workspace)
    notes = [
        f"Source profile: {source_kind} record about {topic}; TrialLens read the indexed summary and any available structured source sections.",
        f"Design/context understood: {methods}",
    ]
    notes.append(f"Population/use context: {population}")
    notes.append(f"Intervention context: {intervention}")
    if comparator and not comparator.lower().startswith(("not specified", "comparator not")):
        notes.append(f"Comparator context: {comparator}")
    elif source.source_type in {SourceType.clinical_trials, SourceType.pubmed}:
        notes.append("Comparator context: no clear comparator was available in the indexed text.")
    if outcome and not outcome.lower().startswith(("no direct outcome", "trial record may describe protocol")):
        notes.append(f"Outcome/result understood: {outcome}")
    else:
        notes.append("Outcome/result understood: no direct measured result was available in the indexed text.")
    if safety and not safety.lower().startswith("no safety-specific note"):
        notes.append(f"Safety context understood: {safety}")
    if key_findings:
        notes.append(f"Primary extracted signal: {key_findings[0]}")
    if limitations:
        notes.append(f"Use caveat: {limitations[0]}")
    return unique_trimmed(notes, limit=8, max_length=360)


def evidence_limitations_for(source: EvidenceSource, sentences: list[str], outcome: str, safety: str) -> list[str]:
    limitations = []
    if source.source_type == SourceType.clinical_trials:
        limitations.append("Trial registry records can describe protocols or planned outcomes even when peer-reviewed results are unavailable.")
    elif source.source_type == SourceType.fda_label:
        limitations.append("FDA label language is regulatory context and should not be read as a head-to-head effectiveness estimate.")
    elif source.source_type == SourceType.fda_adverse_event:
        limitations.append("Adverse-event reports are suspected reports and cannot establish causality, incidence, or comparative risk.")
    else:
        limitations.append("The indexed summary may omit full-text methods, subgroup findings, and detailed outcome tables.")
    if not outcome:
        limitations.append("No separate outcome/result sentence was confidently extracted from this source.")
    if not safety and source.source_type not in {SourceType.fda_adverse_event, SourceType.fda_label}:
        limitations.append("No safety-specific sentence was confidently extracted from this source.")
    if sentences and len(" ".join(sentences)) > 1200:
        limitations.append("Long record was compressed into source-level fields; inspect the original source for full context.")
    return unique_trimmed(limitations, limit=4, max_length=260)


def select_distinct_sentences(sentences: list[str], preferred_terms: set[str], limit: int) -> list[str]:
    scored = []
    for index, sentence in enumerate(sentences):
        if sentence_quality(sentence) < -1:
            continue
        terms = set(tokenize(sentence))
        score = len(terms.intersection(preferred_terms)) + quantitative_relevance(sentence) + benefit_signal(sentence)
        if score <= 0:
            continue
        scored.append((score, -index, sentence))
    return [trim_sentence(sentence, 320) for _, _, sentence in sorted(scored, reverse=True)[:limit]]


def unique_trimmed(items: list[str], limit: int, max_length: int) -> list[str]:
    seen: set[str] = set()
    unique = []
    for item in items:
        cleaned = trim_sentence(item, max_length).strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        unique.append(cleaned)
        seen.add(key)
        if len(unique) == limit:
            break
    return unique


def population_context_for(source: EvidenceSource, workspace: Workspace, sentences: list[str]) -> str:
    population_terms = {"patient", "patients", "participant", "participants", "adult", "adults", "children", "pediatric", "aged", "years", "subjects", "people"}
    candidates = [
        sentence
        for sentence in sentences
        if set(tokenize(sentence)).intersection(population_terms)
        and not set(tokenize(sentence)).intersection({"objective", "determine", "primary"})
    ]
    if candidates:
        return trim_sentence(candidates[0], 260)
    return population_fallback(source, workspace)


def intervention_context_for(source: EvidenceSource, workspace: Workspace) -> str:
    if workspace.intervention:
        return workspace.intervention
    if source.source_type == SourceType.fda_label:
        return source.title.replace("FDA label:", "").strip() or "Labeled drug product."
    return intervention_fallback(source, workspace)


def comparator_context_for(source: EvidenceSource, text: str) -> str:
    match = re.search(r"compared (?:with|to) ([^.]+?)(?: in | among | for | after | at |,|\\.)", text, flags=re.IGNORECASE)
    if match:
        return trim_sentence(match.group(1), 180)
    match = re.search(r"(placebo|vehicle|standard care|active comparator|comparator)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return comparator_fallback(source)


def population_fallback(source: EvidenceSource, workspace: Workspace) -> str:
    if source.source_type == SourceType.clinical_trials:
        return f"Trial population for {workspace.condition}; inspect the trial eligibility record for exact criteria."
    if source.source_type == SourceType.fda_adverse_event:
        return f"OpenFDA spontaneous reports involving {workspace.intervention or workspace.condition}; not a defined study population."
    if source.source_type == SourceType.fda_label:
        return f"FDA label population/use context for {workspace.intervention or workspace.condition}."
    return f"Study or review context related to {workspace.condition}; full eligibility details may require the full text."


def intervention_fallback(source: EvidenceSource, workspace: Workspace) -> str:
    if workspace.intervention:
        return workspace.intervention
    if source.source_type == SourceType.fda_adverse_event:
        return "Drug named in openFDA adverse-event query."
    return "Intervention not specified in indexed summary."


def comparator_fallback(source: EvidenceSource) -> str:
    if source.source_type == SourceType.clinical_trials:
        return "Comparator not separately extracted from the indexed trial summary."
    return "Not specified in indexed summary."


def outcome_fallback(source: EvidenceSource) -> str:
    if source.source_type == SourceType.clinical_trials:
        return "Trial record may describe protocol or planned outcomes; numerical results were not extracted."
    if source.source_type == SourceType.fda_label:
        return "FDA label context extracted; label passages may focus on indications, warnings, or adverse reactions rather than efficacy outcomes."
    if source.source_type == SourceType.fda_adverse_event:
        return "Adverse-event count summary; not an effectiveness result."
    return "No direct outcome/result extracted from the indexed abstract."


def safety_fallback(source: EvidenceSource) -> str:
    if source.source_type == SourceType.fda_adverse_event:
        return "Reported adverse events are suspected reports and do not prove causality or incidence."
    if source.source_type == SourceType.fda_label:
        return "Inspect FDA label warnings and adverse reaction sections before interpreting safety."
    return "No safety-specific note extracted from the indexed summary."


def citation_for(source: EvidenceSource) -> str:
    if source.source_type == SourceType.pubmed:
        return f"PubMed:{source.external_id}"
    if source.source_type == SourceType.clinical_trials:
        return f"ClinicalTrials.gov:{source.external_id}"
    if source.source_type == SourceType.fda_label:
        return f"openFDA label:{source.external_id}"
    return f"openFDA adverse events:{source.external_id}"


class Retriever:
    def retrieve(
        self,
        workspace: Workspace,
        question: str,
        chunks: list[EvidenceChunk],
        sources: list[EvidenceSource],
        source_types: list[SourceType] | None = None,
        limit: int = 8,
    ) -> list[RetrievedChunk]:
        query_embedding = stable_embedding(question)
        source_lookup = {source.id: source for source in sources}
        intent = question_intent(question)
        question_terms = meaningful_terms(question)
        topic_terms = meaningful_terms(f"{workspace.condition} {workspace.intervention or ''}")
        filtered = [chunk for chunk in chunks if source_types is None or chunk.source_type in source_types]
        scored = []
        for chunk in filtered:
            source = source_lookup.get(chunk.source_id)
            source_text = f"{source.title if source else ''} {chunk.text}"
            semantic = cosine(query_embedding, chunk.embedding)
            lexical = lexical_score(question, source_text)
            topic_overlap = term_overlap(topic_terms, source_text)
            question_overlap = term_overlap(question_terms, source_text)
            source_boost = source_type_boost(question, chunk.source_type)
            intent_alignment = intent_relevance(intent, source_text)
            off_topic_penalty = 0.16 if topic_terms and topic_overlap == 0 else 0.0
            score = (0.42 * semantic) + (0.28 * lexical) + (0.22 * topic_overlap) + (0.18 * question_overlap)
            score = score + source_boost + (0.16 * intent_alignment) - off_topic_penalty
            if intent == "safety" and substantive_safety_claim(chunk.text):
                safety_boost = min(0.18, safety_claim_score(chunk.text) * 0.015)
                if chunk.source_type == SourceType.pubmed:
                    safety_boost += 0.04
                score += safety_boost
            if intent == "statistics":
                score += quantitative_relevance(source_text) * 0.18
                if not has_quantitative_signal(source_text):
                    score -= 0.1
            matched_terms = sorted((topic_terms | question_terms).intersection(tokenize(source_text)))[:8]
            scored.append((score, chunk, matched_terms, source))
        ranked = sorted(scored, key=lambda item: item[0], reverse=True)[:limit]
        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                source_id=chunk.source_id,
                source_type=chunk.source_type,
                citation=chunk.citation,
                text=chunk.text,
                score=round(max(score, 0.0), 4),
                section=chunk.section,
                title=source.title if source else "",
                url=source.url if source else None,
                external_id=source.external_id if source else "",
                publication_date=source.publication_date if source else None,
                status=source.status if source else None,
                phase=source.phase if source else None,
                matched_terms=matched_terms,
                relevance_note=relevance_note(matched_terms, chunk.source_type),
            )
            for score, chunk, matched_terms, source in ranked
            if score > 0.12 and matched_terms
        ]


class AnswerService:
    DOCUMENT_CONTEXT_WORD_LIMIT = 1800

    def answer(
        self,
        workspace: Workspace,
        question: str,
        retrieved: list[RetrievedChunk],
        extractions: list[EvidenceExtraction] | None = None,
    ) -> Answer:
        extraction_answer = answer_from_extractions(workspace, question, extractions or [], retrieved)
        if extraction_answer:
            return extraction_answer

        if not retrieved or not strong_enough(retrieved):
            return abstention_answer(workspace.id, question, retrieved)

        intent = question_intent(question)
        citations = list(dict.fromkeys(chunk.citation for chunk in retrieved))
        evidence_chunks = select_evidence_chunks(retrieved, intent)
        safety_chunks = select_safety_chunks(retrieved)
        if intent == "statistics" and not evidence_chunks:
            return statistics_abstention_answer(workspace, question, retrieved, citations, safety_chunks)
        direct_answer = direct_answer_text(workspace, question, retrieved, bool(safety_chunks))
        supporting_evidence = synthesize_document_supporting_evidence(workspace, question, intent, evidence_chunks)
        if not direct_answer_supported(intent, evidence_chunks):
            direct_answer = partial_direct_answer(workspace, intent, retrieved)
            supporting_evidence.insert(0, directness_warning(intent))
        safety_limitations = synthesize_safety_limitations(intent, safety_chunks, retrieved)
        uncertainty = synthesize_uncertainty(intent, retrieved)
        limitations = [
            "This answer is generated only from retrieved workspace sources and may omit evidence not indexed here.",
            "It is not medical advice, diagnosis, or treatment guidance.",
        ]
        if any(chunk.source_type == SourceType.fda_adverse_event for chunk in retrieved):
            limitations.append("FDA adverse event reports are suspected reports and do not prove causality or incidence.")

        return Answer(
            workspace_id=workspace.id,
            question=question,
            short_answer=direct_answer,
            direct_answer=direct_answer,
            evidence=supporting_evidence,
            supporting_evidence=supporting_evidence,
            safety_limitations=safety_limitations or ["No safety-specific passage was retrieved strongly enough for this workspace/question."],
            uncertainty=uncertainty,
            limitations=limitations,
            citations=citations,
            retrieved_chunks=retrieved,
        )

    def answer_document(
        self,
        workspace: Workspace,
        source: EvidenceSource,
        question: str,
        chunks: list[EvidenceChunk],
        retrieved: list[RetrievedChunk],
        extractions: list[EvidenceExtraction] | None = None,
    ) -> Answer:
        intent = question_intent(question)
        citation = citation_for(source)
        source_chunks = chunks_for_document_context(workspace, source, chunks, retrieved)
        support_chunks = [
            chunk
            for chunk in source_chunks
            if document_chunk_supports_question(question, intent, chunk)
        ]
        extraction = (extractions or [None])[0]
        if not support_chunks and extraction:
            support_chunks = chunks_from_extraction(source, extraction, question, intent)
        if not support_chunks:
            return document_abstention_answer(workspace, source, question, retrieved)

        evidence_chunks = select_evidence_chunks(support_chunks, intent, limit=4)
        if intent == "statistics" and not any(has_effectiveness_statistic(chunk.text) for chunk in evidence_chunks):
            return document_abstention_answer(
                workspace,
                source,
                question,
                retrieved,
                reason="This document does not contain usable quantitative outcome statistics for that question.",
            )
        direct = document_direct_answer(workspace, source, question, evidence_chunks)
        supporting_evidence = synthesize_supporting_evidence(workspace, intent, evidence_chunks)
        safety_chunks = select_safety_chunks(source_chunks)
        limitations = [
            "This answer is limited to the selected document's stored content in TrialLens.",
            "If full text is not stored, TrialLens cannot answer from full article content.",
            "It is not medical advice, diagnosis, or treatment guidance.",
        ]
        if source.source_type == SourceType.fda_adverse_event:
            limitations.append("FAERS/openFDA adverse-event data are unverified spontaneous reports and cannot establish causality, incidence, or comparative risk.")
        trace = [
            AnswerTraceItem(
                label="Answer mode",
                value="Single document",
                detail=f"Scoped to {citation}; workspace sources outside this document were not used.",
            ),
            AnswerTraceItem(
                label="Document content",
                value=document_content_scope(source),
                detail=f"Used {len(source_chunks)} stored section chunk{'s' if len(source_chunks) != 1 else ''}.",
            ),
            AnswerTraceItem(
                label="Caution",
                value=source_type_caution(source.source_type),
                detail="If the selected document does not cover a point, TrialLens should not infer it from other documents.",
            ),
        ]
        evidence_map = [
            f"Document scope: answer used only {citation}.",
            f"Section coverage: {', '.join(sorted({chunk.section for chunk in source_chunks})[:8]) or 'stored summary'}.",
            f"Question fit: {len(evidence_chunks)} section chunk{'s' if len(evidence_chunks) != 1 else ''} supported the answer.",
        ]
        if source.source_type == SourceType.fda_adverse_event:
            evidence_map.append("FAERS handling: summarized as aggregate spontaneous-report counts, not causal evidence.")
        return Answer(
            workspace_id=workspace.id,
            question=question,
            short_answer=direct,
            direct_answer=direct,
            evidence_map=evidence_map,
            reasoning_summary=[
                "The question was answered in document mode, so TrialLens did not pull evidence from other workspace documents.",
                "The answer cites stored document sections and abstains from claims not covered by those sections.",
            ],
            evidence_synthesis=[],
            source_readouts=[
                f"CITED · {citation} · {source_label_for(source.source_type, plural=False)} · sections: {', '.join(sorted({chunk.section for chunk in evidence_chunks})[:5])}"
            ],
            evidence_quality=[
                f"Directness: {quality_level(len(evidence_chunks), 1, 3)}. {len(evidence_chunks)} selected-document chunks directly supported the answer.",
                f"Source scope: {document_content_scope(source)}.",
            ],
            facet_coverage=[f"{facet_label(intent)}: covered by the selected document."],
            answer_trace=trace,
            evidence=supporting_evidence,
            supporting_evidence=supporting_evidence,
            safety_limitations=synthesize_safety_limitations(intent, safety_chunks, source_chunks),
            uncertainty=document_uncertainty(source, intent),
            limitations=limitations,
            citations=[citation],
            retrieved_chunks=evidence_chunks,
        )


def chunks_for_document_context(
    workspace: Workspace,
    source: EvidenceSource,
    chunks: list[EvidenceChunk],
    retrieved: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    total_words = sum(len(chunk.text.split()) for chunk in chunks)
    if total_words > AnswerService.DOCUMENT_CONTEXT_WORD_LIMIT and retrieved:
        return retrieved
    question_terms = meaningful_terms(topic_text(workspace))
    return [
        retrieved_chunk_from_evidence_chunk(source, chunk, question_terms)
        for chunk in chunks
    ]


def retrieved_chunk_from_evidence_chunk(
    source: EvidenceSource,
    chunk: EvidenceChunk,
    matched_terms: set[str] | None = None,
) -> RetrievedChunk:
    terms = sorted((matched_terms or set()).intersection(tokenize(f"{source.title} {chunk.text}")))[:8]
    return RetrievedChunk(
        chunk_id=chunk.id,
        source_id=chunk.source_id,
        source_type=chunk.source_type,
        citation=chunk.citation,
        text=chunk.text,
        score=1.0,
        section=chunk.section,
        title=source.title,
        url=source.url,
        external_id=source.external_id,
        publication_date=source.publication_date,
        status=source.status,
        phase=source.phase,
        matched_terms=terms,
        relevance_note=f"Selected from {chunk.section} in this document.",
    )


def document_chunk_supports_question(question: str, intent: str, chunk: RetrievedChunk) -> bool:
    question_terms = meaningful_terms(question)
    text = f"{chunk.title} {chunk.text}"
    if term_overlap(question_terms, text) >= 0.18:
        return True
    if intent == "statistics":
        return has_effectiveness_statistic(text)
    return intent_relevance(intent, text) >= 0.18


def chunks_from_extraction(
    source: EvidenceSource,
    extraction: EvidenceExtraction,
    question: str,
    intent: str,
) -> list[RetrievedChunk]:
    question_terms = meaningful_terms(question)
    candidates = extraction.source_passages or list(extraction.field_evidence.values()) or extraction.source_understanding
    chunks = []
    for index, text in enumerate(candidates):
        if not text.strip():
            continue
        chunk = RetrievedChunk(
            chunk_id=f"{extraction.id}:field:{index}",
            source_id=source.id,
            source_type=source.source_type,
            citation=extraction.citation,
            text=text,
            score=0.72,
            section="extraction profile",
            title=source.title,
            url=source.url,
            external_id=source.external_id,
            publication_date=source.publication_date,
            status=source.status,
            phase=source.phase,
            matched_terms=sorted(question_terms.intersection(tokenize(text)))[:8],
            relevance_note="Selected from the stored extraction profile for this document.",
        )
        if document_chunk_supports_question(question, intent, chunk):
            chunks.append(chunk)
    return chunks


def document_abstention_answer(
    workspace: Workspace,
    source: EvidenceSource,
    question: str,
    retrieved: list[RetrievedChunk],
    reason: str | None = None,
) -> Answer:
    citation = citation_for(source)
    direct = reason or f"This selected document ({citation}) does not cover the question closely enough for TrialLens to answer without guessing."
    caveat = source_type_caution(source.source_type)
    if source.source_type == SourceType.fda_adverse_event:
        caveat = "FAERS/openFDA adverse-event rows are unverified spontaneous reports and cannot establish causality, incidence, or comparative risk."
    return Answer(
        workspace_id=workspace.id,
        question=question,
        short_answer=direct,
        direct_answer=direct,
        evidence=[],
        supporting_evidence=[],
        safety_limitations=[caveat],
        uncertainty=[
            f"Only {citation} was considered for this document-mode answer.",
            "Ask a workspace-level question if you want TrialLens to compare this source with other papers, trials, or labels.",
        ],
        limitations=[
            "TrialLens does not fill gaps from outside the selected document in document mode.",
            "It is not medical advice, diagnosis, or treatment guidance.",
        ],
        citations=[citation],
        retrieved_chunks=retrieved,
        evidence_map=[
            f"Document scope: answer was limited to {citation}.",
            "Question fit: no stored section in this document directly supported the requested answer.",
        ],
        reasoning_summary=[
            "Document mode requires support inside the selected source. TrialLens abstained because the stored content did not cover the requested point.",
        ],
        evidence_quality=[
            "Directness: low. No selected-document section directly supported the answer.",
            f"Source scope: {document_content_scope(source)}.",
        ],
        answer_trace=[
            AnswerTraceItem(label="Answer mode", value="Single document", detail=f"Scoped to {citation}."),
            AnswerTraceItem(label="Coverage", value="Not covered", detail=direct),
        ],
    )


def document_direct_answer(
    workspace: Workspace,
    source: EvidenceSource,
    question: str,
    chunks: list[RetrievedChunk],
) -> str:
    citation = citation_for(source)
    intent = question_intent(question)
    if source.source_type == SourceType.fda_adverse_event:
        return (
            f"In {citation}, TrialLens found aggregate spontaneous-report context relevant to the question. "
            "These reports are unverified and cannot establish causality, incidence, or comparative risk."
        )
    requested = {
        "statistics": "quantitative information",
        "safety": "safety information",
        "trial": "trial information",
        "label": "regulatory-label information",
        "comparison": "comparison context",
        "mechanism": "mechanism context",
    }.get(intent, "relevant evidence")
    sections = ", ".join(sorted({chunk.section for chunk in chunks})[:4])
    return f"In {citation}, TrialLens found {requested} in the selected document's stored content{f' ({sections})' if sections else ''}."


def synthesize_document_supporting_evidence(
    workspace: Workspace,
    question: str,
    intent: str,
    chunks: list[RetrievedChunk],
) -> list[str]:
    if not chunks:
        return []
    topic = topic_text(workspace)
    lead = f"Within the selected document, TrialLens found passages relevant to {topic} and the user's question."
    preferred_terms = terms_for_intent(intent) | meaningful_terms(question)
    evidence = [lead]
    for chunk in chunks[:4]:
        sentence = best_sentence(chunk, preferred_terms)
        if intent == "statistics" and has_effectiveness_statistic(sentence):
            evidence.append(statistical_claim(chunk))
        else:
            evidence.append(
                f"{source_context_phrase(chunk)} says {claim_clause(sentence)} {inline_citation(chunk)}. Section: {chunk.section}. {apa_reference(chunk)}"
            )
    return evidence


def document_content_scope(source: EvidenceSource) -> str:
    if source.source_type == SourceType.pubmed:
        return "PubMed abstract content stored in TrialLens, not necessarily the full article."
    if source.source_type == SourceType.clinical_trials:
        return "ClinicalTrials.gov stored summary/description content; posted structured results may be incomplete unless indexed."
    if source.source_type == SourceType.fda_label:
        return "Stored FDA label sections available in TrialLens."
    return "FAERS/openFDA aggregate count summary, not individual verified case narratives."


def source_type_caution(source_type: SourceType) -> str:
    if source_type == SourceType.pubmed:
        return "PubMed records may be abstract-only in this workspace."
    if source_type == SourceType.clinical_trials:
        return "ClinicalTrials.gov records can describe protocols or planned outcomes without posted results."
    if source_type == SourceType.fda_label:
        return "FDA labels are regulatory documents, not head-to-head effectiveness studies."
    return "FAERS/openFDA reports are unverified spontaneous reports and cannot establish causality."


def document_uncertainty(source: EvidenceSource, intent: str) -> list[str]:
    notes = [document_content_scope(source)]
    if source.source_type == SourceType.fda_adverse_event:
        notes.append("FAERS/openFDA counts can indicate reporting patterns, but they cannot prove the drug caused the event.")
    if intent == "statistics" and source.source_type in {SourceType.clinical_trials, SourceType.pubmed}:
        notes.append("Detailed numerical results may be missing when TrialLens only has an abstract or registry summary.")
    notes.append("Use workspace mode to compare this document against other source types.")
    return notes


class BriefService:
    def generate(self, workspace: Workspace, sources: list[EvidenceSource],
                 extractions: list[EvidenceExtraction] | None = None,
                 answers: list[Answer] | None = None) -> EvidenceBrief:
        rows = extractions or []
        saved = [answer for answer in (answers or []) if answer.saved_to_brief]
        counts = Counter(source.source_type.value for source in sources)
        review = Counter(row.review_status for row in rows)
        gaps = []
        next_steps = []
        pending = len(rows) - review.get("reviewed", 0)
        if pending:
            gaps.append(f"{pending} of {len(rows)} extraction rows have not been confirmed as reviewed.")
            next_steps.append("Check unreviewed extractions against their original sources.")
        if not any(row.has_quantitative_result for row in rows):
            gaps.append("No quantitative outcome has been identified in the extracted evidence.")
            next_steps.append("Find outcome results with a comparator, timeframe, and effect estimate.")
        if counts.get("clinical_trials"):
            gaps.append("Registry records may describe planned outcomes rather than completed results.")
        demo_count = sum("DEMO" in source.external_id.upper() for source in sources)
        if demo_count:
            gaps.append(f"{demo_count} sources are demonstration records, not research evidence.")
            next_steps.append("Replace demonstration records with retrieved public sources.")
        current_citations = {citation_for(source) for source in sources}
        if any(citation not in current_citations for answer in saved for citation in answer.citations):
            gaps.append("Some saved answers refer to an earlier source collection; check them before sharing.")
        if not saved:
            next_steps.append("Ask a research question, inspect its citations, then save useful answers to this brief.")
        gaps.append("Coverage is limited to stored records; full papers and unpublished evidence may be missing.")
        return EvidenceBrief(
            workspace_id=workspace.id,
            title=f"Research brief: {workspace.intervention or workspace.condition}",
            overview=f"Research handoff for {workspace.condition}"
                     f"{' / ' + workspace.intervention if workspace.intervention else ''}. "
                     f"{len(saved)} saved answers from a workspace with {len(sources)} indexed sources. "
                     "Saved answers are working notes, not an independently validated evidence review.",
            source_summary=dict(counts), review_summary=dict(review),
            key_claims=[answer.direct_answer or answer.short_answer for answer in saved],
            evidence_gaps=gaps, next_steps=next_steps, saved_answers=saved,
            safety_note="Evidence navigation only, not medical advice. Check cited sources before sharing conclusions.",
            citations=list(dict.fromkeys(c for answer in saved for c in answer.citations)),
        )


def meaningful_terms(text: str) -> set[str]:
    return {term for term in tokenize(text) if len(term) > 2 and term not in GENERIC_MEDICAL_TERMS}


def term_overlap(terms: set[str], text: str) -> float:
    if not terms:
        return 0.0
    found = terms.intersection(tokenize(text))
    return len(found) / len(terms)


def source_type_boost(question: str, source_type: SourceType) -> float:
    terms = set(tokenize(question))
    if terms.intersection(STATISTIC_TERMS):
        if source_type in {SourceType.pubmed, SourceType.clinical_trials}:
            return 0.1
    if terms.intersection(SAFETY_TERMS):
        if source_type in {SourceType.fda_label, SourceType.fda_adverse_event}:
            return 0.12
    if terms.intersection(TRIAL_TERMS) and source_type == SourceType.clinical_trials:
        return 0.14
    if terms.intersection(LABEL_TERMS) and source_type == SourceType.fda_label:
        return 0.14
    if terms.intersection(COMPARISON_TERMS) and source_type in {SourceType.pubmed, SourceType.clinical_trials}:
        return 0.1
    if terms.intersection(MECHANISM_TERMS) and source_type in {SourceType.pubmed, SourceType.fda_label}:
        return 0.08
    return 0.0


def relevance_note(matched_terms: list[str], source_type: SourceType) -> str:
    if not matched_terms:
        return "Low topical overlap; inspect carefully."
    source_label = source_label_for(source_type, plural=False)
    return f"Matched {', '.join(matched_terms[:5])} in a {source_label}."


def classify_chunk(chunk: RetrievedChunk) -> str:
    terms = set(tokenize(f"{chunk.title} {chunk.text}"))
    if chunk.source_type == SourceType.fda_adverse_event or terms.intersection(SAFETY_TERMS):
        return "safety"
    if chunk.source_type == SourceType.clinical_trials or terms.intersection(TRIAL_TERMS):
        return "trial"
    if chunk.source_type == SourceType.fda_label or terms.intersection(LABEL_TERMS):
        return "label"
    if terms.intersection(BENEFIT_TERMS):
        return "benefit"
    return "weak"


def strong_enough(retrieved: list[RetrievedChunk]) -> bool:
    if not retrieved:
        return False
    top = retrieved[0]
    if top.score < 0.18:
        return False
    return bool(top.matched_terms)


def answer_from_extractions(
    workspace: Workspace,
    question: str,
    extractions: list[EvidenceExtraction],
    retrieved: list[RetrievedChunk],
) -> Answer | None:
    if not extractions:
        return None
    intent = question_intent(question)
    ranked = rank_extractions(workspace, question, intent, extractions)
    direct_rows = [row for score, row in ranked if score >= extraction_threshold(intent, row)]
    if intent == "statistics":
        direct_rows = [row for row in direct_rows if row.has_quantitative_result]
    if not direct_rows:
        if strong_enough(retrieved):
            return None
        return extraction_abstention_answer(workspace, question, intent, [row for _, row in ranked[:4]], retrieved)

    if intent == "safety":
        directly_supporting_rows = select_safety_answer_rows(workspace, direct_rows, retrieved)
    else:
        directly_supporting_rows = [
            row for row in direct_rows if extraction_row_supports_direct_answer(workspace, intent, row)
        ]
    if not directly_supporting_rows:
        return extraction_abstention_answer(workspace, question, intent, [row for _, row in ranked[:4]], retrieved)

    selected = select_direct_answer_rows(intent, directly_supporting_rows)
    direct = extraction_direct_answer(workspace, question, intent, selected, retrieved)
    directly_cited = set(re.findall(r"\[([^\]]+)\]", direct))
    if directly_cited:
        selected = [row for row in selected if row.citation in directly_cited]
    citations = list(dict.fromkeys(row.citation for row in selected))
    evidence = extraction_evidence_bullets(intent, selected)
    evidence_map = extraction_evidence_map(intent, extractions, direct_rows, selected)
    reasoning_summary = extraction_reasoning_summary(workspace, question, intent, ranked, direct_rows, selected)
    evidence_synthesis = extraction_cross_source_synthesis(intent, extractions, direct_rows, selected)
    source_readouts = extraction_source_readouts(intent, ranked, direct_rows, selected)
    evidence_quality = extraction_evidence_quality(intent, extractions, direct_rows, selected)
    facet_coverage = extraction_facet_coverage(question, extractions, direct_rows)
    answer_trace = extraction_answer_trace(workspace, question, intent, ranked, direct_rows, selected, extractions)
    safety_rows = [row for _, row in ranked if extraction_has_safety(row)][:3]
    safety = extraction_safety_bullets(intent, safety_rows)
    uncertainty = extraction_uncertainty(intent, selected, retrieved)
    limitations = [
        "This answer is synthesized from structured extraction rows and retrieved workspace passages.",
        "It is not medical advice, diagnosis, or treatment guidance.",
    ]
    if any(row.source_type == SourceType.fda_adverse_event for row in selected + safety_rows):
        limitations.append("FDA adverse event reports are suspected reports and do not prove causality or incidence.")

    return Answer(
        workspace_id=workspace.id,
        question=question,
        short_answer=direct,
        direct_answer=direct,
        evidence_map=evidence_map,
        reasoning_summary=reasoning_summary,
        evidence_synthesis=evidence_synthesis,
        source_readouts=source_readouts,
        evidence_quality=evidence_quality,
        facet_coverage=facet_coverage,
        answer_trace=answer_trace,
        evidence=evidence,
        supporting_evidence=evidence,
        safety_limitations=safety,
        uncertainty=uncertainty,
        limitations=limitations,
        citations=citations,
        retrieved_chunks=retrieved,
    )


def rank_extractions(
    workspace: Workspace,
    question: str,
    intent: str,
    extractions: list[EvidenceExtraction],
) -> list[tuple[float, EvidenceExtraction]]:
    question_terms = meaningful_terms(question)
    topic_terms = meaningful_terms(topic_text(workspace))
    ranked = []
    for row in extractions:
        text = extraction_search_text(row)
        score = 0.2 * row.confidence
        score += 0.26 * term_overlap(topic_terms, text)
        score += 0.28 * term_overlap(question_terms, text)
        score += 0.2 * extraction_intent_score(intent, row)
        score += extraction_source_boost(intent, row.source_type)
        if row.review_status == "reviewed":
            score += 0.08
        if row.review_status == "needs_review":
            score -= 0.04
        ranked.append((round(score, 4), row))
    return sorted(ranked, key=lambda item: item[0], reverse=True)


def extraction_search_text(row: EvidenceExtraction) -> str:
    return " ".join(
        [
            row.title,
            row.source_overview,
            row.methods_context,
            " ".join(row.source_sections),
            row.population_context,
            row.intervention,
            row.comparator,
            row.outcome_result,
            row.safety_note,
            row.supporting_quote,
            " ".join(row.key_findings),
            " ".join(row.evidence_limitations),
            " ".join(row.source_understanding),
            " ".join(row.source_passages),
            " ".join(row.field_evidence.values()),
        ]
    )


def extraction_evidence_map(
    intent: str,
    rows: list[EvidenceExtraction],
    matched_rows: list[EvidenceExtraction],
    cited_rows: list[EvidenceExtraction],
) -> list[str]:
    source_counts = Counter(row.source_type for row in rows)
    source_mix = ", ".join(f"{count} {source_label_for(source_type, count != 1)}" for source_type, count in source_counts.items())
    map_items = [
        f"Workspace coverage: TrialLens considered {len(rows)} extracted source rows across {source_mix or 'the current source filter'}.",
        f"Question fit: {len(matched_rows)} rows matched the question strongly enough for direct synthesis; {len(cited_rows)} are cited in the answer.",
    ]
    quantitative_count = sum(row.has_quantitative_result for row in rows)
    if quantitative_count:
        map_items.append(f"Quantitative coverage: {quantitative_count} rows contain extracted numerical outcome signals.")
    elif intent == "statistics":
        map_items.append("Quantitative coverage: no extracted row contains a usable numerical effectiveness signal for this question.")
    safety_count = sum(extraction_has_safety(row) for row in rows)
    if safety_count:
        map_items.append(f"Safety coverage: {safety_count} rows include safety, warning, label, or adverse-event context.")
    low_confidence_count = sum(row.review_status == "needs_review" for row in rows)
    if low_confidence_count:
        map_items.append(f"Review coverage: {low_confidence_count} rows are marked low confidence and should be inspected before relying on them.")
    limitations = unique_trimmed([limit for row in rows for limit in row.evidence_limitations], limit=2, max_length=260)
    for limitation in limitations:
        map_items.append(f"Known limitation: {limitation}")
    return map_items


def extraction_reasoning_summary(
    workspace: Workspace,
    question: str,
    intent: str,
    ranked: list[tuple[float, EvidenceExtraction]],
    matched_rows: list[EvidenceExtraction],
    cited_rows: list[EvidenceExtraction],
) -> list[str]:
    topic = topic_text(workspace)
    question_terms = sorted(meaningful_terms(question))[:8]
    source_mix = extraction_source_mix(cited_rows) if cited_rows else "no cited rows"
    summary = [
        f"Question intent: treated as a {intent} question about {topic}.",
        f"Selection basis: rows were scored for topic overlap, question-term overlap, intent fit, source type, confidence, and review status.",
    ]
    if question_terms:
        summary.append(f"Question anchors: {', '.join(question_terms)}.")
    if cited_rows:
        strongest = cited_rows[0]
        best_score = next((score for score, row in ranked if row.id == strongest.id), 0)
        summary.append(
            f"Strongest row: {strongest.citation} scored {round(best_score * 100)} on the internal relevance scale and contributed {best_extraction_finding(strongest, terms_for_intent(intent)) or strongest.source_overview}."
        )
        summary.append(f"Synthesis scope: answer cites {len(cited_rows)} rows from {source_mix}; {len(matched_rows)} rows met the direct-answer threshold.")
    else:
        summary.append("Synthesis scope: no extraction row met the direct-answer threshold, so TrialLens abstained rather than filling gaps.")
    caution_reasons = []
    if any(row.review_status == "needs_review" for row in cited_rows):
        caution_reasons.append("one or more cited rows are marked low confidence")
    if any(row.source_type == SourceType.clinical_trials for row in cited_rows):
        caution_reasons.append("trial records may describe protocols or planned outcomes")
    if any(row.source_type == SourceType.fda_adverse_event for row in cited_rows):
        caution_reasons.append("adverse-event reports cannot establish causality or incidence")
    if intent == "statistics" and not all(row.has_quantitative_result for row in cited_rows):
        caution_reasons.append("not every cited row contains a quantitative outcome")
    if caution_reasons:
        summary.append(f"Caution applied: {', '.join(caution_reasons)}.")
    else:
        summary.append("Caution applied: answer still remains limited to indexed workspace sources and is not clinical guidance.")
    return summary


def extraction_answer_trace(
    workspace: Workspace,
    question: str,
    intent: str,
    ranked: list[tuple[float, EvidenceExtraction]],
    matched_rows: list[EvidenceExtraction],
    cited_rows: list[EvidenceExtraction],
    all_rows: list[EvidenceExtraction],
) -> list[AnswerTraceItem]:
    question_terms = sorted(meaningful_terms(question))[:8]
    top_context_rows = [row for _, row in ranked[:3]]
    excluded_count = max(len(all_rows) - len(matched_rows), 0)
    trace = [
        AnswerTraceItem(
            label="Question read",
            value=facet_label(intent),
            detail=f"TrialLens treated this as a {intent} question about {topic_text(workspace)}.",
        ),
        AnswerTraceItem(
            label="Question anchors",
            value=", ".join(question_terms) if question_terms else "General evidence question",
            detail="These terms were matched against source profiles, extracted fields, source passages, and limitations.",
        ),
        AnswerTraceItem(
            label="Workspace scan",
            value=f"{len(all_rows)} rows scanned",
            detail=f"{len(matched_rows)} rows met the synthesis threshold; {excluded_count} stayed as context or were not relevant enough.",
        ),
        AnswerTraceItem(
            label="Cited rows",
            value=f"{len(cited_rows)} rows cited",
            detail=f"Main source mix: {extraction_source_mix(cited_rows) or 'no cited rows'}.",
        ),
    ]
    if top_context_rows:
        trace.append(
            AnswerTraceItem(
                label="Closest context",
                value=top_context_rows[0].citation,
                detail=trim_sentence(best_extraction_finding(top_context_rows[0], terms_for_intent(intent)) or top_context_rows[0].source_overview, 260),
            )
        )
    caution = []
    if any(row.review_status == "needs_review" for row in cited_rows):
        caution.append("low-confidence cited row")
    if any(row.source_type == SourceType.clinical_trials for row in cited_rows):
        caution.append("trial registry records may be protocols")
    if any(row.source_type == SourceType.fda_adverse_event for row in cited_rows):
        caution.append("adverse-event rows are non-causal signals")
    if any("full-text" in " ".join(row.evidence_limitations).lower() for row in cited_rows):
        caution.append("indexed summaries can omit full-text detail")
    trace.append(
        AnswerTraceItem(
            label="Caution",
            value=", ".join(caution) if caution else "Indexed evidence only",
            detail="The answer does not use evidence outside the current workspace and is not clinical guidance.",
        )
    )
    return trace


def extraction_cross_source_synthesis(
    intent: str,
    rows: list[EvidenceExtraction],
    matched_rows: list[EvidenceExtraction],
    cited_rows: list[EvidenceExtraction],
) -> list[str]:
    focus_rows = cited_rows or matched_rows or rows[:4]
    source_counts = Counter(row.source_type for row in rows)
    focus_counts = Counter(row.source_type for row in focus_rows)
    source_scope = ", ".join(f"{count} {source_label_for(source_type, count != 1)}" for source_type, count in source_counts.items())
    focus_scope = ", ".join(f"{count} {source_label_for(source_type, count != 1)}" for source_type, count in focus_counts.items())
    synthesis = [
        f"Whole-workspace read: {len(rows)} extracted rows were available across {source_scope or 'the active source filter'}; this answer focused on {focus_scope or 'the closest available rows'}.",
    ]
    if matched_rows:
        shared_terms = common_signal_terms(matched_rows, intent)
        if shared_terms:
            synthesis.append(f"Shared signal: the directly matched rows repeatedly mention {', '.join(shared_terms)}.")
        else:
            synthesis.append("Shared signal: matched rows are relevant by source context and extracted fields, but they do not repeat a single narrow keyword pattern.")
    else:
        synthesis.append("Shared signal: no row was strong enough for direct synthesis, so TrialLens reports closest context rather than a firm answer.")
    by_type_notes = source_type_synthesis_notes(intent, rows)
    synthesis.extend(by_type_notes[:3])
    gap_notes = synthesis_gap_notes(intent, rows, matched_rows)
    synthesis.extend(gap_notes[:3])
    return synthesis


def extraction_source_readouts(
    intent: str,
    ranked: list[tuple[float, EvidenceExtraction]],
    matched_rows: list[EvidenceExtraction],
    cited_rows: list[EvidenceExtraction],
) -> list[str]:
    matched_ids = {row.id for row in matched_rows}
    cited_ids = {row.id for row in cited_rows}
    readouts = []
    for score, row in ranked:
        status = "cited" if row.id in cited_ids else "matched" if row.id in matched_ids else "context"
        best_finding = best_extraction_finding(row, terms_for_intent(intent)) or row.source_overview or row.supporting_quote
        limitation = row.evidence_limitations[0] if row.evidence_limitations else "No additional limitation extracted."
        readouts.append(
            f"{status.upper()} · {row.citation} · {source_label_for(row.source_type, plural=False)} · relevance {round(score * 100)}: {trim_sentence(best_finding, 220)} Limit: {trim_sentence(limitation, 160)}"
        )
    return readouts


def extraction_evidence_quality(
    intent: str,
    rows: list[EvidenceExtraction],
    matched_rows: list[EvidenceExtraction],
    cited_rows: list[EvidenceExtraction],
) -> list[str]:
    focus_rows = cited_rows or matched_rows
    quality = []
    if not focus_rows:
        quality.append("Directness: low. No extracted row met the direct-answer threshold for this question.")
    else:
        quality.append(f"Directness: {quality_level(len(focus_rows), 1, 4)}. {len(focus_rows)} rows directly supported the answer.")
    quantitative = sum(row.has_quantitative_result for row in focus_rows)
    if intent == "statistics":
        quality.append(
            f"Quantitative support: {quality_level(quantitative, 1, 3)}. {quantitative} directly used rows contain numerical outcome signals."
        )
    elif quantitative:
        quality.append(f"Quantitative support: present in {quantitative} directly used rows.")
    source_strength = source_strength_score(focus_rows)
    quality.append(f"Source strength: {quality_label(source_strength)}. {source_strength_reason(focus_rows)}")
    low_confidence = sum(row.review_status == "needs_review" for row in focus_rows)
    if low_confidence:
        quality.append(f"Review risk: elevated. {low_confidence} directly used rows are marked low confidence.")
    else:
        quality.append("Review risk: no directly used row is currently marked low confidence.")
    if any(row.source_type == SourceType.fda_adverse_event for row in focus_rows):
        quality.append("Causality caution: adverse-event rows are signal navigation only and cannot establish incidence or causality.")
    if any("full-text" in " ".join(row.evidence_limitations).lower() for row in rows):
        quality.append("Completeness caution: indexed summaries may omit full-text methods, subgroup analyses, and detailed outcome tables.")
    return quality


def extraction_facet_coverage(
    question: str,
    rows: list[EvidenceExtraction],
    matched_rows: list[EvidenceExtraction],
) -> list[str]:
    requested = requested_facets(question)
    if not requested:
        requested = ["benefit"]
    coverage = []
    for facet in requested:
        facet_rows = [row for row in rows if extraction_intent_score(facet, row) > 0 or facet_row_match(facet, row)]
        matched_facet_rows = [row for row in matched_rows if row in facet_rows]
        if matched_facet_rows:
            coverage.append(f"{facet_label(facet)}: covered by {len(matched_facet_rows)} directly matched rows; strongest source is {matched_facet_rows[0].citation}.")
        elif facet_rows:
            coverage.append(f"{facet_label(facet)}: partial context exists in {len(facet_rows)} rows, but none met the direct-answer threshold.")
        else:
            coverage.append(f"{facet_label(facet)}: not covered by the extracted workspace rows.")
    return coverage


def requested_facets(question: str) -> list[str]:
    terms = set(tokenize(question))
    facets = []
    ordered = [
        ("statistics", STATISTIC_TERMS),
        ("safety", SAFETY_TERMS),
        ("comparison", COMPARISON_TERMS),
        ("trial", TRIAL_TERMS),
        ("label", LABEL_TERMS),
        ("mechanism", MECHANISM_TERMS),
        ("benefit", BENEFIT_TERMS | OUTCOME_TERMS),
    ]
    for facet, facet_terms in ordered:
        if terms.intersection(facet_terms):
            facets.append(facet)
    return facets


def facet_row_match(facet: str, row: EvidenceExtraction) -> bool:
    if facet == "statistics":
        return row.has_quantitative_result
    if facet == "safety":
        return extraction_has_safety(row)
    if facet == "trial":
        return row.source_type == SourceType.clinical_trials
    if facet == "label":
        return row.source_type == SourceType.fda_label
    if facet == "comparison":
        return not row.comparator.lower().startswith(("not specified", "comparator not"))
    if facet == "benefit":
        return not row.outcome_result.lower().startswith("no direct outcome")
    return extraction_intent_score(facet, row) > 0


def facet_label(facet: str) -> str:
    return {
        "benefit": "Benefit/outcome",
        "comparison": "Comparator",
        "label": "FDA label context",
        "mechanism": "Mechanism/context",
        "safety": "Safety/limitations",
        "statistics": "Statistics",
        "trial": "Trial evidence",
    }.get(facet, facet.replace("_", " ").title())


def quality_level(value: int, moderate_threshold: int, high_threshold: int) -> str:
    if value >= high_threshold:
        return "high"
    if value >= moderate_threshold:
        return "moderate"
    return "low"


def source_strength_score(rows: list[EvidenceExtraction]) -> int:
    score = 0
    for row in rows:
        if row.source_type == SourceType.pubmed:
            score += 3
        elif row.source_type == SourceType.clinical_trials:
            score += 2
        elif row.source_type == SourceType.fda_label:
            score += 2
        elif row.source_type == SourceType.fda_adverse_event:
            score += 1
        if row.has_quantitative_result:
            score += 1
        if row.review_status == "needs_review":
            score -= 1
    return score


def quality_label(score: int) -> str:
    if score >= 8:
        return "high"
    if score >= 3:
        return "moderate"
    return "low"


def source_strength_reason(rows: list[EvidenceExtraction]) -> str:
    if not rows:
        return "No directly used rows were available for appraisal."
    counts = Counter(row.source_type for row in rows)
    parts = [f"{count} {source_label_for(source_type, count != 1)}" for source_type, count in counts.items()]
    return f"Directly used rows came from {', '.join(parts)}."


def common_signal_terms(rows: list[EvidenceExtraction], intent: str) -> list[str]:
    preferred = terms_for_intent(intent) | OUTCOME_TERMS | SAFETY_TERMS
    counts: Counter[str] = Counter()
    for row in rows:
        terms = set(tokenize(extraction_search_text(row))).intersection(preferred)
        counts.update(terms)
    threshold = 2 if len(rows) > 1 else 1
    return [term for term, count in counts.most_common(5) if count >= threshold and len(term) > 3]


def source_type_synthesis_notes(intent: str, rows: list[EvidenceExtraction]) -> list[str]:
    notes = []
    by_type: dict[SourceType, list[EvidenceExtraction]] = {}
    for row in rows:
        by_type.setdefault(row.source_type, []).append(row)
    if SourceType.pubmed in by_type:
        pubmed_rows = by_type[SourceType.pubmed]
        quantitative = sum(row.has_quantitative_result for row in pubmed_rows)
        quantitative_suffix = f", including {quantitative} with numerical outcome signals" if quantitative else ""
        notes.append(
            f"Literature view: {len(pubmed_rows)} PubMed rows provide abstract-level study or review context"
            f"{quantitative_suffix}."
        )
    if SourceType.clinical_trials in by_type:
        trial_rows = by_type[SourceType.clinical_trials]
        statuses = sorted({row.status for row in trial_rows if row.status})
        status_suffix = f" ({', '.join(statuses[:3])})" if statuses else ""
        notes.append(
            f"Trial-registry view: {len(trial_rows)} ClinicalTrials.gov rows describe protocol, status, phase, eligibility, or planned outcome context"
            f"{status_suffix}."
        )
    if SourceType.fda_label in by_type:
        notes.append(f"Regulatory view: {len(by_type[SourceType.fda_label])} FDA label rows add approved-use, warning, dosage, or adverse-reaction context.")
    if SourceType.fda_adverse_event in by_type:
        notes.append(f"Safety-signal view: {len(by_type[SourceType.fda_adverse_event])} openFDA adverse-event rows are signal navigation only, not causality or incidence evidence.")
    if intent == "statistics" and not any(row.has_quantitative_result for row in rows):
        notes.append("Statistics view: the active extracted rows do not contain direct numerical effectiveness results.")
    return notes


def synthesis_gap_notes(intent: str, rows: list[EvidenceExtraction], matched_rows: list[EvidenceExtraction]) -> list[str]:
    notes = []
    if not matched_rows:
        notes.append("Answer gap: extracted rows did not directly match the requested evidence type strongly enough.")
    if any(row.review_status == "needs_review" for row in rows):
        notes.append("Review gap: low-confidence rows remain in the workspace and may need human inspection before synthesis is trusted.")
    if intent == "statistics" and not all(row.has_quantitative_result for row in matched_rows):
        notes.append("Statistics gap: some relevant rows provide context rather than measured outcome statistics.")
    if any("full-text" in " ".join(row.evidence_limitations).lower() for row in rows):
        notes.append("Detail gap: indexed summaries can omit full-text methods, subgroup results, and detailed outcome tables.")
    return notes


def extraction_threshold(intent: str, row: EvidenceExtraction) -> float:
    if intent == "statistics":
        return 0.34 if row.has_quantitative_result else 2.0
    if intent in {"safety", "label", "trial"}:
        return 0.28
    return 0.24


def extraction_intent_score(intent: str, row: EvidenceExtraction) -> float:
    text = extraction_search_text(row)
    if intent == "statistics":
        return 1.0 if row.has_quantitative_result else 0.0
    if intent == "safety":
        return 1.0 if extraction_has_safety(row) else 0.0
    if intent == "trial":
        return 1.0 if row.source_type == SourceType.clinical_trials else term_overlap(TRIAL_TERMS, text)
    if intent == "label":
        return 1.0 if row.source_type == SourceType.fda_label else term_overlap(LABEL_TERMS, text)
    if intent == "comparison":
        return term_overlap(COMPARISON_TERMS | {"comparator", "versus"}, text)
    if intent == "mechanism":
        return term_overlap(MECHANISM_TERMS, text)
    return term_overlap(BENEFIT_TERMS | OUTCOME_TERMS, text)


def extraction_source_boost(intent: str, source_type: SourceType) -> float:
    if intent == "safety" and source_type in {SourceType.fda_label, SourceType.fda_adverse_event}:
        return 0.1
    if intent == "label" and source_type == SourceType.fda_label:
        return 0.12
    if intent == "trial" and source_type == SourceType.clinical_trials:
        return 0.12
    if intent in {"statistics", "benefit", "comparison"} and source_type in {SourceType.pubmed, SourceType.clinical_trials}:
        return 0.06
    return 0.0


def extraction_has_safety(row: EvidenceExtraction) -> bool:
    note = row.safety_note.lower()
    return (
        row.source_type in {SourceType.fda_label, SourceType.fda_adverse_event}
        or bool(set(tokenize(note)).intersection(SAFETY_TERMS | LABEL_TERMS))
    ) and not note.startswith("no safety-specific note")


def extraction_direct_answer(
    workspace: Workspace,
    question: str,
    intent: str,
    rows: list[EvidenceExtraction],
    retrieved: list[RetrievedChunk],
) -> str:
    if intent == "safety":
        return synthesize_safety_direct_answer(workspace, rows, retrieved)

    cited_claims = []
    seen_claims: set[str] = set()
    for row in rows:
        claim = trim_sentence(extraction_direct_claim(intent, row), 260).strip().rstrip(".")
        claim_key = " ".join(tokenize(claim))
        if not claim or claim_key in seen_claims:
            continue
        seen_claims.add(claim_key)
        cited_claims.append(f"{claim} [{row.citation}].")
        if len(cited_claims) == 3:
            break
    if not cited_claims:
        return f"The indexed workspace does not contain a source-specific answer to: {question.strip()}"

    boundary = extraction_answer_boundary(workspace, intent, rows)
    return " ".join([*cited_claims, boundary]).strip()


def extraction_direct_claim(intent: str, row: EvidenceExtraction) -> str:
    if intent == "statistics" and row.has_quantitative_result:
        return row.outcome_result
    if intent == "safety":
        return safety_row_claim(row)
    if intent == "trial":
        details = ", ".join(item for item in [row.status, row.phase] if item)
        return f"{details}: {row.outcome_result}" if details else row.outcome_result
    if intent == "label":
        return row.outcome_result or row.source_overview
    if intent == "comparison":
        return f"Compared with {row.comparator}, {row.outcome_result}"
    if intent == "mechanism":
        return best_extraction_finding(row, MECHANISM_TERMS | BENEFIT_TERMS) or row.source_overview
    claim = best_extraction_finding(row, BENEFIT_TERMS | OUTCOME_TERMS) or row.outcome_result
    return re.sub(
        r"\bare (?:a )?biguanide indicated as an adjunct to\b",
        "are indicated alongside",
        claim,
        flags=re.IGNORECASE,
    )


def select_safety_answer_rows(
    workspace: Workspace,
    rows: list[EvidenceExtraction],
    retrieved: list[RetrievedChunk],
    limit: int = 6,
) -> list[EvidenceExtraction]:
    row_by_citation = {row.citation: row for row in rows}
    selected: list[EvidenceExtraction] = []
    seen: set[str] = set()

    for _, citation in safety_chunk_claims(retrieved):
        row = row_by_citation.get(citation)
        if row and row.citation not in seen and safety_source_fits_workspace(workspace, row):
            selected.append(row)
            seen.add(row.citation)

    for row in rows:
        claim = safety_row_claim(row)
        if (
            row.citation not in seen
            and safety_source_fits_workspace(workspace, row)
            and substantive_safety_claim(claim)
        ):
            selected.append(row)
            seen.add(row.citation)
        if len(selected) == limit:
            break
    return selected[:limit]


def synthesize_safety_direct_answer(
    workspace: Workspace,
    rows: list[EvidenceExtraction],
    retrieved: list[RetrievedChunk],
) -> str:
    allowed_citations = {row.citation for row in rows}
    row_by_citation = {row.citation: row for row in rows}
    claims = [item for item in safety_chunk_claims(retrieved) if item[1] in allowed_citations]
    claims.extend(
        (safety_row_claim(row), row.citation)
        for row in rows
        if substantive_safety_claim(safety_row_claim(row))
    )

    chosen: list[tuple[str, str]] = []
    seen_claims: set[str] = set()
    for claim, citation in sorted(claims, key=lambda item: safety_claim_score(item[0]), reverse=True):
        cleaned = trim_sentence(clean_safety_claim(claim), 300).strip().rstrip(".")
        cleaned = contextualize_safety_claim(cleaned, row_by_citation.get(citation))
        key = " ".join(tokenize(cleaned))
        if not cleaned or key in seen_claims or near_duplicate_safety_claim(cleaned, citation, chosen):
            continue
        chosen.append((cleaned, citation))
        seen_claims.add(key)
        if len(chosen) == 3:
            break

    if not chosen:
        return f"The indexed workspace does not contain a source-specific safety answer for {workspace.intervention or workspace.condition}."

    source_count = len({citation for _, citation in chosen})
    source_word = "source" if source_count == 1 else "sources"
    subject = workspace.intervention or workspace.condition
    combined = " ".join(claim.lower() for claim, _ in chosen)
    if set(tokenize(combined)).intersection({"burning", "stinging", "pruritus", "dryness", "erythema", "irritation"}):
        lead = f"According to {source_count} directly relevant indexed {source_word}, the clearest safety concern for {subject} is local skin and application-site irritation."
    else:
        lead = f"According to {source_count} directly relevant indexed {source_word}, the evidence identifies the following safety concerns for {subject}."
    cited_claims = [f"{claim} [{citation}]." for claim, citation in chosen]
    boundary = "The indexed evidence is mainly labeling and limited study records, so it cannot establish how often rare reactions occur across all users."
    return " ".join([lead, *cited_claims, boundary])


def safety_chunk_claims(retrieved: list[RetrievedChunk]) -> list[tuple[str, str]]:
    claims: list[tuple[str, str]] = []
    for chunk in retrieved:
        if chunk.source_type == SourceType.clinical_trials and not re.search(
            r"\b(results?|adverse events?)\b", chunk.section, flags=re.IGNORECASE
        ):
            continue
        sentences = [
            sentence.strip(" -•\n\t")
            for sentence in re.split(r"(?<=[.!?])\s+", normalize_passage(chunk.text))
            if len(sentence.strip()) >= 24 and not table_like(sentence)
        ]
        candidates = [sentence for sentence in sentences if substantive_safety_claim(sentence)]
        if candidates:
            claims.append((max(candidates, key=safety_claim_score), chunk.citation))
    return claims


def safety_row_claim(row: EvidenceExtraction) -> str:
    if row.source_type == SourceType.fda_adverse_event and row.key_findings:
        return row.key_findings[0]
    return row.safety_note


def substantive_safety_claim(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    if not normalized or normalized.startswith(
        (
            "no safety-specific",
            "inspect fda label",
            "to report suspected",
            "to evaluate the efficacy",
            "this study is to evaluate",
            "comparison of efficacy",
            "the purpose of this study",
        )
    ):
        return False
    if any(term in normalized for term in ("contact ", "fda-1088", "medwatch", "www.fda.gov")):
        return False
    if "efficacy for treatment" in normalized or "has not been evaluated" in normalized:
        return False
    if normalized.endswith((" small depigmented", " severe", " mild", " moderate")):
        return False
    if "potential in maintenance therapy due to its good tolerability" in normalized:
        return False
    return bool(set(tokenize(normalized)).intersection(SAFETY_TERMS | {"burning", "stinging", "itching", "dryness", "erythema", "irritation", "hypersensitivity", "angioedema", "tolerability"}))


def safety_claim_score(text: str) -> int:
    normalized = text.lower()
    terms = set(tokenize(normalized))
    score = len(terms.intersection(SAFETY_TERMS)) * 2
    if "most common adverse reactions" in normalized:
        score += 12
    if terms.intersection({"burning", "stinging", "pruritus", "dryness", "erythema", "irritation"}):
        score += 8
    if terms.intersection({"hypersensitivity", "angioedema", "swelling", "urticaria", "asthma", "wheezing"}):
        score += 12
    if "%" in text:
        score += 4
    if "good tolerability" in normalized or "mild and transient" in normalized:
        score += 3
    if "avoid the eye" in normalized or "accidental exposure" in normalized:
        score += 2
    return score


def clean_safety_claim(text: str) -> str:
    cleaned = re.sub(r"^(?:\(?\s*\d+\s*\)?\s*)+(?:adverse reactions\s*)?", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.split(r"\(?\s*6\s*\)?\s*To report SUSPECTED ADVERSE REACTIONS", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = re.sub(r"\bUse Use:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" .")


def contextualize_safety_claim(claim: str, row: EvidenceExtraction | None) -> str:
    if not row or row.source_type != SourceType.pubmed or not claim.lower().startswith("adverse events"):
        return claim
    title = row.title.split(":", 1)[0].strip()
    title = re.sub(r"^efficacy and safety of\s+", "", title, flags=re.IGNORECASE)
    title = trim_sentence(title, 120)
    lowered_claim = claim[0].lower() + claim[1:] if claim else claim
    return f"In a study of {title}, {lowered_claim}"


def near_duplicate_safety_claim(
    claim: str,
    citation: str,
    chosen: list[tuple[str, str]],
) -> bool:
    terms = set(tokenize(claim)) - GENERIC_MEDICAL_TERMS
    if not terms:
        return False
    for existing, existing_citation in chosen:
        if existing_citation != citation:
            continue
        existing_terms = set(tokenize(existing)) - GENERIC_MEDICAL_TERMS
        smaller = min(len(terms), len(existing_terms))
        if smaller and len(terms.intersection(existing_terms)) / smaller >= 0.72:
            return True
    return False


def safety_source_fits_workspace(workspace: Workspace, row: EvidenceExtraction) -> bool:
    text = f"{row.title} {row.source_overview} {' '.join(row.source_sections)} {safety_row_claim(row)}".lower()
    if "unrelated" in text:
        return False
    if set(tokenize(text)).intersection({"cow", "cows", "dairy", "mouse", "mice", "rat", "rats", "veterinary"}):
        return False
    intervention_terms = meaningful_terms(workspace.intervention or "")
    return not intervention_terms or bool(intervention_terms.intersection(tokenize(text)))


def extraction_row_supports_direct_answer(
    workspace: Workspace,
    intent: str,
    row: EvidenceExtraction,
) -> bool:
    claim = extraction_direct_claim(intent, row).strip()
    if not claim:
        return False
    claim_text = f"{row.title} {claim}".lower()
    intervention_terms = meaningful_terms(workspace.intervention or "")
    names_intervention = not intervention_terms or bool(intervention_terms.intersection(tokenize(claim_text)))
    protocol_only = starts_with_protocol_language(claim)
    has_effect_estimate = has_effectiveness_statistic(claim)

    if intent == "statistics":
        return has_effect_estimate and names_intervention and not protocol_only
    if intent == "safety":
        return extraction_has_safety(row) and names_intervention
    if intent == "trial":
        return row.source_type == SourceType.clinical_trials and names_intervention
    if intent == "label":
        return row.source_type == SourceType.fda_label and names_intervention
    if intent == "comparison":
        return names_intervention and not protocol_only and not row.comparator.lower().startswith(("not specified", "comparator not"))
    if intent == "mechanism":
        return names_intervention and not protocol_only
    if row.source_type == SourceType.fda_adverse_event:
        return False
    if row.source_type == SourceType.clinical_trials and not has_effect_estimate:
        return False
    return names_intervention and not protocol_only and benefit_signal(claim) > 0


def select_direct_answer_rows(
    intent: str,
    rows: list[EvidenceExtraction],
    limit: int = 6,
) -> list[EvidenceExtraction]:
    ordered = sorted(rows, key=lambda row: direct_answer_source_priority(intent, row))
    selected: list[EvidenceExtraction] = []
    label_added = False
    seen_claims: set[str] = set()
    for row in ordered:
        claim_key = " ".join(tokenize(extraction_direct_claim(intent, row)))
        if not claim_key or claim_key in seen_claims:
            continue
        if intent not in {"label", "safety"} and row.source_type == SourceType.fda_label:
            if label_added:
                continue
            label_added = True
        seen_claims.add(claim_key)
        selected.append(row)
        if len(selected) == limit:
            break
    return selected


def direct_answer_source_priority(intent: str, row: EvidenceExtraction) -> int:
    priorities = {
        "benefit": {
            SourceType.fda_label: 0,
            SourceType.pubmed: 1,
            SourceType.clinical_trials: 2,
            SourceType.fda_adverse_event: 3,
        },
        "statistics": {
            SourceType.pubmed: 0,
            SourceType.clinical_trials: 1,
            SourceType.fda_label: 2,
            SourceType.fda_adverse_event: 3,
        },
        "safety": {
            SourceType.fda_label: 0,
            SourceType.pubmed: 1,
            SourceType.fda_adverse_event: 2,
            SourceType.clinical_trials: 3,
        },
    }
    return priorities.get(intent, {}).get(row.source_type, 1)


def starts_with_protocol_language(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return normalized.startswith(
        (
            "this study will",
            "this study aimed",
            "this trial will",
            "this is a randomized",
            "this is a randomised",
            "to assess",
            "to evaluate",
            "to analyse",
            "to analyze",
            "eligible subjects",
            "trial record may",
            "the aim of this trial",
        )
    )


def extraction_answer_boundary(
    workspace: Workspace,
    intent: str,
    rows: list[EvidenceExtraction],
) -> str:
    topic = f"{workspace.intervention} for {workspace.condition}" if workspace.intervention else workspace.condition
    if intent in {"benefit", "statistics", "comparison"} and not any(
        has_effectiveness_statistic(extraction_direct_claim(intent, row)) for row in rows
    ):
        return f"These indexed sources do not provide a reliable magnitude-of-effect estimate for {topic}, so TrialLens cannot quantify the benefit from this workspace."
    if any(row.source_type == SourceType.fda_adverse_event for row in rows):
        return "Spontaneous adverse-event reports can identify signals, but they cannot establish causality or incidence."
    if any(row.source_type == SourceType.clinical_trials for row in rows) and not any(row.has_quantitative_result for row in rows):
        return "The cited trial records describe study context or planned outcomes rather than proven results."
    return "This answer is limited to the directly supporting evidence currently indexed in the workspace."


def extraction_evidence_bullets(intent: str, rows: list[EvidenceExtraction]) -> list[str]:
    bullets = []
    for row in rows:
        if intent == "statistics" and row.has_quantitative_result:
            claim = row.outcome_result
        elif intent == "safety":
            claim = row.safety_note
        elif intent == "trial":
            details = ", ".join(item for item in [row.status, row.phase] if item)
            prefix = f"{details}: " if details else ""
            claim = f"{prefix}{row.outcome_result}"
        elif intent == "comparison":
            claim = f"Comparator: {row.comparator}. Result/context: {row.outcome_result}"
        elif intent == "mechanism":
            claim = best_extraction_finding(row, MECHANISM_TERMS | BENEFIT_TERMS) or row.source_overview
        else:
            claim = best_extraction_finding(row, BENEFIT_TERMS | OUTCOME_TERMS) or row.outcome_result
        context = extraction_row_context(row)
        context_suffix = f" {context}" if context else ""
        bullets.append(
            trim_sentence(
                f"{extraction_source_phrase(row)}: {claim} {extraction_inline_citation(row)}.{context_suffix}",
                460,
            )
        )
    return bullets


def best_extraction_finding(row: EvidenceExtraction, preferred_terms: set[str]) -> str:
    candidates = row.key_findings or [row.outcome_result, row.safety_note, row.supporting_quote, row.source_overview]
    scored = []
    for index, candidate in enumerate(candidates):
        text = candidate.strip()
        if not text:
            continue
        score = len(set(tokenize(text)).intersection(preferred_terms)) + quantitative_relevance(text)
        scored.append((score, -index, text))
    if not scored:
        return ""
    return sorted(scored, reverse=True)[0][2]


def extraction_row_context(row: EvidenceExtraction) -> str:
    parts = []
    if row.methods_context and not row.methods_context.startswith("Study design or source methods"):
        parts.append(f"Design/context: {trim_sentence(row.methods_context, 140)}")
    if row.evidence_limitations:
        parts.append(f"Limits: {trim_sentence(row.evidence_limitations[0], 120)}")
    return " ".join(parts)


def extraction_safety_bullets(intent: str, rows: list[EvidenceExtraction]) -> list[str]:
    if rows:
        lead = []
        if intent not in {"safety", "label"}:
            lead.append("Safety was not the main focus of the question, but TrialLens found safety-relevant extraction rows.")
        lead.extend(
            f"{extraction_source_phrase(row)}: {row.safety_note} {extraction_inline_citation(row)}."
            for row in rows
        )
        return lead
    return ["No safety-specific extraction row was strong enough for this workspace/question."]


def extraction_uncertainty(
    intent: str,
    rows: list[EvidenceExtraction],
    retrieved: list[RetrievedChunk],
) -> list[str]:
    notes = [
        "Extraction rows are generated from indexed abstracts, trial summaries, labels, and adverse-event summaries; full-text details may be missing.",
    ]
    if any(row.review_status == "needs_review" for row in rows):
        notes.append("At least one supporting row is marked needs review because topical or intent confidence is limited.")
    if any(row.source_type == SourceType.clinical_trials for row in rows):
        notes.append("ClinicalTrials.gov records may describe protocols or planned outcomes even when peer-reviewed results are unavailable.")
    if any(row.source_type == SourceType.fda_adverse_event for row in rows):
        notes.append("FDA adverse-event rows summarize suspected reports and should not be interpreted as incidence or causality.")
    if intent == "statistics" and not all(row.has_quantitative_result for row in rows):
        notes.append("Some rows may contain context rather than measured outcome statistics; inspect the supporting quote.")
    if retrieved:
        notes.append("Retrieved passages remain available for audit, but the answer prioritizes the structured extraction table.")
    return notes


def extraction_abstention_answer(
    workspace: Workspace,
    question: str,
    intent: str,
    closest: list[EvidenceExtraction],
    retrieved: list[RetrievedChunk],
) -> Answer:
    topic = topic_text(workspace)
    requested = {
        "statistics": "quantitative effectiveness statistics",
        "safety": "direct safety evidence",
        "trial": "direct trial evidence",
        "label": "direct FDA-label evidence",
        "comparison": "direct comparison evidence",
        "mechanism": "direct mechanism evidence",
    }.get(intent, "direct evidence")
    direct = f"For {topic}, the extraction table does not contain enough {requested} to answer this question directly."
    evidence = [
        "TrialLens is abstaining because the structured extraction rows do not directly support the requested answer.",
    ]
    if closest:
        evidence.append(
            "Closest available row: "
            f"{closest[0].title} ({closest[0].citation}) has confidence {round(closest[0].confidence * 100)}%."
        )
    return Answer(
        workspace_id=workspace.id,
        question=question,
        short_answer=direct,
        direct_answer=direct,
        evidence_map=extraction_evidence_map(intent, closest, [], []),
        reasoning_summary=extraction_reasoning_summary(workspace, question, intent, [(0, row) for row in closest], [], []),
        evidence_synthesis=extraction_cross_source_synthesis(intent, closest, [], []),
        source_readouts=extraction_source_readouts(intent, [(0, row) for row in closest], [], []),
        evidence_quality=extraction_evidence_quality(intent, closest, [], []),
        facet_coverage=extraction_facet_coverage(question, closest, []),
        answer_trace=extraction_answer_trace(workspace, question, intent, [(0, row) for row in closest], [], [], closest),
        evidence=evidence,
        supporting_evidence=evidence,
        safety_limitations=[],
        uncertainty=[
            "Try changing the source filter, rebuilding with a more specific intervention, or inspecting sources manually.",
            "TrialLens avoids filling gaps when extracted fields and retrieved passages do not support the question.",
        ],
        limitations=["TrialLens does not provide medical advice or patient-specific recommendations."],
        citations=[row.citation for row in closest[:3]],
        retrieved_chunks=retrieved,
    )


def extraction_source_mix(rows: list[EvidenceExtraction]) -> str:
    counts = Counter(row.source_type for row in rows)
    return ", ".join(f"{count} {source_label_for(source_type, count != 1)}" for source_type, count in counts.items())


def extraction_source_phrase(row: EvidenceExtraction) -> str:
    if row.source_type == SourceType.pubmed:
        return f"PubMed record “{row.title}”"
    if row.source_type == SourceType.clinical_trials:
        return f"ClinicalTrials.gov record “{row.title}”"
    if row.source_type == SourceType.fda_label:
        return f"FDA label record “{row.title}”"
    return f"openFDA adverse-event row “{row.title}”"


def extraction_inline_citation(row: EvidenceExtraction) -> str:
    if row.source_type == SourceType.pubmed:
        return f"(PubMed, {row.external_id})"
    if row.source_type == SourceType.clinical_trials:
        return f"(ClinicalTrials.gov, {row.external_id})"
    if row.source_type == SourceType.fda_label:
        return f"(openFDA, {row.external_id})"
    return f"(openFDA adverse-event reports, {row.external_id})"


def extraction_reference(row: EvidenceExtraction) -> str:
    if row.source_type == SourceType.pubmed:
        return f"Reference: {row.title}. PubMed. {row.external_id}."
    if row.source_type == SourceType.clinical_trials:
        return f"Reference: ClinicalTrials.gov. {row.title}. {row.external_id}."
    if row.source_type == SourceType.fda_label:
        return f"Reference: openFDA. {row.title}. Drug label record {row.external_id}."
    return f"Reference: openFDA. {row.title}. Adverse-event summary {row.external_id}."


def abstention_answer(workspace_id: str, question: str, retrieved: list[RetrievedChunk]) -> Answer:
    return Answer(
        workspace_id=workspace_id,
        question=question,
        short_answer="I do not have enough directly relevant retrieved evidence to answer this from the current workspace.",
        direct_answer="I do not have enough directly relevant retrieved evidence to answer this from the current workspace.",
        evidence=[],
        supporting_evidence=[],
        safety_limitations=[],
        uncertainty=[
            "Try asking about the indexed condition/intervention, choosing a narrower source filter, or rebuilding the workspace with a clearer intervention.",
            "TrialLens avoids filling gaps when retrieved passages do not support the question.",
        ],
        limitations=[
            "TrialLens does not provide medical advice or patient-specific recommendations.",
        ],
        citations=[],
        retrieved_chunks=retrieved,
    )


def statistics_abstention_answer(
    workspace: Workspace,
    question: str,
    retrieved: list[RetrievedChunk],
    citations: list[str],
    safety_chunks: list[RetrievedChunk],
) -> Answer:
    topic = topic_text(workspace)
    direct = (
        f"I did not find quantitative effectiveness statistics for {topic} in the retrieved passages. "
        "The indexed sources mention relevance, study design, or safety context, but they do not provide usable numerical outcome results for this question."
    )
    return Answer(
        workspace_id=workspace.id,
        question=question,
        short_answer=direct,
        direct_answer=direct,
        evidence=[
            "No retrieved passage contained a usable effectiveness statistic such as a percentage improvement, lesion-count change, response rate, p-value, confidence interval, or comparator result.",
            "Try filtering to Literature or Trials, or rebuild the workspace with more result-focused sources if you need numerical efficacy estimates.",
        ],
        supporting_evidence=[],
        safety_limitations=synthesize_safety_limitations("statistics", safety_chunks, retrieved),
        uncertainty=[
            "ClinicalTrials.gov records often describe planned outcomes without posting numerical results.",
            "PubMed abstracts may omit detailed statistics that appear only in full text.",
        ],
        limitations=[
            "TrialLens does not invent statistics when indexed sources do not contain them.",
            "It is not medical advice, diagnosis, or treatment guidance.",
        ],
        citations=citations,
        retrieved_chunks=retrieved,
    )


def question_intent(question: str) -> str:
    terms = set(tokenize(question))
    if terms.intersection(STATISTIC_TERMS):
        return "statistics"
    if terms.intersection(COMPARISON_TERMS):
        return "comparison"
    if terms.intersection(MECHANISM_TERMS):
        return "mechanism"
    if terms.intersection(SAFETY_TERMS):
        return "safety"
    if terms.intersection(TRIAL_TERMS):
        return "trial"
    if terms.intersection(LABEL_TERMS):
        return "label"
    return "benefit"


def select_evidence_chunks(retrieved: list[RetrievedChunk], intent: str, limit: int = 4) -> list[RetrievedChunk]:
    if intent == "statistics":
        numeric_chunks = sorted(
            [chunk for chunk in retrieved if has_effectiveness_statistic(chunk.text)],
            key=lambda chunk: effectiveness_statistic_relevance(chunk.text),
            reverse=True,
        )
        return unique_source_chunks(numeric_chunks, limit)
    intent_chunks = sorted(
        [chunk for chunk in retrieved if intent_relevance(intent, f"{chunk.title} {chunk.text}") > 0],
        key=lambda chunk: intent_relevance(intent, f"{chunk.title} {chunk.text}"),
        reverse=True,
    )
    if intent in {"comparison", "mechanism"}:
        return unique_source_chunks(intent_chunks, limit)
    priority = {
        "safety": {"safety"},
        "trial": {"trial"},
        "label": {"label", "safety"},
        "benefit": {"benefit", "trial", "label"},
    }[intent]
    selected = unique_source_chunks(intent_chunks or [chunk for chunk in retrieved if classify_chunk(chunk) in priority], limit)
    if selected:
        return selected
    return unique_source_chunks(retrieved, limit)


def select_safety_chunks(retrieved: list[RetrievedChunk], limit: int = 3) -> list[RetrievedChunk]:
    safety_chunks = [chunk for chunk in retrieved if classify_chunk(chunk) == "safety"]
    ranked = sorted(safety_chunks, key=safety_chunk_quality, reverse=True)
    return unique_source_chunks([chunk for chunk in ranked if safety_chunk_quality(chunk) > 0], limit)


def unique_source_chunks(chunks: list[RetrievedChunk], limit: int) -> list[RetrievedChunk]:
    selected: list[RetrievedChunk] = []
    seen_sources: set[str] = set()
    for chunk in chunks:
        if chunk.source_id in seen_sources:
            continue
        selected.append(chunk)
        seen_sources.add(chunk.source_id)
        if len(selected) == limit:
            break
    if len(selected) < limit:
        for chunk in chunks:
            if chunk.chunk_id in {item.chunk_id for item in selected}:
                continue
            selected.append(chunk)
            if len(selected) == limit:
                break
    return selected


def synthesize_supporting_evidence(workspace: Workspace, intent: str, chunks: list[RetrievedChunk]) -> list[str]:
    if not chunks:
        return ["No directly supportive passage was retrieved strongly enough to summarize."]
    topic = topic_text(workspace)
    lead = {
        "benefit": f"The indexed evidence suggests potential benefit or therapeutic relevance for {topic}, but the strength of that evidence depends on source type and study design.",
        "comparison": f"The indexed evidence contains comparison-oriented context for {topic}. The strongest passages below mention comparator arms, alternative treatments, or versus-style study designs.",
        "mechanism": f"The indexed evidence contains mechanism or delivery context for {topic}. The passages below explain how the intervention is described as working or being delivered.",
        "safety": f"The indexed evidence points to safety considerations for {topic}; these should be read as evidence-navigation findings, not patient-specific guidance.",
        "trial": f"The indexed trial records describe how {topic} is being or has been studied, including comparator and eligibility context where available.",
        "label": f"The indexed regulatory-label passages describe approved-use, warning, or limitation context for {topic}.",
        "statistics": f"The indexed passages below contain quantitative signals relevant to {topic}. Interpret them by source type: trial protocols may describe planned measures, while labels may report safety rates rather than effectiveness.",
    }[intent]
    summaries = [lead]
    for chunk in chunks[:4]:
        summaries.append(statistical_claim(chunk) if intent == "statistics" else synthesized_claim(chunk, intent))
    return summaries


def synthesize_safety_limitations(intent: str, safety_chunks: list[RetrievedChunk], retrieved: list[RetrievedChunk]) -> list[str]:
    clean_chunks = [chunk for chunk in safety_chunks if has_usable_sentence(chunk, SAFETY_TERMS | LABEL_TERMS)]
    if clean_chunks:
        notes = []
        if intent == "benefit":
            notes.append(
                "Safety was not the main focus of this benefits question, but the retrieved evidence includes relevant tolerability or adverse-event context."
            )
        for chunk in clean_chunks[:3]:
            sentence = best_sentence(chunk, SAFETY_TERMS | LABEL_TERMS)
            notes.append(
                f"{source_context_phrase(chunk)} reports or describes {claim_clause(sentence)} {inline_citation(chunk)}. {apa_reference(chunk)}"
            )
        return notes
    if intent == "benefit":
        return [
            "The retrieved passages for this question focus more on possible benefit, use, or trial context than on safety. Check FDA labels or ask a safety-specific question for a more targeted safety review."
        ]
    return ["No safety-specific passage was retrieved strongly enough for this workspace/question."]


def synthesize_uncertainty(intent: str, retrieved: list[RetrievedChunk]) -> list[str]:
    source_counts = Counter(chunk.source_type for chunk in retrieved)
    notes = [
        "The answer is limited to the abstracts, trial summaries, labels, and adverse-event summaries indexed in this workspace; full-text results and unpublished evidence may be missing.",
    ]
    if source_counts.get(SourceType.clinical_trials, 0):
        notes.append("ClinicalTrials.gov records may describe protocols, eligibility, or planned outcomes even when peer-reviewed results are unavailable.")
    if source_counts.get(SourceType.fda_adverse_event, 0):
        notes.append("FDA adverse-event reports are reports of suspected events and should not be interpreted as proof that the drug caused the event.")
    if intent == "statistics":
        notes.append("Some retrieved numbers may describe eligibility, dose, formulation, or adverse-event frequency rather than effectiveness; TrialLens separates those from true outcome statistics when possible.")
    elif intent == "comparison":
        notes.append("Comparison claims are limited unless the cited source reports comparator outcomes, not just a comparator study design.")
    elif intent == "mechanism":
        notes.append("Mechanism explanations may be based on abstracts, labels, or formulation studies rather than clinical outcome evidence.")
    elif intent == "benefit":
        notes.append("Benefit claims should be treated as preliminary unless the cited source reports measured outcomes, comparator results, or trial completion details.")
    else:
        notes.append("Use the source links and retrieved passages to inspect whether each cited record directly addresses the question.")
    return notes


def intent_relevance(intent: str, text: str) -> float:
    terms = INTENT_TERMS.get(intent, BENEFIT_TERMS)
    overlap = term_overlap(set(terms), text)
    if intent == "statistics":
        return effectiveness_statistic_relevance(text)
    if intent == "comparison" and set(tokenize(text)).intersection(COMPARISON_TERMS):
        overlap += 0.35
    if intent == "mechanism" and set(tokenize(text)).intersection(MECHANISM_TERMS):
        overlap += 0.35
    if intent == "trial" and set(tokenize(text)).intersection(TRIAL_TERMS):
        overlap += 0.25
    if intent == "label" and set(tokenize(text)).intersection(LABEL_TERMS):
        overlap += 0.25
    if intent == "safety" and set(tokenize(text)).intersection(SAFETY_TERMS):
        overlap += 0.25
    return min(overlap, 1.0)


def direct_answer_supported(intent: str, chunks: list[RetrievedChunk]) -> bool:
    if intent == "benefit":
        return bool(chunks)
    if intent == "statistics":
        return any(has_effectiveness_statistic(chunk.text) for chunk in chunks)
    return any(intent_relevance(intent, f"{chunk.title} {chunk.text}") >= 0.18 for chunk in chunks)


def partial_direct_answer(workspace: Workspace, intent: str, retrieved: list[RetrievedChunk]) -> str:
    topic = topic_text(workspace)
    requested = {
        "comparison": "a direct comparison",
        "label": "direct FDA-label context",
        "mechanism": "a direct mechanism explanation",
        "safety": "direct safety evidence",
        "statistics": "quantitative effectiveness statistics",
        "trial": "direct trial evidence",
    }.get(intent, "direct evidence")
    return (
        f"For {topic}, I found topical sources, but the retrieved passages do not strongly provide {requested}. "
        "The evidence below is the closest indexed context rather than a complete answer."
    )


def directness_warning(intent: str) -> str:
    requested = {
        "comparison": "direct comparator outcomes",
        "label": "specific FDA-label statements",
        "mechanism": "mechanism-specific explanations",
        "safety": "safety-specific evidence",
        "statistics": "usable numerical effectiveness results",
        "trial": "trial-specific details",
    }.get(intent, "direct support")
    return f"Closest-match warning: the retrieved passages have limited {requested}; inspect the source links before relying on this answer."


def synthesized_claim(chunk: RetrievedChunk, intent: str) -> str:
    sentence = best_sentence(chunk, terms_for_intent(intent))
    context = source_context_phrase(chunk)
    verb = {
        "benefit": "supports the relevance of this intervention by noting that",
        "comparison": "addresses comparison context by noting that",
        "mechanism": "addresses mechanism or delivery context by noting that",
        "safety": "highlights a safety consideration by noting that",
        "trial": "describes study context by noting that",
        "label": "provides regulatory context by noting that",
    }[intent]
    return f"{context} {verb} {claim_clause(sentence)} {inline_citation(chunk)}. {apa_reference(chunk)}"


def statistical_claim(chunk: RetrievedChunk) -> str:
    sentence = best_sentence(chunk, STATISTIC_TERMS | OUTCOME_TERMS | BENEFIT_TERMS)
    numbers = extract_numbers(sentence) or extract_numbers(chunk.text)
    number_text = ", ".join(numbers[:5])
    if number_text:
        return (
            f"{source_context_phrase(chunk)} provides the quantitative signal {number_text}; the relevant passage says "
            f"{claim_clause(sentence)} {inline_citation(chunk)}. {apa_reference(chunk)}"
        )
    return synthesized_claim(chunk, "benefit")


def terms_for_intent(intent: str) -> set[str]:
    if intent == "statistics":
        return STATISTIC_TERMS | OUTCOME_TERMS | BENEFIT_TERMS
    if intent == "comparison":
        return COMPARISON_TERMS | BENEFIT_TERMS | OUTCOME_TERMS
    if intent == "mechanism":
        return MECHANISM_TERMS | BENEFIT_TERMS
    if intent == "safety":
        return SAFETY_TERMS | LABEL_TERMS
    if intent == "trial":
        return TRIAL_TERMS | BENEFIT_TERMS
    if intent == "label":
        return LABEL_TERMS | SAFETY_TERMS | BENEFIT_TERMS
    return BENEFIT_TERMS | TRIAL_TERMS | LABEL_TERMS


def has_quantitative_signal(text: str) -> bool:
    return bool(extract_numbers(text)) and quantitative_relevance(text) > 0


def has_effectiveness_statistic(text: str) -> bool:
    return any(effectiveness_statistic_relevance(sentence) >= 0.72 for sentence in split_sentences(normalize_passage(text)))


def effectiveness_statistic_relevance(text: str) -> float:
    numbers = extract_numbers(text)
    if not numbers:
        return 0.0
    terms = set(tokenize(text))
    lowered = text.lower()
    score = min(len(numbers), 4) / 8
    if terms.intersection({"efficacy", "effective", "effectiveness", "improved", "improvement", "reduced", "reduction", "response", "success"}):
        score += 0.38
    if terms.intersection({"lesion", "lesions", "comedones", "microcomedones", "clearance", "outcome", "score", "scores"}):
        score += 0.28
    if any(term in lowered for term in ["p =", "p<", "confidence interval", "response rate", "lesion count", "mean reduction"]):
        score += 0.3
    if any(term in lowered for term in ["molar ratio", "dose", "mg", "formulation", "containing 3%", "cream containing"]):
        score -= 0.32
    if any(term in lowered for term in ["adverse event", "adverse reaction", "erythema", "contact dermatitis", "edema"]):
        score -= 0.25
    if lowered.startswith(("this is a", "the current study proposes", "the results of the study will")):
        score -= 0.3
    return max(score, 0.0)


def quantitative_relevance(text: str) -> float:
    terms = set(tokenize(text))
    numbers = extract_numbers(text)
    if not numbers:
        return 0.0
    score = min(len(numbers), 6) / 6
    if terms.intersection(OUTCOME_TERMS):
        score += 0.35
    if terms.intersection(STATISTIC_TERMS):
        score += 0.25
    lowered = text.lower()
    if any(term in lowered for term in ["p =", "p<", "confidence interval", "ci ", "response rate", "lesion count"]):
        score += 0.25
    if table_like(text):
        score -= 0.15
    if terms.intersection({"dose", "mg", "ratio", "molar", "phase"}):
        score -= 0.12
    return max(score, 0.0)


def extract_numbers(text: str) -> list[str]:
    patterns = [
        r"\b\d+(?:\.\d+)?\s?%",
        r"\bp\s?[<=>]\s?0?\.\d+",
        r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|g|weeks?|months?|years?|subjects?|patients?|participants?)\b",
        r"\bn\s?=\s?\d+",
        r"\b\d+(?:\.\d+)?\s?(?:to|-)\s?\d+(?:\.\d+)?\b",
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    seen: set[str] = set()
    unique = []
    for value in found:
        cleaned = value.strip()
        key = cleaned.lower()
        if key not in seen:
            unique.append(cleaned)
            seen.add(key)
    return unique


def safety_chunk_quality(chunk: RetrievedChunk) -> int:
    terms = set(tokenize(chunk.text))
    quality = len(terms.intersection(SAFETY_TERMS))
    if chunk.source_type in {SourceType.fda_label, SourceType.fda_adverse_event}:
        quality += 4
    if terms.intersection({"tolerability", "tolerated", "phototoxicity", "photoallergenicity", "postmarketing"}):
        quality += 3
    if "risk factor" in chunk.text.lower() or table_like(chunk.text):
        quality -= 3
    if has_usable_sentence(chunk, SAFETY_TERMS | LABEL_TERMS):
        quality += 2
    return quality


def has_usable_sentence(chunk: RetrievedChunk, preferred_terms: set[str]) -> bool:
    text = normalize_passage(chunk.text)
    return any(
        set(tokenize(sentence)).intersection(preferred_terms) and sentence_quality(sentence) >= 0
        for sentence in split_sentences(text)
    )


def best_sentence(chunk: RetrievedChunk, preferred_terms: set[str]) -> str:
    text = normalize_passage(chunk.text)
    sentences = split_sentences(text)
    polished = [sentence for sentence in sentences if sentence_quality(sentence) >= 0]
    if polished:
        sentences = polished
    if not sentences:
        return fallback_claim(chunk)
    scored = sorted(
        sentences,
        key=lambda sentence: (
            len(set(tokenize(sentence)).intersection(preferred_terms)),
            quantitative_relevance(sentence),
            benefit_signal(sentence),
            len(set(tokenize(sentence)).intersection(set(chunk.matched_terms))),
            -abs(len(sentence) - 180),
        ),
        reverse=True,
    )
    return trim_sentence(scored[0])


def split_sentences(text: str) -> list[str]:
    candidates = re.split(r"(?<=[.!?])\s+", text)
    return [
        candidate.strip(" -•\n\t")
        for candidate in candidates
        if 55 <= len(candidate.strip()) <= 360 and not table_like(candidate)
    ]


def split_safety_sentences(text: str) -> list[str]:
    candidates = re.split(r"(?<=[.!?])\s+", text)
    return [
        candidate.strip(" -•\n\t")
        for candidate in candidates
        if 24 <= len(candidate.strip()) <= 360 and not table_like(candidate)
    ]


def normalize_passage(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.replace("•", ". "))
    cleaned = re.sub(r"\[\s*see[^\]]+\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d+(\.\d+)?\s+(Postmarketing Experience|Clinical Trials Experience|Adverse Reactions)\b", " ", cleaned)
    return cleaned.strip()


def table_like(text: str) -> bool:
    tokens = text.split()
    if not tokens:
        return False
    numeric = sum(1 for token in tokens if any(char.isdigit() for char in token))
    return numeric / len(tokens) > 0.28


def benefit_signal(sentence: str) -> int:
    terms = set(tokenize(sentence))
    signal = len(terms.intersection({"used", "treat", "treats", "reduced", "reduce", "improve", "efficacy", "therapeutic"}))
    if sentence.strip().lower().startswith(("therefore", "the results", "this is a", "the current study")):
        signal -= 2
    return signal


def sentence_quality(sentence: str) -> int:
    stripped = sentence.strip()
    lowered = sentence.strip().lower()
    quality = 0
    if lowered.startswith(("therefore", "as described before", "the following adverse reactions", "the results of the study")):
        quality -= 4
    if lowered.startswith(("defined as", "based on the data", "to subject dropouts")):
        quality -= 3
    if re.match(r"^\d+(\.\d+)?\b", lowered):
        quality -= 3
    if stripped and stripped[0].islower():
        quality -= 2
    if lowered.startswith(("no ", "azelaic", "treatment", "cosmeceuticals", "microcomedones", "it is non")):
        quality += 2
    if table_like(sentence):
        quality -= 5
    return quality


def trim_sentence(sentence: str, limit: int = 280) -> str:
    sentence = sentence.strip().rstrip(".")
    if len(sentence) <= limit:
        return sentence
    return sentence[:limit].rsplit(" ", 1)[0].rstrip(",;:")


def fallback_claim(chunk: RetrievedChunk) -> str:
    source = chunk.title or chunk.citation
    return f"{source} contains a retrieved passage relevant to {', '.join(chunk.matched_terms[:3]) or 'the question'}"


def claim_clause(sentence: str) -> str:
    cleaned = re.sub(r"^(moreover|therefore|because|as described before),?\s+", "", sentence.strip(), flags=re.IGNORECASE)
    if not cleaned:
        return sentence
    return cleaned[0].lower() + cleaned[1:]


def source_context_phrase(chunk: RetrievedChunk) -> str:
    if chunk.source_type == SourceType.pubmed:
        return f"The PubMed record {source_title(chunk)}"
    if chunk.source_type == SourceType.clinical_trials:
        details = ", ".join(item for item in [chunk.status, chunk.phase] if item)
        suffix = f" ({details})" if details else ""
        return f"The ClinicalTrials.gov record {source_title(chunk)}{suffix}"
    if chunk.source_type == SourceType.fda_label:
        return f"The FDA label record {source_title(chunk)}"
    return f"The openFDA adverse-event record {source_title(chunk)}"


def source_title(chunk: RetrievedChunk) -> str:
    return f"“{chunk.title}”" if chunk.title else chunk.citation


def inline_citation(chunk: RetrievedChunk) -> str:
    if chunk.source_type == SourceType.pubmed:
        return f"(PubMed, {chunk.external_id or chunk.citation})"
    if chunk.source_type == SourceType.clinical_trials:
        return f"(ClinicalTrials.gov, {chunk.external_id or chunk.citation})"
    if chunk.source_type == SourceType.fda_label:
        return f"(openFDA, {chunk.external_id or chunk.citation})"
    return f"(openFDA adverse-event reports, {chunk.external_id or chunk.citation})"


def apa_reference(chunk: RetrievedChunk) -> str:
    year = publication_year(chunk.publication_date)
    date = year or "n.d."
    title = chunk.title.rstrip(".") if chunk.title else chunk.citation
    if chunk.source_type == SourceType.pubmed:
        return f"Reference: {title}. ({date}). PubMed. {chunk.external_id}."
    if chunk.source_type == SourceType.clinical_trials:
        return f"Reference: ClinicalTrials.gov. ({date}). {title}. {chunk.external_id}."
    if chunk.source_type == SourceType.fda_label:
        return f"Reference: openFDA. ({date}). {title}. Drug label record {chunk.external_id}."
    return f"Reference: openFDA. ({date}). {title}. Adverse-event report summary {chunk.external_id}."


def publication_year(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(19|20)\d{2}", value)
    return match.group(0) if match else None


def direct_answer_text(workspace: Workspace, question: str, retrieved: list[RetrievedChunk], has_safety: bool) -> str:
    topic = topic_text(workspace)
    source_mix = source_mix_text(retrieved)
    intent = question_intent(question)
    if intent == "statistics":
        numeric_count = sum(1 for chunk in retrieved if has_quantitative_signal(chunk.text))
        return (
            f"For {topic}, I found {numeric_count} retrieved passage{'s' if numeric_count != 1 else ''} with quantitative signals. "
            "The evidence section separates actual numbers from broader effectiveness context, and it will not treat non-outcome numbers as proof of effectiveness."
        )
    if intent == "comparison":
        return (
            f"For {topic}, the answer focuses on comparison evidence from {source_mix}. "
            "Where the retrieved records only describe a comparator study design rather than results, the uncertainty section calls that out."
        )
    if intent == "mechanism":
        return (
            f"For {topic}, the answer focuses on mechanism, pharmacology, or delivery evidence from {source_mix}. "
            "Clinical benefits and safety are kept separate from mechanism claims."
        )
    if intent == "trial":
        return (
            f"For {topic}, the answer focuses on indexed trial records from {source_mix}. "
            "Trial status, phase, comparator context, and outcome availability are treated separately from proven effectiveness."
        )
    if intent == "label":
        return (
            f"For {topic}, the answer focuses on regulatory-label context from {source_mix}. "
            "Label statements are cited separately from literature or trial evidence."
        )
    if set(tokenize(question)).intersection(SAFETY_TERMS):
        return (
            f"For {topic}, the retrieved sources include safety-relevant evidence from {source_mix}. "
            "The answer below synthesizes the cited records first, while the retrieved passages remain available for inspection."
        )
    if has_safety:
        return (
            f"For {topic}, the indexed evidence suggests possible benefit or therapeutic relevance, with safety notes separated below. "
            "The summary below separates benefit evidence from safety notes and uncertainty."
        )
    return (
        f"For {topic}, the retrieved evidence provides relevant context from {source_mix}. "
        "The summary below synthesizes the highest-matching records and cites each source for inspection."
    )


def topic_text(workspace: Workspace) -> str:
    return f"{workspace.intervention or ''} {workspace.condition}".strip()


def source_mix_text(retrieved: list[RetrievedChunk]) -> str:
    counts = Counter(chunk.source_type for chunk in retrieved)
    parts = []
    for source_type, count in counts.items():
        label = source_label_for(source_type, plural=count != 1)
        parts.append(f"{count} {label}")
    return ", ".join(parts) if parts else "the indexed sources"


def source_label_for(source_type: SourceType, plural: bool) -> str:
    labels = {
        SourceType.pubmed: ("literature source", "literature sources"),
        SourceType.clinical_trials: ("trial record", "trial records"),
        SourceType.fda_label: ("FDA label passage", "FDA label passages"),
        SourceType.fda_adverse_event: ("FDA adverse-event signal", "FDA adverse-event signals"),
    }
    singular, plural_label = labels[source_type]
    return plural_label if plural else singular
