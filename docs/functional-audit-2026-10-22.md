# TrialLens functionality audit — 22 October 2026

**Scope:** evaluate current functionality before any design/aesthetic iteration. Starting commit `bd3f70d`. The four source connectors were queried with bounded generic public research topics; application mutations and generated test answers used isolated stores/ledgers and deterministic provider stubs. No additional Cloudflare, Ollama or OpenAI model inference was required. Existing research/workspace data and unrelated local research files were not edited.

This is a scoped functional audit, not proof of biomedical accuracy, a comprehensive security assessment, or deployment-host verification. The active research app remains a shared local installation. No public deployment or aesthetic redesign was performed.

## Workflow assessment

| Function | Evidence / result | Limitation |
|---|---|---|
| Create workspace / input validation | Trimmed condition and optional intervention validated before persistence; blank/too-short topics and questions rejected; browser input limits match API bounds. | Existing stored records are not migrated or deleted. |
| Live evidence ingestion | All four connectors succeeded: 5 PubMed, 5 registry records, 3 labels and 1 adverse-event aggregate. A nonexistent query yielded zero records and `no_matches` for all services. | Bounded sample, not an uptime/relevance benchmark or systematic review. |
| Empty/outage refresh | All-empty refresh keeps prior evidence with HTTP409; partial outage now keeps failed services' sources/chunks/reviewed rows and explicitly warns they may be outdated. | No automatic monitoring or uniform last-attempt/freshness timeline. |
| Source identity / provenance refresh | Unchanged sources keep identity and review state; URL/date changes now rebuild current extraction provenance and require review again. | FDA latest-revision policy and historical-source versioning remain limited. |
| Extraction / researcher corrections | Re-extraction refreshes derived fields while preserving saved editable fields, row identity and review status, including unreviewed corrections. | No per-field edit provenance: unchanged stored rows retain all editable values conservatively. |
| Evidence table / filters / inspection | Source/review/quantitative filtering, source inspection, original-source links and review controls covered by API and browser checks. | Heuristic extraction/quantitative flags are not calibrated accuracy scores. |
| Ask / follow-ups | Source-scope history, document boundaries, missing evidence and guards checked through real API with deterministic generation; latest live hosted suite already retained 18 outputs. | Latest semantic review remains 9 supported / 9 partially supported; population/comparator/timeframe omissions remain. |
| Source scope changes | `null` (all) and `[]` (none) now remain distinct; invalid history transitions reject with HTTP400. | Document-scoped Ask is an API capability; the current composer calls workspace mode, so a dedicated document-chat UI is absent. |
| Citation grounding / boundaries | Unknown IDs, malformed citation lists, copied passages and incomplete outputs rejected; no failed draft or automatic alternate-provider generation displayed. | Citation syntax cannot prove entailment. Ancillary notes can contradict the final citation list (below). |
| Source truncation metadata | Full text retained through deduplication now reports no truncation; genuine prefix/passage/budget cuts still report truncation. | Character budgeting is not a token guarantee; partial source types remain explicitly scoped. |
| Brief | Save/remove, current review counts, saved-answer membership and historical-source warnings checked. It serves selected research notes rather than duplicating first abstracts. | Saved answers are historical snapshots; sharing requires source inspection. |
| Persistence / restart | Temporary-store reopen preserves answers, exact retrieved provenance, review corrections and Brief membership. Existing tests cover atomic writes and cross-instance serialization. | Does not establish a deployment-host backup/restore or transaction isolation across large overlapping workflows. |
| Usage / free inference | Two-pass accounting, 100-answer alert, persistent atomic Cloudflare daily guard, missing-usage holds and error/busy paths covered. | Free-plan confirmation is operator attestation; local ledger cannot see other apps' account-wide usage. |
| UI recovery / navigation | Existing browser suite covers recovery, scopes, desktop/mobile, keyboard navigation and evidence boundaries; expanded integrated workflow verification recorded below. | No complete WCAG certification or exhaustive browser/device matrix. |
| Reliability view | Static development targets remain labeled illustrative/unmeasured. | They are not measured answer accuracy or current workspace scores. |
| Hosting / access | Both Compose profiles validate; hosted profile avoids Ollama. Same-origin proxy remains server-configured and forwards error responses. | No accounts/workspace ownership, authenticated remote access, actual container startup or host restoration verified. |

## Confirmed defects fixed

