# Browser functionality evaluation — 2026-10-22

The current production build passed **13 browser regression tests** (18.6 seconds), including three new tests that exercise the complete UI → Next.js proxy → FastAPI → temporary JSON store path. A separate real upstream-shutdown check passed. Lint and TypeScript checks also passed after the new tests were added. No aesthetic changes were made by this evaluation.

## Isolation and evidence

All browser mutations used `http://127.0.0.1:3002`, whose server was explicitly configured with `TRIALLENS_API_BASE=http://127.0.0.1:8002`. The API used hash-checked M0 frozen fixtures and its own temporary data file and usage ledger. Source fetching was replaced with deterministic fixture ingestion. Generation returned purpose-labelled deterministic JSON through the existing validation path; outbound provider HTTP was blocked. No `.env` file, live Cloudflare call, Ollama inference, OpenAI call, or production workspace mutation was used by this browser audit.

The existing ten tests include browser-route mocks for rendering/failure/allowance behavior. The new three tests avoid browser mocks and use the actual proxy/API/store, with only the external source/provider seams replaced. Therefore these results establish plumbing and persistence, **not model answer accuracy or live upstream availability**.

Machine-readable evidence: [functional-browser-2026-10-22-results.json](functional-browser-2026-10-22-results.json).

## Verified functionality

| Area | Evidence and result |
|---|---|
| Workspace validation | Whitespace and one-character conditions disable Build. Condition required/max 120, intervention max 120, question max 500; Ask disabled before evidence exists. |
| Create and ingest | Actual UI form creates workspace, calls API ingestion, displays two fixture sources and two extraction rows; API response/persisted source count checked. |
| Evidence filters | Literature, review state and quantitative toggles work; combined reviewed/unreviewed filters produce the expected rows/empty state. |
| Evidence inspection | Supporting quote and source citation displayed in sheet; mark reviewed persists through PATCH and reload; Escape closes sheet. |
| Source explorer | Current indexed source records displayed; existing answer tests verify citation and original-source link rendering. Synthetic fixture records intentionally have no original URL. |
| Ask and citations | Actual API generated-answer validation accepts stub output, returns only selected-source citations/retrieved passages and displays its labelled response. |
| Conversation | Follow-up records previous-answer ID and source scope; reload restores history; Continue selects previous conversation scope. Changing source family starts a new chain with null previous ID. New conversation clears active answer and composer. |
| Safety and clarification | Personal medication decision returns clinician-oriented guard with explicit no-generation note. Ambiguous “the other one” comparison requests clarification without generation. These deterministic guards are labelled conversational by the existing response schema. |
| Brief | Empty export disabled; saving a real API answer displays it; downloaded Markdown contains question, citation and evidence gaps; reload retains saved answer; removing it persists and disables export again. |
| Navigation and persistence | All five evidence views, newest-workspace cache merge, light/dark persistence and responsive tab keyboard navigation pass existing regressions. |
| Mobile viewport | Existing 390×844 viewport test passes: no page overflow, evidence table horizontal scrolling and usable theme control. This is emulation, not physical-device coverage. |
| Failures and quota UI | Existing regressions cover retryable Ask failure, input preservation, Cloudflare identification, 100-answer alert, exhausted allowance and excerpt follow-ups. |
| Actual proxy outage | After stopping fixture API, creating a workspace produces Next proxy 502 and a focused actionable error; condition stays intact and Build is re-enabled. Separate `/api/health` request confirms 502. |
| Reliability view | Existing navigation test displays Reliability scenario checks and metrics. It does not independently validate those static metric claims. |

## Reproduce

Use three separate terminals from the repository root. The fixture server terminates and cleans up its temporary files on Ctrl-C; keep it running until the browser suite finishes.

```sh
apps/api/.venv/bin/python apps/api/evaluation/functional_fixture_server.py
```

```sh
cd apps/web
TRIALLENS_API_BASE=http://127.0.0.1:8002 npm run start -- --port 3002
```

```sh
cd apps/web
TRIALLENS_FUNCTIONAL_TESTS=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3002 npm run test:e2e
```

The frontend requires a current `npm run build` beforehand. These checks used that fresh build. Without `TRIALLENS_FUNCTIONAL_TESTS=1`, the three integration tests skip because an ordinary developer API is not a safe destination for fixture mutations. During this audit browser execution was launched through the Expect Playwright tool.

## Remaining limits and deployment risks

- The earlier Cloudflare quality evaluation remains applicable. Deterministic integration responses cannot resolve or remeasure its partially supported answers; a fresh source-backed quality pass is still needed after answer-quality changes.
- Live PubMed, ClinicalTrials.gov and FDA availability, real ingestion latency, current Cloudflare quota/failure behavior and production network conditions were not exercised here. Backend tests cover relevant parsing and failure contracts separately.
- Authentication, tenant isolation, internet exposure, backup/restore, production persistence and sustained concurrent load are outside this browser run. Passing local regression tests is not deployment approval.
- The Reliability view is reachable, but displayed metric accuracy needs the separate code/data audit; this browser test checks rendering only.
- Desktop Chromium and one mobile viewport do not replace Safari/Firefox, real touch-device or assistive-technology testing.

The minor enabled-button/whitespace issue observed on the initial build was fixed by the parent task and verified on the fresh build. No unresolved browser failure remained in this test scope. Functional and scientific correctness work should precede visual redesign.
