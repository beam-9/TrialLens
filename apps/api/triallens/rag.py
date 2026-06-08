from __future__ import annotations

from collections import Counter

from triallens.models import Answer, EvidenceBrief, EvidenceChunk, EvidenceSource, RetrievedChunk, SourceType, Workspace
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


def build_chunks(sources: list[EvidenceSource]) -> list[EvidenceChunk]:
    chunks: list[EvidenceChunk] = []
    for source in sources:
        source_chunks = chunk_text(source.abstract)
        for idx, text in enumerate(source_chunks, start=1):
            citation = citation_for(source)
            chunks.append(
                EvidenceChunk(
                    workspace_id=source.workspace_id,
                    source_id=source.id,
                    source_type=source.source_type,
                    text=text,
                    citation=citation,
                    section=f"chunk {idx}",
                    embedding=stable_embedding(text),
                )
            )
    return chunks


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
            off_topic_penalty = 0.16 if topic_terms and topic_overlap == 0 else 0.0
            score = (0.42 * semantic) + (0.28 * lexical) + (0.22 * topic_overlap) + (0.18 * question_overlap)
            score = score + source_boost - off_topic_penalty
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
                title=source.title if source else "",
                url=source.url if source else None,
                external_id=source.external_id if source else "",
                matched_terms=matched_terms,
                relevance_note=relevance_note(matched_terms, chunk.source_type),
            )
            for score, chunk, matched_terms, source in ranked
            if score > 0.12 and matched_terms
        ]


class AnswerService:
    def answer(self, workspace: Workspace, question: str, retrieved: list[RetrievedChunk]) -> Answer:
        if not retrieved or not strong_enough(retrieved):
            return abstention_answer(workspace.id, question, retrieved)

        is_safety_question = bool(set(tokenize(question)).intersection(SAFETY_TERMS))
        citations = list(dict.fromkeys(chunk.citation for chunk in retrieved))
        safety_chunks = [chunk for chunk in retrieved if classify_chunk(chunk) == "safety"][:4]
        evidence_chunks = (
            safety_chunks
            if is_safety_question and safety_chunks
            else [chunk for chunk in retrieved if classify_chunk(chunk) in {"benefit", "trial", "label"}][:4]
        )
        uncertainty_chunks = [chunk for chunk in retrieved if classify_chunk(chunk) in {"weak", "trial"}][:3]
        supporting_evidence = [self._evidence_sentence(chunk) for chunk in evidence_chunks] or [
            self._evidence_sentence(chunk) for chunk in retrieved[:3]
        ]
        safety_limitations = [self._evidence_sentence(chunk) for chunk in safety_chunks]
        uncertainty = [
            "Retrieved sources may not include full-text articles, all trial outcomes, unpublished evidence, or all regulatory updates.",
            "Use the source links and citations to inspect the original records before drawing conclusions.",
        ]
        if uncertainty_chunks:
            uncertainty.insert(0, self._evidence_sentence(uncertainty_chunks[0]))
        limitations = [
            "This answer is generated only from retrieved workspace sources and may omit evidence not indexed here.",
            "It is not medical advice, diagnosis, or treatment guidance.",
        ]
        if any(chunk.source_type == SourceType.fda_adverse_event for chunk in retrieved):
            limitations.append("FDA adverse event reports are suspected reports and do not prove causality or incidence.")

        direct_answer = direct_answer_text(workspace, question, retrieved, bool(safety_limitations))
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

    def _evidence_sentence(self, chunk: RetrievedChunk) -> str:
        text = chunk.text
        if len(text) > 260:
            text = text[:257].rsplit(" ", 1)[0] + "..."
        return f"{text} [{chunk.citation}]"


class BriefService:
    def generate(self, workspace: Workspace, sources: list[EvidenceSource]) -> EvidenceBrief:
        counts = Counter(source.source_type.value for source in sources)
        citations = [citation_for(source) for source in sources[:8]]
        key_claims = []
        for source in sources[:5]:
            snippet = source.abstract[:220].rsplit(" ", 1)[0]
            key_claims.append(f"{snippet} [{citation_for(source)}]")
        if not key_claims:
            key_claims.append("No evidence sources have been indexed yet.")

        gaps = [
            "The workspace may not include full-text articles, unpublished evidence, or all regulatory updates.",
            "ClinicalTrials.gov records can describe protocols even when peer-reviewed results are unavailable.",
            "Adverse event reports are useful for signal navigation but cannot establish causality.",
        ]
        return EvidenceBrief(
            workspace_id=workspace.id,
            title=f"Evidence brief: {workspace.intervention or workspace.condition} and {workspace.condition}",
            overview=(
                f"This brief summarizes indexed evidence for {workspace.condition}"
                f"{' with ' + workspace.intervention if workspace.intervention else ''}."
            ),
            source_summary=dict(counts),
            key_claims=key_claims,
            evidence_gaps=gaps,
            safety_note="TrialLens is an evidence navigation tool and does not provide medical advice.",
            citations=citations,
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
    if terms.intersection(SAFETY_TERMS):
        if source_type in {SourceType.fda_label, SourceType.fda_adverse_event}:
            return 0.12
    if terms.intersection(TRIAL_TERMS) and source_type == SourceType.clinical_trials:
        return 0.14
    if terms.intersection(LABEL_TERMS) and source_type == SourceType.fda_label:
        return 0.14
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


def direct_answer_text(workspace: Workspace, question: str, retrieved: list[RetrievedChunk], has_safety: bool) -> str:
    topic = f"{workspace.intervention or ''} {workspace.condition}".strip()
    source_mix = source_mix_text(retrieved)
    if set(tokenize(question)).intersection(SAFETY_TERMS):
        return (
            f"For {topic}, the retrieved sources include safety-relevant evidence from {source_mix}. "
            "Review the cited passages and original source links because these findings are evidence navigation, not clinical guidance."
        )
    if has_safety:
        return (
            f"For {topic}, the retrieved evidence includes both use/effectiveness context and safety limitations. "
            "The strongest directly relevant passages are cited below."
        )
    return (
        f"For {topic}, the retrieved evidence provides relevant context from {source_mix}. "
        "The directly matched passages are cited below for inspection."
    )


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
