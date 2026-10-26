# Chat grounding and source acquisition — 25 October 2026 (Vancouver)

This continues [the preceding report](chat-improvement-2026-10-25.md). **The answer-quality gate remains open.** No experimental model or answer strategy is promoted; deployment has not occurred. The original M0 inventory, snapshots and rubric are unchanged.

## Retained production improvements

1. **Paragraph attribution.** A citation in one paragraph no longer permits a separate uncited paragraph. Validation also splits blank-line paragraph breaks inside a single schema item. A regression reproduced an accepted uncited “safe for everyone” paragraph before the fix. Repeated valid citation markers remain supported. This enforces attribution, not scientific entailment.
2. **Safe uncited abstention.** Previously, a negative phrase such as “I can't assess…” could let an uncited clinical claim and clinical assertions in `uncertainty` pass. A second regression reproduced this. An accepted citation-free abstention now uses a fixed verification-outcome message and clears model uncertainty: it says the application could not verify a sourced answer, rather than asserting that evidence does not exist. Uncited affirmative answers still fail validation. Cited source claims still require semantic evaluation.
3. **Relevance-first PubMed acquisition.** ESearch now explicitly requests `sort=relevance`, retains its five-hit limit and two-request search/fetch flow, and preserves returned search order even if EFetch returns a different order. PubMed publication types are retained as source metadata and sent as bounded context fields to both generation passes. Older records without those fields remain readable.

The production Llama default, global instructions, two-pass strategy, copy/citation safeguards, product scope, treatment guard, 100-answer alert and daily cap remain. A Qwen3.8 named-schema/low-reasoning request profile is gated to the inactive evaluation model. No paid or local GPU provider was called.

Existing workspaces were not refreshed or migrated. These retrieval changes apply on a subsequent build/refresh. The existing ingestion policy re-extracts rows when source metadata changes; refreshed rows may therefore need review. No researcher corrections were altered during this session.

## Source acquisition evidence

The read-only [sort audit](functional-results/pubmed-sort-audit-2026-10-25.json) compared five results for exactly `type 2 diabetes metformin`. The unspecified sort returned titles concerning nerve surgery, rat studies, genetic response and pancreatic cancer. Relevance sort returned clinical metformin reviews and a randomized combination trial, alongside broader/prevention reviews. This is an observed retrieval improvement for one query, not a calibrated recall or evidence-quality score.

