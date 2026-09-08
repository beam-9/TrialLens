# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are biomedical researchers, evidence reviewers, and technically informed analysts working on a desktop research workflow. They need to gather public evidence for a condition, drug, or intervention, inspect what each source actually supports, and synthesize findings without losing source provenance.

## Product Purpose

TrialLens is a biomedical evidence navigation workspace. It creates a research workspace, ingests public biomedical sources, extracts source-level evidence fields, supports citation-grounded questions, exposes retrieved passages, and generates a structured evidence brief. Success means a user can move from a research topic to inspectable, cited evidence while retaining visibility into uncertainty and source limits.

## Positioning

TrialLens uses an extraction-first workflow: sources become reviewable evidence rows before model synthesis. The interface keeps supporting passages, citations, source types, confidence, review status, and limitations visible instead of presenting an answer as an opaque chat response.

## Operating Context

Users work across PubMed records, ClinicalTrials.gov records, FDA labels, and FDA adverse-event style records. The core workflow is to create or reopen a workspace, retrieve sources, inspect extracted evidence, filter and review rows, ask a question across the workspace or a document, inspect citations, and generate or review an evidence brief and reliability report.

## Capabilities and Constraints

- Create and reopen workspaces for a condition and optional intervention.
- Retrieve, normalize, and inspect public biomedical sources.
- Extract population, intervention, comparator, outcome, safety, supporting quote, methods, findings, limitations, confidence, and review status.
- Filter evidence by source type, review state, and presence of quantitative results.
- Mark extraction rows as reviewed or needing review.
- Ask citation-grounded questions across a workspace or a selected document.
- Generate a structured brief and inspect a static reliability report.
- Remain usable with deterministic sample fallbacks when public APIs are unavailable or rate-limited.
- This is an evidence navigation tool, not medical advice or clinical decision support.
- Preserve existing route anchors, API contracts, field names, and medical-scope language during the redesign.

## Brand Commitments

The product name is TrialLens. The voice is direct, sober, source-aware, and explicit about uncertainty. The redesign brief commits the product to a minimal, clean, sharp, flowing, polymorphic visual direction while preserving functional clarity.

## Evidence on Hand

- Product and scope description in `README.md`.
- Existing end-to-end workflow in `apps/web/app/page.tsx`.
- Typed frontend API contract in `apps/web/lib/api.ts`.
- Backend models and endpoints in `apps/api/triallens/models.py` and `apps/api/triallens/main.py`.
- Deterministic sample evidence in `apps/api/triallens/sample_data.py`.
- No testimonials, customer logos, commercial benchmarks, or outcome claims are available and none should be fabricated.

## Product Principles

1. Show the evidence before the synthesis.
2. Keep every claim traceable to inspectable source material.
3. Make uncertainty and review state visible and actionable.
4. Prefer clear research workflows over conversational novelty.
5. Preserve usefulness when external evidence services are unavailable.

## Accessibility & Inclusion

The web interface must support keyboard operation, visible focus, semantic controls, readable contrast, reduced motion, and responsive layouts. Medical and evidence terminology must remain explicit rather than relying on color or visual metaphor alone.
