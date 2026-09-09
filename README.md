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

TrialLens's original answer engine does not require a language-model API key: it selects extracted evidence and assembles deterministic text. The new OpenAI integration is an optional generation layer, not a requirement for running TrialLens. It is the only hosted provider adapter implemented so far. Another hosted provider or a local model would require its own adapter and quality evaluation; neither is connected automatically.

For the optional OpenAI path, set `OPENAI_API_KEY` and `TRIALLENS_CHAT_MODEL` in the API process environment. Choose a model available to your account that supports Responses API strict structured outputs. See `apps/api/.env.example`. To load a local environment file, start the backend from `apps/api` with `uvicorn triallens.main:app --env-file .env --port 8000`. The example is a template; `.env` is ignored by Git. Never put the key in frontend code or a `NEXT_PUBLIC_*` variable.

For local startup, run `apps/api/.venv/bin/python apps/api/run.py` from the repository root. The launcher loads `apps/api/.env` automatically; restart it after saving changes. Use `apps/api/.venv/bin/python apps/api/run.py --check` to check configuration without displaying the key or making an API request. The template selects `gpt-4.1-mini` as an initial model; live quality evaluation is still required.

`GET /health` reports whether chat is configured. Without both values, answers are explicitly labeled source excerpts. Provider errors, incomplete output, invented citation identifiers, and long copied passages also fall back with a visible explanation. Requests use `store: false`; the provider receives the research question, up to six prior turns, and selected indexed source content.

Ask preserves answers in the workspace and uses `previous_answer_id` to continue a scoped conversation. Changing the source scope starts a new conversation. Reopen a workspace and use **Continue conversation** on an earlier answer to resume it.

## Research brief

Use **Save to brief** on useful answers after checking their citations. Brief collects these working notes, current review gaps, next steps, and citations. **Export brief** downloads Markdown. Saving is reversible, persists on the backend, and does not certify an answer as validated. The brief is rebuilt from current state so review changes appear immediately.

## Verification and remaining release work

Run `cd apps/api && .venv/bin/python -m pytest tests -q`; run `cd apps/web && npx tsc --noEmit && npm run build`. Build requires access to Google Fonts. See `docs/product-review.md` for the product assessment and the remaining live-model evaluation. Reliability percentages are illustrative development targets, not measured workspace scores.


## Small-scale usage limits

TrialLens enforces a **US$0.10 cumulative model budget** across all workspaces, with no automatic reset. A persistent SQLite ledger at `apps/api/data/usage.sqlite3` reserves a conservative request allowance before sending to OpenAI, then settles against reported input/output tokens. Concurrent requests share the same ledger. Unknown model pricing or unavailable usage storage stops paid generation. Timeout/unknown-usage reservations remain held; explicit pre-generation HTTP rejections release their reservation. Keep this file when restarting or deploying so the cap persists.

Ask shows the generated-answer count and budget usage and displays an alert at **100 successfully generated answers**. Failed attempts and extractive fallbacks do not count as generated answers; any billable provider work still counts toward the spending cap. The spending cap can stop generation before 100 answers. This is an in-app alert, not an email or background notification. Source browsing and brief export do not call the model.

Pricing is configured for GPT-4.1 mini (US$0.40/M input tokens and US$1.60/M output tokens, ignoring cache discounts conservatively). The cap covers requests made through this TrialLens installation and this ledger, not other applications using the same API key, taxes, hosting, or independently deployed copies. `GET /usage` returns counts and costs, never credentials. There is no public reset or budget-increase endpoint.
