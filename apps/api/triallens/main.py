from __future__ import annotations

from typing import Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from triallens.evals import static_eval_report
from triallens.models import Answer, AskRequest, EvidenceBrief, EvidenceSource, Workspace, WorkspaceCreate
from triallens.rag import AnswerService, BriefService, Retriever, build_chunks
from triallens.sources import fetch_sources
from triallens.store import JsonStore

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "triallens-api"}


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
    store.replace_workspace_evidence(workspace.id, sources, chunks)
    workspace.status = "ingested" if sources else "partial"
    store.update_workspace(workspace)
    return {"workspace_id": workspace.id, "sources": len(sources), "chunks": len(chunks)}


@app.get("/workspaces/{workspace_id}/sources", response_model=list[EvidenceSource])
def list_sources(workspace_id: str) -> list[EvidenceSource]:
    _workspace_or_404(workspace_id)
    return store.list_sources(workspace_id)


@app.post("/workspaces/{workspace_id}/ask", response_model=Answer)
def ask(workspace_id: str, payload: AskRequest) -> Answer:
    workspace = _workspace_or_404(workspace_id)
    chunks = store.list_chunks(workspace_id)
    sources = store.list_sources(workspace_id)
    retrieved = retriever.retrieve(workspace, payload.question, chunks, sources, payload.source_types)
    answer = answer_service.answer(workspace, payload.question, retrieved)
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
    existing = store.get_brief(workspace_id)
    if existing:
        return existing
    generated = brief_service.generate(workspace, store.list_sources(workspace_id))
    return store.save_brief(generated)


@app.get("/evals")
def evals():
    return static_eval_report()


def _workspace_or_404(workspace_id: str) -> Workspace:
    workspace = store.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace
