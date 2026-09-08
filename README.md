# TrialLens

TrialLens is a full-stack biomedical evidence intelligence assistant. It lets a user create a research workspace for a condition, drug, or intervention, ingest public biomedical evidence, extract source-level evidence rows, ask citation-grounded questions, inspect retrieved passages, and generate a structured evidence brief.

This project is an evidence navigation tool, not a medical advice or clinical decision support system.

## What It Demonstrates

- Full-stack AI product architecture with `FastAPI` and `Next.js`
- Biomedical source normalization across PubMed, ClinicalTrials.gov, and openFDA-style records
- Evidence extraction table with population/context, intervention, comparator, outcome/result, safety notes, citations, confidence, and review status
- RAG pipeline with chunking, hybrid retrieval, reranking, extraction-first synthesis, citations, and abstention behavior
- Evidence briefs with claims, uncertainty, source separation, and limitations
- Reliability checks for retrieval relevance, extraction coverage, citation support, answer directness, and abstention behavior

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
- Generated answers prefer structured extraction rows before falling back to retrieved passages. An optional server-side Responses API integration generates conversational answers with validated citation identifiers and an explicit extractive fallback.


## Conversational answers

Set `OPENAI_API_KEY` and `TRIALLENS_CHAT_MODEL` in the API process environment. Choose a model available to your account that supports Responses API strict structured outputs. See `apps/api/.env.example`. To load a local environment file, start the backend from `apps/api` with `uvicorn triallens.main:app --env-file .env --port 8000`. The example is a template; `.env` is ignored by Git. Never put the key in frontend code or a `NEXT_PUBLIC_*` variable.

For local startup, run `apps/api/.venv/bin/python apps/api/run.py` from the repository root. The launcher loads `apps/api/.env` automatically; restart it after saving changes. Use `apps/api/.venv/bin/python apps/api/run.py --check` to check configuration without displaying the key or making an API request. The template selects `gpt-4.1-mini` as an initial model; live quality evaluation is still required.

`GET /health` reports whether chat is configured. Without both values, answers are explicitly labeled source excerpts. Provider errors, incomplete output, invented citation identifiers, and long copied passages also fall back with a visible explanation. Requests use `store: false`; the provider receives the research question, up to six prior turns, and selected indexed source content.

Ask preserves answers in the workspace and uses `previous_answer_id` to continue a scoped conversation. Changing the source scope starts a new conversation. Reopen a workspace and use **Continue conversation** on an earlier answer to resume it.

## Research brief

Use **Save to brief** on useful answers after checking their citations. Brief collects these working notes, current review gaps, next steps, and citations. **Export brief** downloads Markdown. Saving is reversible, persists on the backend, and does not certify an answer as validated. The brief is rebuilt from current state so review changes appear immediately.

## Verification and remaining release work

Run `cd apps/api && .venv/bin/python -m pytest tests -q`; run `cd apps/web && npx tsc --noEmit && npm run build`. Build requires access to Google Fonts. See `docs/product-review.md` for the product assessment and the remaining live-model evaluation. Reliability percentages are illustrative development targets, not measured workspace scores.
