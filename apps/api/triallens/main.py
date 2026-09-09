from __future__ import annotations

from typing import Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from triallens.conversation import ConversationService, chat_configured, retrieval_question
from triallens.evals import static_eval_report
from triallens.models import (
    Answer,
    AskRequest,
    EvidenceBrief,
    EvidenceExtraction,
    EvidenceSource,
    ExtractionUpdate,
    Workspace,
    WorkspaceCreate,
)
from triallens.rag import AnswerService, BriefService, Retriever, build_chunks, build_extractions
from triallens.sources import fetch_sources
from triallens.store import JsonStore
from triallens.usage import UsageLedger

app = FastAPI(
    title="TrialLens API",
    description="Biomedical evidence intelligence assistant with cited retrieval.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = JsonStore()
retriever = Retriever()
answer_service = AnswerService()
brief_service = BriefService()
conversation_service = ConversationService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "triallens-api", "chat": "configured" if chat_configured() else "extractive"}


@app.get("/usage")
def usage() -> dict:
    return UsageLedger().status()


@app.post("/workspaces", response_model=Workspace)
def create_workspace(payload: WorkspaceCreate) -> Workspace:
    workspace = Workspace(
        condition=payload.condition.strip(),
        intervention=payload.intervention.strip() if payload.intervention else None,
        source_types=payload.source_types,
    )
    return store.create_workspace(workspace)


@app.get("/workspaces", response_model=list[Workspace])
def list_workspaces() -> list[Workspace]:
    return store.list_workspaces()


@app.post("/workspaces/{workspace_id}/ingest", response_model=dict[str, Union[int, str]])
async def ingest_workspace(workspace_id: str) -> dict[str, Union[int, str]]:
    workspace = _workspace_or_404(workspace_id)
    sources = await fetch_sources(workspace)
    chunks = build_chunks(sources)
    extractions = build_extractions(sources, workspace)
    store.replace_workspace_evidence(workspace.id, sources, chunks)
    store.replace_workspace_extractions(workspace.id, extractions)
    workspace.status = "ingested" if sources else "partial"
    store.update_workspace(workspace)
    return {"workspace_id": workspace.id, "sources": len(sources), "chunks": len(chunks), "extractions": len(extractions)}


@app.get("/workspaces/{workspace_id}/sources", response_model=list[EvidenceSource])
def list_sources(workspace_id: str) -> list[EvidenceSource]:
    _workspace_or_404(workspace_id)
    return store.list_sources(workspace_id)


@app.post("/workspaces/{workspace_id}/extract", response_model=dict[str, Union[int, str]])
def extract_workspace(workspace_id: str) -> dict[str, Union[int, str]]:
    workspace = _workspace_or_404(workspace_id)
    sources = store.list_sources(workspace_id)
    if not sources:
        raise HTTPException(status_code=400, detail="No sources indexed for this workspace")
    extractions = build_extractions(sources, workspace)
    store.replace_workspace_extractions(workspace_id, extractions)
    return {"workspace_id": workspace_id, "extractions": len(extractions)}


@app.get("/workspaces/{workspace_id}/extractions", response_model=list[EvidenceExtraction])
def list_extractions(workspace_id: str) -> list[EvidenceExtraction]:
    _workspace_or_404(workspace_id)
    return store.list_extractions(workspace_id)


