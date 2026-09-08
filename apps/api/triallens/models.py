from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourceType(str, Enum):
    pubmed = "pubmed"
    clinical_trials = "clinical_trials"
    fda_label = "fda_label"
    fda_adverse_event = "fda_adverse_event"


class WorkspaceCreate(BaseModel):
    condition: str = Field(min_length=2, max_length=120)
    intervention: Optional[str] = Field(default=None, max_length=120)
    source_types: list[SourceType] = Field(
        default_factory=lambda: [
            SourceType.pubmed,
            SourceType.clinical_trials,
            SourceType.fda_label,
            SourceType.fda_adverse_event,
        ]
    )


class Workspace(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    condition: str
    intervention: Optional[str] = None
    source_types: list[SourceType]
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    status: Literal["created", "ingested", "partial", "failed"] = "created"


class EvidenceSource(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_type: SourceType
    external_id: str
    title: str
    abstract: str = ""
    url: Optional[str] = None
    publication_date: Optional[str] = None
    status: Optional[str] = None
    phase: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)


class EvidenceChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_id: str
    source_type: SourceType
    text: str
    citation: str
    section: str = "summary"
    embedding: list[float] = Field(default_factory=list)


class EvidenceExtraction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    source_id: str
    source_type: SourceType
    external_id: str = ""
    title: str
    source_url: Optional[str] = None
    publication_date: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    citation: str
    population_context: str = "Not specified in indexed summary."
    intervention: str = "Not specified in indexed summary."
    comparator: str = "Not specified in indexed summary."
    outcome_result: str = "No direct outcome/result extracted."
    safety_note: str = "No safety-specific note extracted."
    supporting_quote: str = ""
    source_overview: str = "No source-level summary extracted."
    methods_context: str = "Study design or source methods were not separately extracted."
    source_sections: list[str] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)
    evidence_limitations: list[str] = Field(default_factory=list)
    source_understanding: list[str] = Field(default_factory=list)
    source_passages: list[str] = Field(default_factory=list)
    field_evidence: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=0.45, ge=0, le=1)
    review_status: Literal["unreviewed", "reviewed", "needs_review"] = "unreviewed"
    has_quantitative_result: bool = False
    status: Optional[str] = None
    phase: Optional[str] = None
    created_at: str = Field(default_factory=utc_now)


class RetrievedChunk(BaseModel):
    chunk_id: str
    source_id: str
    source_type: SourceType
    citation: str
    text: str
    score: float
    section: str = "summary"
    title: str = ""
    url: Optional[str] = None
    external_id: str = ""
    publication_date: Optional[str] = None
    status: Optional[str] = None
    phase: Optional[str] = None
    matched_terms: list[str] = Field(default_factory=list)
    relevance_note: str = ""


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    source_types: Optional[list[SourceType]] = None
    mode: Literal["workspace", "document"] = "workspace"
    source_id: Optional[str] = None
    previous_answer_id: Optional[str] = None


class ExtractionUpdate(BaseModel):
    population_context: Optional[str] = Field(default=None, max_length=500)
    intervention: Optional[str] = Field(default=None, max_length=500)
    comparator: Optional[str] = Field(default=None, max_length=500)
    outcome_result: Optional[str] = Field(default=None, max_length=800)
    safety_note: Optional[str] = Field(default=None, max_length=800)
    supporting_quote: Optional[str] = Field(default=None, max_length=1200)
    review_status: Optional[Literal["unreviewed", "reviewed", "needs_review"]] = None


class AnswerTraceItem(BaseModel):
    label: str
    value: str
    detail: str = ""


class Answer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    question: str
    previous_answer_id: Optional[str] = None
    mode: Literal["workspace", "document"] = "workspace"
    source_id: Optional[str] = None
    source_types: Optional[list[SourceType]] = None
    generation_mode: Literal["extractive", "conversational"] = "extractive"
    generation_note: str = ""
    saved_to_brief: bool = False
    short_answer: str
    direct_answer: str = ""
    evidence_map: list[str] = Field(default_factory=list)
    reasoning_summary: list[str] = Field(default_factory=list)
    evidence_synthesis: list[str] = Field(default_factory=list)
    source_readouts: list[str] = Field(default_factory=list)
    evidence_quality: list[str] = Field(default_factory=list)
    facet_coverage: list[str] = Field(default_factory=list)
    answer_trace: list[AnswerTraceItem] = Field(default_factory=list)
    evidence: list[str]
    supporting_evidence: list[str] = Field(default_factory=list)
    safety_limitations: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    limitations: list[str]
    citations: list[str]
    retrieved_chunks: list[RetrievedChunk]
    created_at: str = Field(default_factory=utc_now)


class EvidenceBrief(BaseModel):
    workspace_id: str
    title: str
    overview: str
    source_summary: dict[str, int]
    key_claims: list[str]
    evidence_gaps: list[str]
    safety_note: str
    citations: list[str]
    saved_answers: list[Answer] = Field(default_factory=list)
    review_summary: dict[str, int] = Field(default_factory=dict)
    next_steps: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=utc_now)


class EvalMetric(BaseModel):
    name: str
    score: float
    description: str


class EvalReport(BaseModel):
    generated_at: str = Field(default_factory=utc_now)
    metrics: list[EvalMetric]
    scenarios: list[dict[str, Any]]