NLM documents that the API default differs from the web default: see [E-utilities parameters](https://dataguide.nlm.nih.gov/eutilities/utilities.html), [EDirect relevance sorting](https://www.nlm.nih.gov/dataguide/edirect/esearch.html), and [NCBI's PubMed API note](https://ncbiinsights.ncbi.nlm.nih.gov/2022/03/24/test-server-pubmed-api/).

The [production connector check](functional-results/pubmed-relevance-production-check-2026-10-25.json) returned four usable abstract-bearing sources and publication types in **0.83 seconds**, in memory only. Its IDs differ from the earlier audit: live rankings can change, and records without abstracts are skipped. The earlier relevance audit includes a hit with zero abstract characters. Do not interpret the comparison field against a different live request as a same-request rank failure; the mocked contract test verifies order preservation within one fetch. Relevance ranking is not clinical grading, a date cutoff, or comprehensive coverage.

A new, separately hash-checked [public cohort](../apps/api/evaluation/cohorts/pubmed-relevance-2026-10-25/README.md) retains a subsequent relevance-sorted source set. One broad Ask diagnostic on that set completed in **16.46 seconds**. Its high-level claims were source-consistent, but it remained vague about limitations and other potential benefits. Older review claims need dated framing. This is not an independent clinical validation set or a replacement for the frozen benchmark; no controlled before/after accuracy improvement is claimed.

## Rejected answer experiments

Ten isolated Ask checks ran across the following variants, making 18 provider calls. Six final responses passed technical answer validation; that does not mean six accurate/informative answers. Primary-agent adjudications inspect exact source context and distinguish drafts from final answers. They are engineering judgments, not clinical validation.

| Variant | Observed result | Decision |
| --- | --- | --- |
| Strict quote selection, broad question | Seven exact quotes and one nonmatching quotation; stopped after selection, no final answer | Reject; follow-up not run |
| Verified quote subset, broad/follow-up | Exact text membership held, but writer promoted registry background into general harm and generalized a MODY case into type2 support; 25.14–39.92 s | Reject |
| Qwen3.8 competence check | Draft has placeholder citations and unsupported rarity/mechanism; correction hits 1,800-token limit; 97.53 s | Reject; no final generated answer |
| Atomic draft/review, initial | Draft citation IDs contain extra delimiters; stopped before review; 11.61 s | Reject |
| Citation-enumerated draft/review | Correct IDs, but reviewer approves preclinical effect without qualifier and weak case generalization; 21.47 s | Reject |
| Scope-filtered claims, plain-label holdout | Keeps purpose/age/diet-exercise; drops the entire requested downside claim because its evidence quote cannot be verified; 11.69 s | Incomplete; not promoted |
| Atomic claims, regimen holdout | Reviewer approves 0.6%–3.9% as a range despite larger rates/other controls in context and a quote not containing 3.9%; 29.28 s | Reject: numeric/comparator error |
| Granite competence check | Draft adds unsupported clinical details; final has no inline citations and loses downside coverage; 15.43 s | Reject; final guard works |
| Fresh relevance cohort, normal production strategy | More topic-relevant inputs; concise but insufficiently specific answer; 16.46 s | Retain acquisition change, no quality-gate claim |

All answer/primary-adjudication artifacts follow `apps/api/evaluation/m0/results/cloudflare-<variant>-2026-10-25-{answers,adjudication}.json`. Timing artifacts are in `docs/performance/results/`. Source answer hashes are pinned in adjudications; failed observations are not overwritten.

Exact source contexts and outputs are retained. Intermediate strategy module revisions were hash-pinned but not committed individually; not every earlier code revision is available as a standalone artifact. Later filters must not be credited retroactively to the recorded hosted answers. Archive or commit each next strategy revision before running it.

The two strategy prototypes live only in `apps/api/evaluation/evidence_plan.py`, selected explicitly through `--strategy-experiment`. They preserve the original evidence context and normal final answer guards, restore globals on exit, and make two calls at most. Invalid strategy outputs stop a run. They are **not imported or enabled by the production server**.

Later necessary prototype filters reject missing preclinical/case scope, unsupported “rare”, and numbers absent from an approved quote. [Offline post-filter observations](performance/results/claim-filter-offline-2026-10-25.json) show that these remove known bad claims, but they also leave inadequate coverage or no claims. Those observations are not new model generations, final API acceptance checks, or entailment proof. A review model's “supported” label is not verification.

Model availability, reasoning options and rates were checked against [Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/), [Qwen3.8](https://developers.cloudflare.com/workers-ai/models/qwen3.8-27b/), and [Granite](https://developers.cloudflare.com/workers-ai/models/granite-4.0-h-micro/). Both stayed on the Free-account path; neither earned a production switch.

## Verification and remaining allowance

- **284 backend tests passed in 5.15 seconds**. Two existing websockets deprecation warnings remain. Regressions reproduced both attribution/uncited-abstention failures before fixes; quote/claim experiments, context restoration, same-record membership, schema/citation errors, unchanged final copy guards and source ordering are covered.
- [Offline validation replay](performance/results/citation-paragraph-replay-2026-10-25.json): all three retained final responses from the selected earlier run remain accepted; one draft with an uncited paragraph is rejected. This tests guards, not claim accuracy.
- [Browser checks](functional-results/chat-browser-check-2026-10-25.json): page rendering, Ask/Evidence navigation/selection, disabled empty submission and retained empty composer pass; no console errors or inference calls. Duplicate successful icon requests are a minor observation. This is not a new full hosted UI-answer quality run. The test browser was closed afterward.
- A bounded read-only agent review found no material regression in the production diff. GPT-6 Luna at medium effort handled unit-test scaffolding, browser checks and that limited review; primary-agent review handled factual answer assessment and promotion decisions.

The [ledger calculation](performance/results/free-evaluation-cap-2026-10-25.json) records **8,109.399 neurons used/reserved of 9,000**, leaving **890.601** for UTC day 26 October. One failed request retains its conservative reservation. The representative broad draft alone requires **1,023.855** under the existing reservation rule; the next broad validation request cannot be reserved. No reservation was refunded/reset and no cap was raised. Smaller requests may fit, but that cannot complete the required broad quality gate. This local ledger cannot measure other account applications. Cloudflare resets its daily allocation at 00:00 UTC (next reset: 26 October at 5 p.m. Vancouver time).

## Next required work

The remaining task is factual completeness and coherent source interpretation, not styling or transport success. Continue with question-relevant evidence coverage, exact product/population/comparison/timeframe and source evidence level. Avoid another unconstrained prose rewrite or relying on a model's self-approved quote alone. Preserve requested risk/context through simplification, and phrase evidence gaps narrowly.

Before deployment, a candidate must pass focused failures, separately authored conversational holdouts and the full frozen suite without material unsupported claims, while actually answering each requested facet. Recheck the free allowance before hosted runs; do not bypass the failed reservation to resume. Keep all rejected observations and the existing safeguards. The fresh-source diagnostic and passing software/browser checks do not close the answer-quality gate.