@app.patch("/workspaces/{workspace_id}/extractions/{extraction_id}", response_model=EvidenceExtraction)
def update_extraction(workspace_id: str, extraction_id: str, payload: ExtractionUpdate) -> EvidenceExtraction:
    _workspace_or_404(workspace_id)
    updated = store.update_extraction(workspace_id, extraction_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return updated


@app.post("/workspaces/{workspace_id}/ask", response_model=Answer)
def ask(workspace_id: str, payload: AskRequest) -> Answer:
    workspace = _workspace_or_404(workspace_id)
    chunks = store.list_chunks(workspace_id)
    sources = store.list_sources(workspace_id)
    extractions = store.list_extractions(workspace_id)
    history = []
    previous_id = payload.previous_answer_id
    seen = set()
    while previous_id and len(history) < 6:
        previous = store.get_answer(previous_id)
        if not previous or previous.workspace_id != workspace_id:
            raise HTTPException(status_code=404, detail="Previous answer not found in workspace")
        if previous.id in seen:
            raise HTTPException(status_code=400, detail="Invalid conversation chain")
        if (previous.mode != payload.mode or previous.source_id != payload.source_id
                or set(previous.source_types or []) != set(payload.source_types or [])):
            raise HTTPException(status_code=400, detail="Source scope changed. Start a new conversation.")
        seen.add(previous.id)
        history.insert(0, previous)
        previous_id = previous.previous_answer_id
    query = retrieval_question(payload.question, history)
    if payload.source_types is not None:
        sources = [source for source in sources if source.source_type in payload.source_types]
        extractions = [row for row in extractions if row.source_type in payload.source_types]
        chunks = [chunk for chunk in chunks if chunk.source_type in payload.source_types]
    if payload.mode == "document":
        if not payload.source_id:
            raise HTTPException(status_code=400, detail="source_id is required for document mode")
        source = next((item for item in sources if item.id == payload.source_id), None)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found in workspace")
        document_chunks = [chunk for chunk in chunks if chunk.source_id == source.id]
        document_extractions = [row for row in extractions if row.source_id == source.id]
        retrieved = retriever.retrieve(workspace, query, document_chunks, [source], [source.source_type])
        answer = answer_service.answer_document(workspace, source, query, document_chunks, retrieved, document_extractions)
    else:
        retrieved = retriever.retrieve(workspace, query, chunks, sources, payload.source_types)
        answer = answer_service.answer(workspace, query, retrieved, extractions)
    answer.question = payload.question
    answer.previous_answer_id = payload.previous_answer_id
    answer.mode, answer.source_id, answer.source_types = payload.mode, payload.source_id, payload.source_types
    ranked_ids = list(dict.fromkeys([chunk.source_id for chunk in retrieved] + [row.source_id for row in extractions if row.citation in answer.citations]))
    source_by_id = {item.id: item for item in sources}
    selected_sources = [source_by_id[sid] for sid in ranked_ids if sid in source_by_id]
    if payload.mode == "document":
        selected_sources = [source]
    answer = conversation_service.generate(workspace, payload.question, history, selected_sources, answer)
    return store.save_answer(answer)


@app.get("/workspaces/{workspace_id}/retrievals/{answer_id}", response_model=Answer)
def retrievals(workspace_id: str, answer_id: str) -> Answer:
    _workspace_or_404(workspace_id)
    answer = store.get_answer(answer_id)
    if not answer or answer.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Answer not found")
    return answer


@app.get("/workspaces/{workspace_id}/brief", response_model=EvidenceBrief)
def brief(workspace_id: str) -> EvidenceBrief:
    workspace = _workspace_or_404(workspace_id)
    # Rebuild from current review state and saved answers; never serve a stale cached brief.
    generated = brief_service.generate(workspace, store.list_sources(workspace_id),
                                       store.list_extractions(workspace_id), store.list_answers(workspace_id))
    return generated


@app.get("/workspaces/{workspace_id}/answers", response_model=list[Answer])
def answers(workspace_id: str) -> list[Answer]:
    _workspace_or_404(workspace_id)
    return store.list_answers(workspace_id)


@app.patch("/workspaces/{workspace_id}/answers/{answer_id}/brief", response_model=Answer)
def save_answer_to_brief(workspace_id: str, answer_id: str, saved: bool = True) -> Answer:
    _workspace_or_404(workspace_id)
    answer = store.get_answer(answer_id)
    if not answer or answer.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Answer not found in workspace")
    answer.saved_to_brief = saved
    return store.save_answer(answer)


@app.get("/evals")
def evals():
    return static_eval_report()


def _workspace_or_404(workspace_id: str) -> Workspace:
    workspace = store.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace
