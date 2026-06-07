from __future__ import annotations

from collections import Counter

from triallens.models import Answer, EvidenceBrief, EvidenceChunk, EvidenceSource, RetrievedChunk, SourceType, Workspace
from triallens.text import chunk_text, cosine, lexical_score, stable_embedding, tokenize


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
        question: str,
        chunks: list[EvidenceChunk],
        source_types: list[SourceType] | None = None,
        limit: int = 6,
    ) -> list[RetrievedChunk]:
        query_embedding = stable_embedding(question)
        filtered = [chunk for chunk in chunks if source_types is None or chunk.source_type in source_types]
        scored = []
        for chunk in filtered:
            semantic = cosine(query_embedding, chunk.embedding)
            lexical = lexical_score(question, chunk.text)
            score = (0.58 * semantic) + (0.42 * lexical)
            scored.append((score, chunk))
        ranked = sorted(scored, key=lambda item: item[0], reverse=True)[:limit]
        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                source_id=chunk.source_id,
                source_type=chunk.source_type,
                citation=chunk.citation,
                text=chunk.text,
                score=round(score, 4),
            )
            for score, chunk in ranked
            if score > 0.03
        ]


class AnswerService:
    def answer(self, workspace: Workspace, question: str, retrieved: list[RetrievedChunk]) -> Answer:
        if not retrieved:
            return Answer(
                workspace_id=workspace.id,
                question=question,
                short_answer="I do not have enough retrieved evidence to answer this question from the current workspace.",
                evidence=[],
                limitations=[
                    "Try ingesting more sources or asking a question closer to the indexed evidence.",
                    "TrialLens does not provide medical advice or patient-specific recommendations.",
                ],
                citations=[],
                retrieved_chunks=[],
            )

        citations = list(dict.fromkeys(chunk.citation for chunk in retrieved))
        evidence = [self._evidence_sentence(chunk) for chunk in retrieved[:4]]
        safety_chunks = [chunk for chunk in retrieved if chunk.source_type == SourceType.fda_adverse_event]
        limitations = [
            "This answer is generated only from retrieved workspace sources and may omit evidence not indexed here.",
            "It is not medical advice, diagnosis, or treatment guidance.",
        ]
        if safety_chunks:
            limitations.append("FDA adverse event reports are suspected reports and do not prove causality or incidence.")

        source_mix = Counter(chunk.source_type.value for chunk in retrieved)
        mix_text = ", ".join(f"{count} {source.replace('_', ' ')}" for source, count in source_mix.items())
        short_answer = (
            f"The retrieved evidence for {workspace.intervention or workspace.condition} is mixed across {mix_text}. "
            "The strongest answer should be read through the cited source passages rather than as a clinical recommendation."
        )
        return Answer(
            workspace_id=workspace.id,
            question=question,
            short_answer=short_answer,
            evidence=evidence,
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

