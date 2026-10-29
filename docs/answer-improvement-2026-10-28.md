# Answer coverage implementation — 28 October 2026

## Retained production change

Conversation context now selects up to eight eligible sources in retrieved-passage order, then fills any spare slots in stable input order. Previously, the first eight source records were selected even when retrieval found a relevant passage in a later source. The same citation/source identity check controls admission and passage attachment. Product scope and source-type filtering remain upstream. Both generation passes receive the same bounded evidence records.

The existing 28,000-character **source-text** budget is retained; it does not include instructions, metadata or history. No model, token limit, generation strategy, production instruction text, citation/copy checks, provider fallback or free-plan quota was changed.

## Milestone results

| Stage | Implementation and evidence |
| --- | --- |
| 1. Benchmark | Fourteen authored synthetic controls, partitioned into nine development / five holdout cases before comparison. Required facts map to exact source passages; forbidden interpretations and manual semantic rubrics remain separate. New hosted questions reuse unchanged hash-checked M0 snapshots. |
| 2. Context selection | Implemented and retained. Corrected offline comparison: development 19/19 required passages before and after; holdout 8/10 before, 10/10 after. The gain is the source at input position nine. These are context-membership measurements, not generated-answer accuracy. |
| 3. Complete numerical records | Conservative parser prototype tested but deliberately isolated under evaluation, not imported by ingestion. A real NCT01563029 payload had eight outcomes; all were omitted at the complete-outcome 1,200-character limit. Simply indexing this prototype would not solve missing statistics. Ordinary 92-word chunking can also detach values from their groups/timeframes. Atomic numerical context packaging is still required. |
| 4–5. Adaptive depth / coverage-preserving revision | Two instruction candidates were frozen in commits before model calls and tested using the same broad question, explicit statistics question, and simplification follow-up. Neither is promoted. The first rejected broad output triggered the unchanged 28-word source-copy guard and displayed the excerpt fallback; numerical prose was repetitive. The second returned technical model answers but retained unsupported risk-frequency and registry-rationale interpretation in the broad answer. |
| 6. Validation | Final backend suite: 303 passed in 5.14 seconds, two existing websockets deprecation warnings. Hosted HTTP evaluations used isolated frozen stores; production store/usage isolation was verified. The clinical answer-quality/release gate remains open. |

The initial unprivileged suite had 13 loopback socket-bind failures. With the test server's required local socket permission, the baseline observed run passed 287 tests; final checks passed as above. No provider calls were made by the regression tests.

## Hosted observations

All nine diagnostic Ask runs used the existing production Llama model and two-pass Workers Free route. All outputs, including rejected raw drafts/revisions and displayed fallbacks, are retained. Technical validation is not an answer-quality score.

| Instructions | Broad question | Explicit statistics | Simplification |
| --- | --- | --- | --- |
| Current production | 21.15 s; accepted, but vague and promotes registry rationale | 15.00 s; values retained, explanation thin | 10.88 s; concise numerical restatement |
| Completeness candidate | 35.39 s; rejected by copy guard, excerpt fallback omits benefits | 20.33 s; values retained but repetitive | 11.70 s; repetitive |
| Scope/depth candidate v2 | 27.83 s; accepted technically, unsupported frequency/rationale remain | 18.25 s; correct fixture numbers, repetitive explanation | 10.72 s; concise and source-consistent in this fixture |

Single observations on three cases are diagnostic; no population-level accuracy or latency improvement is claimed. The frozen source set contains noisy records and differs from current/future relevance-sorted ingestion. None of these runs refreshed a user workspace, changed review markings, or saved evaluation answers to a user brief.

The separate persistent evaluation ledger recorded **2,435.893162 neurons, 18 provider requests, zero pending reservations**, within the unchanged 9,000-neuron local cap for its UTC day. Production inference accounting was not modified by these runs. Other applications' Cloudflare account usage is outside this ledger's visibility. No paid provider or local GPU inference was called.

## Artifacts and review

- `apps/api/evaluation/answer_coverage/`: inventory, split manifest, corrected context comparisons, hosted-case rubrics and saved answers.
- `apps/api/evaluation/prompts/answer-completeness*.json`: inactive candidates, with exact prompt hashes in hosted metrics.
- `docs/performance/results/answer-coverage-{baseline,candidate,candidate-v2}-2026-10-28.json`: request timings, isolation checks and quota observations.
- `docs/functional-results/answer-coverage*-adjudication-2026-10-28.json`: source-hashed engineering judgments, not independent clinical validation. Historical/current comparisons were corrected before retention.
- `docs/functional-results/trial-results-parser-probe-2026-10-28.json`: real-payload schema/usefulness probe and inactive-parser decision.

The original offline comparison artifacts were retained and labeled superseded after fixing two evaluator errors: substring source-ID attribution and a shadowed per-fact indexing variable. The `*-corrected.json` results use exact source-scoped membership and the existing per-source context budgets. The correction did not change the reported totals.

GPT-6 Luna at medium effort prepared bounded benchmark/parser work and reviewed the production context fix and semantic traces. The primary agent cross-checked the reviews, required evaluator/parser/adjudication corrections, and retained responsibility for promotion decisions.

## Next optimization experiments

1. Package complete numerical outcome records with treatment/control definitions, units, denominator/population, timeframe, and uncertainty attached. Preserve atomic packets through chunking and context allocation; report omissions instead of slicing a number or dropping its comparator. Test against real posted-results payloads plus malformed, partial, multi-arm and missing-result fixtures before connecting ingestion.
2. Improve evidence-role selection: distinguish direct measured findings and labeling from registry rationale, unrelated disease case reports and preclinical discussion. Evaluate on the newer frozen relevance cohort as well as the original noisy source snapshots; do not hide failures by replacing the original benchmark.
3. Retry adaptive writing only against those improved contexts, then independently check held-out explanations, comparisons, benefits/risks and follow-ups. Preserve numerical accuracy and qualification while reducing repetition. Do not accept a longer answer merely because it contains more numbers.
4. Broaden hosted semantic evaluation after targeted cases pass, keeping shared free accounting and all attribution guards. Deployment remains deferred.

The local API and frontend were restored at ports 8000/3001 with the retained context change. Health checks do not submit Ask requests. The parser and candidate instructions remain inactive; source refresh/migration and answer-generation changes have not been rolled out.
