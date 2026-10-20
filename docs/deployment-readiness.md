# TrialLens deployment readiness

Assessment date: 20 October 2026. Scope: source/API review, isolated backend tests, real public-source ingestion, local-model integration and deployment configuration. Browser/design and live-model semantic reviews are tracked separately. This is a readiness assessment, not a claim of clinical validation.

## Completion assessment

TrialLens has a working research-prototype workflow: create a workspace, ingest public records, inspect extraction rows and citations, ask questions with source-scoped follow-ups, save selected answers into a brief, and export it. It has progressed beyond a visual mockup. The main remaining work is the trustworthiness and operation of that workflow under realistic inputs and deployment conditions.

A private pilot for a small trusted group is the next appropriate release. An anonymous public multiuser service is a separate milestone: the current API has no account or workspace ownership boundary, and the local model runs on the API machine. Publishing only the Next.js frontend will not provide working chat to visitors. A numerical completion percentage would obscure these distinct release targets.

## Evidence collected

- `cd apps/api && .venv/bin/python -m pytest tests -q`: **67 passed in 0.94 seconds** after the implementation iteration, including concurrency, no-synthetic-fallback, FDA provenance, inline XML text, empty-refresh and identical-source refresh regressions. These are contract/regression tests; mocked generation does not establish real answer accuracy.
- `cd apps/api && .venv/bin/python run.py --check`: selected `ollama`, `qwen3.5:9b`, configuration ready. This checks settings, not model readiness.
- Fresh public-source ingestion into an in-memory, unsaved workspace for `type 2 diabetes` / `metformin`: **4 PubMed abstracts, 5 ClinicalTrials.gov summaries, 3 label records and 1 adverse-event aggregate**, completed in approximately 7.5 seconds. No local or paid model request was made.
- PubMed and trial records had record-specific source links. All three FDA labels used positional identifiers (`FDA-LABEL-metformin-1`, etc.) and linked to API documentation. The first label was a combination product, ZITUVIMET; subsequent records were standalone metformin labels. Accurate answers must preserve this distinction.
- The small query result set included a gastric ischemia case report, a high-fiber diet study and registry studies of other drugs or add-on treatments. Search matches are not automatically relevant efficacy evidence and do not constitute a systematic review.
- An isolated concurrency harness drove two real `JsonStore.create_workspace` calls through the same read-modify-write seam. Both returned successfully; only **1 of 2** records remained. The test deliberately synchronized reads and even serialized final writes, showing that atomic file replacement alone cannot prevent lost updates. No user data was touched.
- With all upstream clients mocked to return zero records, `fetch_sources` returned **4 synthetic records**. Their IDs contained `DEMO`; none had `metadata.demo=True`. Normal ingestion would report these as ingested. Generation later adds a demo warning, but this does not make the source discovery step truthful. This happens for a legitimate zero-result query as well as an outage.

The implementation iteration fixed those baseline defects: each whole read-modify-write mutation now holds a process file lock, writes publish an fsynced complete temporary snapshot with atomic replacement, and a concurrent-instance regression preserves all 8 workspaces. Normal ingestion returns zero real records instead of synthetic records. An empty refresh of an existing workspace returns a conflict and preserves its current evidence. These regressions pass in the test run above. Identical-source refresh also preserves its source identity and reviewed extraction state, covered by an API regression.

A fresh FDA-only call after the fix returned three stable UUID-based external IDs, each with an exact `api.fda.gov/drug/label.json?search=id...` record link, plus label/set identifiers in metadata. An inline XML fixture through the actual PubMed parser preserved the complete title, numeric effect and trailing text. Existing workspaces retain their earlier source snapshots until refreshed; historical positional FDA IDs are not retroactively repaired.

## Release gates

