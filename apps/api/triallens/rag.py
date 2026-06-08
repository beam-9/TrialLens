from __future__ import annotations

from collections import Counter
import re

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
    def answer(self, workspace: Workspace, question: str, retrieved: list[RetrievedChunk]) -> Answer:
        if not retrieved or not strong_enough(retrieved):
            return abstention_answer(workspace.id, question, retrieved)

        intent = question_intent(question)
        citations = list(dict.fromkeys(chunk.citation for chunk in retrieved))
        evidence_chunks = select_evidence_chunks(retrieved, intent)
        safety_chunks = select_safety_chunks(retrieved)
        if intent == "statistics" and not evidence_chunks:
            return statistics_abstention_answer(workspace, question, retrieved, citations, safety_chunks)
        direct_answer = direct_answer_text(workspace, question, retrieved, bool(safety_chunks))
        supporting_evidence = synthesize_supporting_evidence(workspace, intent, evidence_chunks)
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
