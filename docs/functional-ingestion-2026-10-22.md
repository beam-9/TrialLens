# Source ingestion functional audit — 2026-10-22

This audit uses public research queries and temporary stores only. No user research workspace, patient information, inference provider, or paid service was used. Provider credentials were not read or printed. No design or query-ranking changes were made.

## Live connector checks

An isolated `Workspace(condition="type 2 diabetes", intervention="metformin", source_types=list(SourceType))` was passed through the production `fetch_sources` function. The first run completed in 2.133 seconds; a repeat captured in [public connector metadata](functional-results/public-source-connectors-2026-10-22.json) completed in 1.686 seconds. Both returned all four providers as `available`, with 14 source records. These times are individual observations, not a performance benchmark or availability guarantee.

| Connector | Returned | Identity / usable field checks | Scope and freshness limits |
|---|---:|---|---|
| PubMed | 5 abstracts | Real PMIDs and PubMed links; title, abstract text, named sections and publication year populated | Limited to five search hits; abstracts only; publication year rather than full publication date; recent hits include combination/alternative treatments |
| ClinicalTrials.gov | 5 protocols | Stable NCT IDs and study links; all five `COMPLETED`, phases populated; brief/detailed descriptions | Protocol descriptions only, no posted outcome tables; no source publication/update dates captured; broad `query.term` admits healthy-participant, pregnancy, pediatric obesity and prevention studies |
| FDA labels | 3 labels | Stable record IDs, encoded record-specific API links, effective dates, ingredient/brand metadata; indication, boxed warning, contraindication, warnings, adverse reaction, interaction and clinical-study sections | First three results, no explicit latest-label sort; ZITUVIMET combination label accompanies two metformin labels; label revisions have distinct record IDs |
| FDA adverse events | 1 aggregate | Query-specific endpoint URL and drug-specific identity; top five reported reaction counts; explicit no-causality/no-incidence caveat | Aggregate spontaneous reports, not trial outcomes or incidence; no query date window or upstream freshness date attached |

The ClinicalTrials results were NCT02077803, NCT00835861, NCT02515773, NCT00282451 and NCT03766256. Completed study status is not evidence that posted results were indexed. The live set includes real contextual breadth and should not be described as a comprehensive intervention-specific evidence review.

A separate deliberately nonexistent term, `zztriallensnomatch739241`, returned zero records in 0.873 seconds and `no_matches` for every connector. openFDA's documented-shaped 404 `NOT_FOUND` response is distinguished from a service outage by deterministic tests. No live outage occurred during this audit; HTTP503/outage behavior was tested with a mock transport rather than inducing upstream failures.

## Reproduced and fixed refresh defects

1. **Partial-provider failure deleted existing evidence.** A temporary workspace with an existing ClinicalTrials source and researcher-reviewed extraction was refreshed while PubMed succeeded and ClinicalTrials reported unavailable. The old implementation deleted the failed provider's source. The new regression first failed with actual IDs `{'new-paper'}` instead of `{'NCT-existing', 'new-paper'}`. The small ingestion fix keeps unavailable selected providers' exact previous sources and chunks, including extraction IDs and researcher corrections. Successful providers still replace their own previous results. The workspace remains `partial`; an explicit warning says previously indexed evidence was kept and may be outdated. A reopened `JsonStore` verifies persisted records, review state and warning status.
2. **Date/URL-only updates left stale extraction provenance.** An unchanged title/abstract with a new publication date and source URL previously retained the old extraction date/URL and reviewed status. A second regression failed (`2024` instead of `2025`). Refresh equality now includes publication date and URL, so changed provenance rebuilds an unreviewed extraction with current source information while preserving the stable source ID. Truly unchanged evidence continues to preserve researcher corrections, covered by the existing test.

All-empty refresh behavior remains conservative: when existing evidence exists and every fetch returns empty, HTTP409 reports that evidence was kept. No synthetic/demo evidence is manufactured. A successful `no_matches` for one provider during an otherwise successful refresh is still treated as that provider's current empty result; the stale retention rule is specifically for unavailable providers.

## Verification

Command: `apps/api/.venv/bin/pytest apps/api/tests/test_ingestion_integrity.py apps/api/tests/test_sources.py apps/api/tests/test_api.py -q`

Result: **12 passed**, including stable FDA identity/provenance and safety sections; inline PubMed markup; no-match/outage distinction; no synthetic records; all-empty evidence retention; unchanged-source review preservation; partial coverage warning persistence; and both new refresh regressions. No model calls were required.

## Remaining limitations and recommendations

- Query relevance, result caps, missing ClinicalTrials result tables/dates and FDA latest-revision policy remain unchanged. Address these as explicit product/data-scope work, with realistic parser fixtures and source-backed QA, rather than silently widening or narrowing this audit.
- Provider failures are represented as a generic `unavailable` state; parser changes, transport timeouts and upstream errors are not differentiated in user-visible diagnostics. This audit did not observe an actual live provider failure.
- Refresh is sequential, bounded by per-provider HTTP timeouts, and is not a comprehensive or continuous monitoring service. No concurrency architecture changes were attempted.
- Retained evidence is explicitly stale on provider failure. All-empty HTTP409 leaves the prior workspace state unchanged; the request error explains preservation but does not persist a fresh last-attempt timestamp.
- Source publication/effective dates and retrieval timestamps have different meanings. Existing schema does not provide uniform upstream last-updated timestamps; do not claim current/comprehensive coverage from a successful fetch alone.
