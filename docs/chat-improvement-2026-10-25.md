# Chat improvement — 25 October 2026 (Vancouver)

This continues [the previous evaluation](chat-improvement-2026-10-24.md). Hosted runs occurred on 26 October UTC / 25 October in Vancouver. No deployment, model replacement, global prompt replacement, paid inference, or local GPU inference occurred.

## Changes

ClinicalTrials.gov ingestion now records that it indexes protocol descriptions, and separately audits whether the fetched API payload has an absent, present, empty, or unrecognized `resultsSection`. It still does **not** index structured outcome tables. This field describes a fetched payload, not whether results exist elsewhere. No existing records were refreshed or migrated.

Conversation context carries bounded nonempty indexed section names. Known protocol-only content is described explicitly, while unknown historical content remains unknown. Source content and public citation identity are preserved. Extra model interpretation and completed-status notes were tried but rejected after the focused quality gate; they are **not** in production. The final rejected profile is retained as an unapplied evaluation patch: `apps/api/evaluation/context-boundaries-2026-10-25.patch`.

`INSTRUCTIONS`, `REVISION_INSTRUCTIONS`, the production Llama model, two-pass strategy, citation/copy validation, product scope, 100-answer alert and daily cap are unchanged. The retained change concerns factual source inventory and known indexed-content scope delivered to those passes. It does not mechanically verify every generated claim.

## Evaluation and iterations

All runs used the isolated frozen-source runner and the same persistent evaluation ledger. Source snapshots, question rubrics and production stores were preserved. Outputs are immutable; each independent adjudication pins its answer artifact hash. The bounded review and source tests were delegated to GPT-6 Luna at medium effort; implementation and release decisions remained with the primary agent. The primary agent cross-checked the latest review against exact draft/final text and required correction of material copied-over review descriptions before retention. These are engineering judgments, not clinical validation or calibrated accuracy scores.

| Run | Purpose and measured observation |
| --- | --- |
| `cloudflare-holdout-baseline-2026-10-25` | Four previously pending authored holdouts, original production context. All returned model answers in 10.67–15.10 seconds. Independent review: four partial, no critical errors. Correct core distinctions, but omitted population, regimen/time, diet/exercise and explicit mortality-measurement qualifiers. |
| `cloudflare-section-boundaries-2026-10-25` | Two broad/follow-up cases after adding section inventory and known-content scope. Old snapshots lack section metadata, so this did not establish the needed boundary for those records. 14.57–22.06 seconds; two partial. Broad final promoted registry background about adherence into an established limitation. |
| `cloudflare-registry-boundaries-2026-10-25` | Added explicit rationale-versus-results guidance to the generic registry scope. 16.92–26.12 seconds. Independent review: broad partial, simplification supported; the broad answer correctly called AXOS research planned. Drafts still contained unsupported or incompletely qualified claims that revision removed. This intermediate scope wording was subsequently moved out of visible source descriptions. |
| `cloudflare-explicit-boundaries-2026-10-25` | Experimental interpretation boundary in a separate model-context field. Three model answers in 9.31–22.11 seconds. Broad/follow-up partial, with completed-status errors; protocol control supported. Not promoted. |
| `cloudflare-completed-status-2026-10-25` | Experimental explicit completed-status note added to that profile. Three answers in 8.20–18.56 seconds. The ongoing-status wording disappeared, but the follow-up introduced a false source-wide absence claim (other sources “don’t provide additional information on its effects”). Rejected; extra model notes removed. See pinned independent adjudication for detail. |

Answer artifacts and adjudications: `apps/api/evaluation/m0/results/cloudflare-<run>-2026-10-25-{answers,adjudication}.json`. Timing/protocol records: `docs/performance/results/cloudflare-<run>-2026-10-25.json`. These small differing workloads are diagnostic observations, not a controlled estimate of accuracy or latency improvement. Single outputs are stochastic; no quantitative quality improvement rate is claimed.

The experiments show why more prompt-like context notes are insufficient: removing one interpretation error did not yield robust relevance and preservation of detail. The protocol controls correctly distinguish planned research from proof of mortality benefit. The fixture explicitly says no results have been posted, so repeating that is supported for this control. Synthetic records do not validate real-world effectiveness. No experimental context profile clears the quality gate; no quantitative accuracy improvement is claimed.

## Verification and limits

- **235 backend tests passed** in the final run (3.67 seconds after rejecting the extra notes), with two existing websockets deprecation warnings. New tests cover fetched-results states, protocol-only indexing, known/unknown section scopes and both generation passes receiving section names and interpretation rules.
- The first full test attempt had seven sandbox socket-bind failures; rerunning with loopback permission passed. During final wording cleanup two assertions temporarily expected old text; they were updated and the full suite passed again.
- No frontend files changed. The prior 14 browser checks are historical evidence, not rerun results for this session.
- Restored local API on port 8000 and web preview on port 3001; `/api/health` confirms Cloudflare configured without generating an answer.
- Current UTC-day evaluation accounting: **4,213.282 neurons**, 28 requests, no pending reservations, within the unchanged 9,000-neuron cap. Other applications/account activity is not visible in this local ledger. No reservations were cleared or limits raised.

## Next steps / release decision

The chat quality gate remains open. First improve question-relevant source selection and preservation of requested context through revision and simplification: formulation/age/adjunct conditions, major warnings, trial-specific background regimens and explicit study-status wording. Use exact existing traces to distinguish missing evidence from information dropped by generation. Do not treat an omitted optional number as an invented statistic, or a concise answer as automatically sufficient.

Re-evaluate targeted failures and independent holdouts before a full frozen-suite rerun and deployment preparation. Further experiments must stay under the free cap, retain failed outputs, and preserve all attribution and fallback safeguards. Broader result-table ingestion is a separate scoped task requiring real parser fixtures; this change deliberately does not claim that those tables have been read.