| Area | State at audit | Required for trusted private pilot | Additional requirement for public multiuser release |
| --- | --- | --- | --- |
| Core workspace / brief contracts | Implemented; automated tests pass | Browser smoke test of create, ingest, inspect, follow-up, save/remove and export on the final build | Same tests under user isolation |
| Conversational quality | Real model connected; semantic evaluation still needs final adjudication | Review open-ended, numerical, contradictory, absent-evidence and follow-up answers against sources; retain failures | Broader independently adjudicated evaluation, monitoring and model/version regression gates |
| Evidence discovery | Live services work; synthetic fallback removed; coverage warnings persist; empty refresh preserves prior data | No-fabrication and empty-refresh regressions pass; persisted partial-source failure warnings distinguish outages from genuine no matches | Observable source-service failures, request controls and operational monitoring |
| Source provenance | New FDA ingestion now keeps stable IDs and exact API record links | Provenance regression and fresh live call pass; refresh old positional-ID workspaces; label aggregates clearly | Versioned source snapshots and traceable refresh history |
| Persistence | Process mutation lock and atomic snapshot writes implemented; concurrency regression passes | Keep persistent volume; test restore and refresh/answer concurrency on host; database still preferable as scope grows | Ownership-aware transactional database, migrations, backups and retention policy |
| Access | Shared API; no authentication | Keep loopback-only, or protect the whole site and API behind a trusted private-network/access gateway | Authentication, per-user/organization authorization and workspace ownership checks |
| Inference hosting | Fixed loopback Ollama on API host | API and Ollama must run on the same persistent compute host; benchmark that host | Provision capacity, bounded queue/admission control, per-user limits and abuse controls |
| Browser/API routing | Same-origin proxy verified in production build; configurable exact CORS origins; private Compose topology provided | Local production same-origin proxy and build pass; configure the host HTTPS/access gateway | Production routing/config validation and service monitoring |
| Usage | Persistent SQLite counter/cap implemented | Preserve ledger volume; verify 100-answer alert and zero-cost local counting | Installation/account-wide accounting policy across replicas |
| Build and operation | Private-pilot Dockerfiles/Compose and operating guide added; no CI release workflow | Production build, production server, process supervisor/restart, readiness check, backup/restore and rollback instructions | Automated release pipeline and staging checks |

## Recommended small-scale architecture

Start with one trusted private deployment on one machine that can run the selected local model. Serve Next.js and FastAPI behind one HTTPS reverse proxy/access gateway. Keep FastAPI and Ollama bound to loopback; route browser API requests through the proxy. Protect the entire application and API with the same access boundary. A frontend-only login does not protect API endpoints. Keep the inference port private.

Run the API and Ollama on the same host because the application currently calls `127.0.0.1:11434`. Do not put Ollama in a separate container or host without implementing and validating that topology. Do not expose the developer Mac directly to the public internet to make a hosted frontend work. A developer Mac can support a private local pilot while a permanent inference host is decided.

Use a persistent, backed-up location for both workspace storage and `usage.sqlite3`. The JSON store currently uses a source-relative path, while the usage ledger has a `TRIALLENS_USAGE_PATH` override. A deployment must preserve both. A single API worker does not eliminate request concurrency: synchronous FastAPI endpoints can run concurrently in its threadpool.

Local generation avoids per-token API billing, but hosted compute is a separate cost. The 100-answer threshold is an alert, not a rate limit or concurrency limit. Two-pass generation can spend several minutes across two requests, each with a 180-second timeout. Align proxy/request timeouts with measured behavior, show useful progress and control admission rather than allowing unbounded requests to queue behind one model.

## Grounding and product limits to preserve

