# TrialLens Architecture

## System Shape

TrialLens is organized around research workspaces. A workspace has a condition, optional intervention, normalized evidence sources, chunks, structured evidence extraction rows, question answers, and evaluation results.

```mermaid
flowchart LR
  UI["Next.js research workspace"] --> API["FastAPI API"]
  API --> Ingest["Ingestion service"]
  Ingest --> Sources["PubMed / ClinicalTrials.gov / openFDA"]
  Ingest --> Store["Workspace store"]
  Store --> Extract["Evidence extraction table"]
  Store --> Retriever["Hybrid retriever"]
  Extract --> Answer["Extraction-first answer service"]
  Retriever --> Answer
  Answer --> API
  Store --> Evals["RAG evaluation service"]
```

## MVP Storage

The MVP uses a JSON-backed repository to keep local setup simple. The schema mirrors the planned database entities:

- workspaces
- evidence sources
- chunks
- evidence extractions
- answers
- retrieval traces
- briefs
- eval summaries

The intended production upgrade is PostgreSQL plus pgvector:

- relational tables for workspaces, sources, chunks, answers, and model/eval runs
- `vector` column on chunks
- GIN indexes for keyword retrieval
- vector indexes for semantic retrieval

## RAG Contract

The frontend does not know whether retrieval uses local embeddings, pgvector, Qdrant, or hosted embeddings. It depends only on these backend contracts:

- create workspace
- ingest evidence
- list sources
- ask question
- extract and list evidence rows
- inspect retrievals
- generate brief
- view evals

## Safety Positioning

TrialLens is not a diagnosis or treatment recommender. It separates evidence source types and explicitly labels FDA adverse events as reports rather than proof of causality.
