# TrialLens

TrialLens is a full-stack biomedical evidence intelligence assistant. It lets a user create a research workspace for a condition, drug, or intervention, ingest public biomedical evidence, ask citation-grounded questions, inspect retrieved passages, and generate a structured evidence brief.

This project is an evidence navigation tool, not a medical advice or clinical decision support system.

## What It Demonstrates

- Full-stack AI product architecture with `FastAPI` and `Next.js`
- Biomedical source normalization across PubMed, ClinicalTrials.gov, and openFDA-style records
- RAG pipeline with chunking, hybrid retrieval, reranking, citations, and abstention behavior
- Evidence briefs with claims, uncertainty, source separation, and limitations
- Evaluation page for retrieval hit rate, citation coverage, faithfulness, and abstention checks

## Repository Layout

```text
apps/
  api/     FastAPI backend, ingestion, retrieval, answer generation, evals
  web/     Next.js frontend
docs/
  architecture.md
```

## Quick Start

Backend:

```bash
cd apps/api
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn triallens.main:app --reload --port 8000
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`.

## MVP Notes

- The backend includes public API clients and deterministic sample fallbacks so the app remains usable offline or under API rate limits.
- The initial vector layer uses local deterministic embeddings plus lexical scoring. The production path is documented for pgvector or Qdrant.
- Generated answers are extractive and citation-grounded in the MVP. A hosted LLM can be added behind `AnswerService` without changing the frontend contract.