- Citations validate source identifiers and structure. They do not prove that adjacent claims follow from the source.
- The local model drafts and revises against evidence; both passes use the same model. This is a mitigation, not independent fact-checking.
- Indexed material is mostly abstracts and registry descriptions. Registry ingestion currently reads protocol descriptions, not posted results tables. The app must not promise full-paper or complete trial-results coverage.
- Source retrieval caps currently request 5 PubMed matches, 5 registry studies and 3 labels; generation considers at most 8 selected sources with bounded text/history. Answers must say what the indexed evidence supports, without implying exhaustive literature coverage.
- Upstream source queries leave the host for public research APIs. Local generation alone does not make the entire workflow offline. Workspaces should not contain identifiable patient data in this pilot.
- Model failure or validation failure produces a labeled extractive answer and never silently switches to paid generation. Keep this visible distinction.
- The reliability endpoint contains static development targets. They must remain identified as unmeasured targets, including in API-facing documentation.
- Identical-source refresh preserves source identity and reviewed extraction state. Changed source content still requires renewed review; saved answers remain historical snapshots rather than regenerated conclusions. A public release should preserve traceable source/review versions.

## Final pilot acceptance checklist

- [x] Final code passes 67 backend tests, ESLint, TypeScript and a clean-install production build; build-time font access is understood.
- [x] Final production browser suite passes 8/8 regressions; manual checks cover desktop/mobile, source scope, real follow-ups, Inspect/Escape and Brief save/export/remove. Real semantic failures are retained separately.
- [ ] Final local-model evaluation is adjudicated against actual evidence; any unresolved factual error is recorded and handled before widening access.
- [x] Empty/outage ingestion cannot manufacture synthetic research records; empty refresh preserves existing data.
- [x] Partial upstream failures are persisted and visible separately from genuine zero matches; FDA NOT_FOUND searches remain no-match results.
- [x] Concurrent-instance workspace saves preserve all records; atomic replacement publishes complete JSON snapshots.
- [ ] Backup/restore and larger overlapping workflows are exercised on the deployment host.
- [ ] Deployment host and access scope are chosen; browser API requests reach its HTTPS API, which reaches its own local model.
- [ ] Real inference readiness is checked after restart; `/health` alone is insufficient because it only checks configuration.
- [ ] Persistent workspace and usage data survive a restart; a backup is restored successfully.
- [ ] Admission/concurrency behavior and a slow-model/error path are tested on the actual host.
- [x] Rollback/restart steps are documented and runtime data/credentials are excluded from Git and image build contexts; procedures still need host verification.

## Private deployment artifacts

`compose.yaml`, `deploy/api.Dockerfile`, `deploy/web.Dockerfile` and `.dockerignore` package a private stack. Only the web port is published, bound to 127.0.0.1:3001; API and inference share a network namespace so the fixed local-inference boundary remains valid. Persistent volumes hold workspace/usage data and model downloads. See `private-pilot.md` for provisioning, readiness, access protection, backup/restore and rollback steps.

`docker compose config --quiet` passes. The Ollama 0.32.14 image manifest exists for Linux amd64 and arm64. The Docker daemon is not running, so image builds, container startup, actual model provisioning/performance and backup/restore remain unverified. This is a concrete deployment package, not a running deployment.

No production deployment was performed by this audit. Application changes and subsequent checks can close the listed gates; update their status with evidence rather than treating the checklist itself as completed work.


## Dependency and tooling check

The obsolete `next lint` command was reproduced failing and replaced with configured ESLint plus an explicit typecheck script. Next.js/React/PostCSS were updated, nonbreaking transitive patches applied, and the unused shadcn generator removed from deployed dependencies. A clean `npm ci` and production build pass on Next.js 16.4.2 / React 19.3.1. `npm audit --omit=dev` reports **zero advisories** at this check; this is not a complete security assessment.

The full audit still reports **9 build/lint-toolchain advisories** (7 high, 2 moderate), involving Tailwind 3 glob/selector parsing and the Next ESLint plugin's transitive glob dependencies. These dev dependencies are pruned from the production web image. Do not feed untrusted projects/styles into the build toolchain. A Tailwind 4 migration and upstream tooling updates are separate work; no forced major migration or unsupported dependency override was applied to hide the findings. ESLint 9 is retained for compatibility with Next's React/import/accessibility plugin peer ranges; its deprecation is tracked as tooling debt.