1. **Partial refresh could delete old evidence from an unavailable connector.** Reproduced with a successful PubMed refresh and failed registry fetch. Failed connector data, stable IDs, chunks and researcher reviews now survive, with a stale-evidence warning.
2. **Date/URL-only source updates could retain stale extraction provenance.** Freshness comparison now includes those source fields; changed provenance rebuilds an unreviewed extraction.
3. **Re-extraction erased saved review status and researcher corrections.** Existing source-linked editable values and identities are retained while generated detail fields refresh.
4. **Follow-ups could cross all-sources/no-sources scope.** `None` and `[]` no longer collapse to the same history scope.
5. **Whitespace-only topics/questions passed length checks.** Inputs now trim before validation, with empty optional interventions normalized to null. Browser blocks invalid trimmed topics and bounds topic/intervention/question lengths.
6. **Deduplication falsely marked complete source content truncated.** The flag now measures loss before duplicate passages are removed.

Every change has deterministic regression evidence; failing cases were reproduced before fixes. No prompt wording, source selection policy, model, context budget, generation strategy or billable fallback was changed. Correcting truncation metadata can change future generated caveats; the retained live outputs precede this metadata correction and were not silently relabeled as post-fix evaluations.

## Outstanding functional and trust issues, before design work

### P1: required evidence qualifiers are still omitted

The retained [Cloudflare evaluation](performance/cloudflare-first.md) completes requests quickly, but nine answers were partial. Add-on comparisons can lose the comparator percentage, 24-week window, adult population or background treatment. Numerical simplification can repeat the original nearly verbatim. These require controlled source-backed answer-quality work, not visual polish. Independent expert review is still pending. Do not equate the absence of critical invented assertions in one small run with a safe quality promotion.

### P2: expanded provenance notes can misdescribe generated answers

A deterministic real-API replay of the frozen metformin workspace produced no final citations while the earlier extractive `source_readouts` still contained three `CITED` labels, including an excluded combination product. The actual generation context and final citation allow-list correctly excluded that product, but the UI renders these notes under “Source matching notes.” Some supporting/reasoning/quality fields also describe the extractive fallback rather than the accepted generated response.

This audit leaves that broader provenance contract unchanged rather than silently deleting evidence fields. Reconcile the notes with final answer citations or explicitly label them as retrieval-stage context, then verify source-filtered, combination-product and abstention cases before design changes. Do not call them final-answer verification in their current form.

### P2: evidence coverage and relevance remain bounded

The live registry query included healthy bioequivalence, pregnancy and pediatric prevention records alongside the requested type-2-diabetes topic. The search uses broad term relevance and indexes protocol descriptions, not posted structured results. PubMed is generally abstract-only; labels are regulatory evidence; FAERS aggregate reports establish neither incidence nor causality. Result caps and incomplete/freshness metadata must remain visible. More records alone are not an accuracy fix.

### Release gates remain unverified

Hosted inference removes the need for native GPU model execution, but does not add authentication or ownership. Remote use needs a chosen hosting environment, access protection for the entire site including `/api`, persistent storage and a verified backup/restore. Container configuration validation is not runtime proof. Local Python is still 3.9.6 despite the declared >=3.11 requirement; supported-runtime verification remains outstanding. No Docker daemon was started just to run this audit.

## Verification

- **167 backend tests passed**, with two upstream websockets deprecation warnings.
- ESLint, TypeScript and production build passed after the functional form changes.
- Both `docker compose config --quiet` and the standalone Cloudflare profile configuration check passed.
- Live generic ingestion and no-match checks: four providers exercised; public metadata retained under [functional results](functional-results/public-source-connectors-2026-10-22.json).
- No new live model calls; the separately retained 18-case hosted semantic evaluation remains the live answer-quality evidence.
- **13/13 production-browser regressions passed** in 18.6 seconds (ten existing plus three new integrated flows). `TRIALLENS_FUNCTIONAL_TESTS=1` enables the fixture-only tests; they skip by default to prevent accidental mutations against an ordinary API.
- Actual fixture-API shutdown returned proxy HTTP502; browser showed a focused actionable error, retained input and enabled retry. Brief Markdown download, citations, caveats, save/remove and reload were exercised through the actual proxy/API/store.
- The isolated fixture API/frontend and temporary data were cleaned up. The actual local API and website were restarted with the tested changes and Cloudflare still selected; no inference was needed for restart readiness.

Detailed evidence: [backend audit](functional-backend-2026-10-22.md), [ingestion audit](functional-ingestion-2026-10-22.md), [browser audit](functional-browser-2026-10-22.md) and [browser results](functional-browser-2026-10-22-results.json). Test fixtures and reports contain public/synthetic material, not credentials, private research histories or patient records.

## Recommended order

1. Reconcile generated-answer provenance notes and preserve required population/comparator/time qualifiers; rerun affected frozen cases and source-filtered follow-ups.
2. Finish a repeatable source-backed quality comparison and decide the trusted pilot's exact data/access scope; keep broad registry relevance and posted-results limitations explicit.
3. Only then iterate on design/aesthetics; after that, verify the selected hosting environment, persistence, access and restore/failure paths before inviting users.
