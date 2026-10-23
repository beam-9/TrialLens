# Browser functionality verification — 2026-10-23

The existing production browser suite passed **13 of 13 tests in 15.2 seconds**, with no retries. The frontend build was unchanged from the previous functional audit; the fixture API loaded the current backend, including attribution reconciliation and the numerical fallback repair. This run verifies application behavior and rendering, not generated-answer accuracy.

## Isolation

The browser used `http://127.0.0.1:3002`, whose separate production server was explicitly configured with `TRIALLENS_API_BASE=http://127.0.0.1:8002`. The fixture server used an isolated temporary JSON store and usage database, hash-checked M0 frozen fixtures, deterministic source ingestion, and a purpose-labelled stub completion. Outbound inference HTTP was blocked. No production workspace was changed, no `.env` was loaded, and no Cloudflare, OpenAI or local model call ran.

## Existing regression coverage

The three integration tests exercised actual UI → Next proxy → FastAPI → temporary store behavior: input bounds, create/ingest, evidence filters, source inspection, persisted review state, scoped question and follow-up attribution, conversation restoration and reset, treatment/ambiguity guards, save/remove brief answers and Markdown download. The ten established rendering regressions covered every view, theme persistence, mobile overflow and table scrolling, responsive keyboard tab navigation, recoverable Ask failure, newest-workspace selection, fallback evidence boundary, Cloudflare identification, the 100-answer alert and exhausted-allowance behavior. Their route-mocked cases verify those interface contracts without validating a live provider.

## Additional provenance inspection

A separate Playwright CLI inspection reopened the temporary integration workspace and requested one deterministic stub answer across both source families. Generation received two source records and cited only the publication. The expanded real interface showed:

- `CITED IN ANSWER · PubMed:EVAL-FILTER-PUBLICATION` for the final attributed source.
- `CONTEXT ONLY · ClinicalTrials.gov:EVAL-FILTER-PROTOCOL` for the uncited selected context.
- A generation-context trace of two records, separately from final attribution of one citation.
- An explicit warning that citation checks verify supplied source names, not independent support for each claim.
- An explicit note that context-only records and retrieval match scores do not establish support for the final answer.
- Only the publication under “Sources cited in this answer”; the protocol did not receive a final-citation label.

This confirms the new provenance fields reach the rendered UI without stale extractive citation judgments. Screenshot: [functional-provenance-2026-10-23.png](../output/playwright/functional-provenance-2026-10-23.png).

## Narrow UI findings retained for the design stage

The supporting-evidence disclosure still says “0 items” after the reconciliation intentionally clears extractive supporting arrays, despite containing safety/uncertainty details. “How this answer was built” counts trace/quality/reasoning entries as “5 checks”; that label overstates the nature of these explanatory notes. These are presentation issues to resolve once the answer-quality gate permits UI work. The only observed console error was an existing missing `/favicon.ico` request.

## Reproduction

Start these separately from the repository root, with an existing frontend production build:

```sh
apps/api/.venv/bin/python apps/api/evaluation/functional_fixture_server.py
```

```sh
cd apps/web
TRIALLENS_API_BASE=http://127.0.0.1:8002 npm run start -- --hostname 127.0.0.1 --port 3002
```

```sh
cd apps/web
TRIALLENS_FUNCTIONAL_TESTS=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3002 npm run test:e2e
```

## Limits

The run does not establish clinical correctness, hosted inference quality, live source availability, public deployment readiness, authentication/ownership isolation, production load behavior, Safari/Firefox compatibility or real assistive-technology coverage. Answer quality remains subject to the independent source-backed evaluation. No aesthetic changes were made during this verification.
