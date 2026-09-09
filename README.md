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
python run.py
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

TrialLens uses **Ollama locally by default**, with `qwen3:8b`. No API key or per-answer API credits are needed. Install Ollama from its official distribution or Homebrew (`brew install ollama`), then download the model once with `ollama pull qwen3:8b` while Ollama is running. The model download is approximately 5.2 GB.

Run `apps/api/.venv/bin/python apps/api/run.py` from the repository root. The launcher loads `apps/api/.env`, starts Ollama on localhost when needed with cloud features disabled, and starts the API. It stops only the Ollama process it started when the API exits. Start the frontend separately with `cd apps/web && npm run dev`. Local configuration:

```dotenv
TRIALLENS_CHAT_PROVIDER=ollama
TRIALLENS_LOCAL_MODEL=qwen3:8b
```

The first answer may take longer while the model loads. Source retrieval still contacts the public research services, but answer generation goes only to `127.0.0.1:11434`. Local failures show a labeled extractive fallback; they never trigger paid OpenAI requests. Citations, structured output, incomplete responses, and copied passages are checked for both providers. These checks do not prove semantic correctness; inspect cited evidence.

This setup runs on the developer's Mac. A public deployment needs a separately planned inference host; deploying the web frontend does not make this Mac's local model available to visitors. There are no per-token API fees for local generation, but it consumes memory, electricity, and compute time.

`GET /health` reports the selected provider/model and configuration (not model readiness). `python apps/api/run.py --check` checks settings without displaying keys. Ask preserves answers and source-scoped conversation context. Reopen a workspace and use **Continue conversation** on an earlier answer to resume it.

For optional paid OpenAI generation, explicitly set `TRIALLENS_CHAT_PROVIDER=openai`, `OPENAI_API_KEY`, and `TRIALLENS_CHAT_MODEL=gpt-4.1-mini` in the backend environment. `.env` stays out of Git. No frontend variable should contain a key. This mode retains the US$0.10 spending cap; switching to local does not reset the paid ledger.

## Research brief

Use **Save to brief** on useful answers after checking their citations. Brief collects these working notes, current review gaps, next steps, and citations. **Export brief** downloads Markdown. Saving is reversible, persists on the backend, and does not certify an answer as validated. The brief is rebuilt from current state so review changes appear immediately.

## Verification and remaining release work

Run `cd apps/api && .venv/bin/python -m pytest tests -q`; run `cd apps/web && npx tsc --noEmit && npm run build`. Build requires access to Google Fonts. See `docs/product-review.md` for the product assessment and the remaining live-model evaluation. Reliability percentages are illustrative development targets, not measured workspace scores.


## Small-scale usage limits

For optional OpenAI mode, TrialLens enforces a **US$0.10 cumulative model budget** across all workspaces, with no automatic reset. A persistent SQLite ledger at `apps/api/data/usage.sqlite3` reserves a conservative request allowance before sending to OpenAI, then settles against reported input/output tokens. Concurrent requests share the same ledger. Unknown model pricing or unavailable usage storage stops paid generation. Timeout/unknown-usage reservations remain held; explicit pre-generation HTTP rejections release their reservation. Keep this file when restarting or deploying so the cap persists.

Ask shows the generated-answer count and either local mode or paid budget usage and displays an alert at **100 successfully generated answers**. Successful local answers count toward the alert at zero API cost. Failed attempts and extractive fallbacks do not count as generated answers; any billable provider work still counts toward the spending cap. The spending cap can stop generation before 100 answers. This is an in-app alert, not an email or background notification. Source browsing and brief export do not call the model.

Pricing is configured for GPT-4.1 mini (US$0.40/M input tokens and US$1.60/M output tokens, ignoring cache discounts conservatively). The cap covers requests made through this TrialLens installation and this ledger, not other applications using the same API key, taxes, hosting, or independently deployed copies. `GET /usage` returns counts and costs, never credentials. There is no public reset or budget-increase endpoint.
