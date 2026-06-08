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


class RetrievedChunk(BaseModel):
    chunk_id: str
    source_id: str
    source_type: SourceType
    citation: str
    text: str
    score: float
    title: str = ""
    url: Optional[str] = None
    external_id: str = ""
    matched_terms: list[str] = Field(default_factory=list)
    relevance_note: str = ""


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    source_types: Optional[list[SourceType]] = None


class Answer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    workspace_id: str
    question: str
    short_answer: str
    direct_answer: str = ""
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
    generated_at: str = Field(default_factory=utc_now)


class EvalMetric(BaseModel):
    name: str
    score: float
    description: str


class EvalReport(BaseModel):
    generated_at: str = Field(default_factory=utc_now)
    metrics: list[EvalMetric]
    scenarios: list[dict[str, Any]]
