# TrialLens chat quality — 29 October 2026

## Retained improvements

ClinicalTrials.gov ingestion now indexes bounded **complete posted-outcome packets**, in addition to protocol descriptions. Each packet preserves the submitted outcome, population description, groups and regimens, denominators, measurement units/values/dispersion, timeframe, and reported analyses (including CI level, bounds, statistical method and gatekeeper/estimate comments). Values are not calculated or clinically reinterpreted. Oversized or malformed outcomes are omitted with metadata rather than sliced into partial statistics. Participant-flow, baseline and adverse-event tables are **not** indexed by this parser.

The previous inactive prototype omitted all eight outcomes in the saved real payload at its 1,200-character limit. The production parser retains all eight, at 3,746–7,306 characters per packet, within an 8,000-character packet bound. This is a format/coverage observation on one frozen public record, not universal parser coverage.

Packets remain whole through chunking, retrieval and the model context, including document-mode Ask. Context allocation gives a selected packet enough room to fit, reclaims duplicate excerpt space, and retains the global 28,000-character source-text budget. Packets that cannot fit are omitted and the context is marked incomplete. Metadata/instructions/history are outside that source-text budget; the provider quota reservation still includes the entire serialized request.

Conversational retrieval now covers explicitly requested evidence roles (labels, registry/protocols, publications/reviews, or adverse-event reports), subject to the existing source filter. An actual HTTP regression verifies that both generation passes receive the requested registry and label records. Previously, repeated chunks from a long label crowded out those records. This is distinct from the preceding helper-only first-eight-source control; that earlier control did not prove source-role coverage at the HTTP route.

Fallbacks no longer infer that statistics are absent from all indexed sources when only the selected passages failed to supply a usable result. Posted-outcome excerpt responses disclose that no statistical interpretation was generated instead of reverting to protocol-derived pseudo-results.

Existing workspaces, reviewed rows, saved answers and briefs were not refreshed or migrated. **New builds or an explicit source refresh are required to acquire posted results in older workspaces.** Ingestion metadata changes can require reviewing refreshed extraction rows. No frontend design or API request contract changed.

## Measured answer results

The four-case packet cohort uses the saved public NCT01563029 API payload. Protocol-only and posted-result snapshots are separate, hash-pinned inputs. The model and production instructions remained unchanged for this comparison.

| Question | Observed result | Wall time |
| --- | --- | --- |
| Protocol-only request for primary outcome statistics | Correctly states that requested results are not in the supplied excerpt | 13.30 s |
| Same question with complete posted outcomes | Reports both group values, analyzed denominators, reported contrast and 95% CI | 22.30 s |
| Simpler follow-up | Retains the numerical comparison, units, timeframe and uncertainty | 17.97 s |
| Whether supplied outcomes establish mortality benefit | Scoped “not established” answer; no claim mortality was never measured in the entire trial | 12.04 s |

The exact source-hashed engineering review found no material unsupported clinical claim in these four outputs. This is **not independent clinical validation or a general accuracy rate**. Remaining source/wording limits: the protocol calls its primary endpoint PM PEF while posted outcome 001 calls it AM PEF; the answer follows the posted result but does not surface that conflict. “Clear difference” is mildly evaluative; the answer does not reproduce the analysis gatekeeper comment and should not be read as a claim of unconditional or clinical significance.

## General answering remains below the release threshold

Five authored general holdouts cover combined benefits/limitations and source roles, numerical safety frequencies, a numerical comparison, protocol-versus-results, and simplification. Baseline and adaptive-depth-plus-feedback variants used the same source snapshots. Follow-up histories contain each variant’s own preceding answer, so they are not identical-input follow-up comparisons.

Targeted draft feedback is an **inactive evaluation experiment**. It flags schema/citation issues, 28-word source copies, assertive frequency wording absent from cited context, and explicitly requested quantities missing from a draft. These are negative mechanical checks, not proof of scientific entailment. It retains two calls and restores all patched state. It is not enabled in the server.

The experiment added more numerical detail but remained repetitive and omitted requested population/denominator or source-role qualifiers. The initial broad outputs lacked the requested AXOS/extended-release records in their actual model context; that was a retrieval issue, not evidence the writer ignored those records. After source-role coverage was repaired, the records reached the model, but the new final answer still dropped requested distinctions. The writer profile is therefore **not promoted**.

Two bounded model probes were also retained without changing the production model:

- The existing allowlisted gpt-oss-120b profile reached its 4,096-token output cap on the draft and returned `finish_reason=length`. The incomplete answer was rejected; this does not establish its semantic capability.
- The cheaper GLM profile completed two provider calls but repeated long label language. The existing 28-word copy guard rejected the final answer. A displayed excerpt fallback is not a successful conversational answer.

The production Llama model, production instruction strings, paragraph/citation and copy validation, product scoping, personal-treatment guard, daily cap and 100-answer alert remain unchanged. No guard was weakened to make a test pass. No new model or writing profile is activated.

Model rates and availability were checked against [Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/) and the [gpt-oss model reference](https://developers.cloudflare.com/workers-ai/models/gpt-oss-120b/). Requests used the Workers Free path without paid-provider or local-GPU fallback.

## Verification and accounting

- **327 backend tests passed in 5.56 seconds**; two existing websockets deprecation warnings remain. Tests include real public packet coverage, malformed/oversized fragments, allocation/deduplication, document-mode handling, results-only records, actual HTTP source-role delivery, filter preservation and the unchanged safeguards.
- All hosted runs used isolated frozen stores and a separate persistent evaluation ledger. Recorded production-store/usage isolation checks passed. No evaluation answer was inserted into a researcher’s workspace or brief.
- This UTC-day ledger ended at **8,492.779212 neurons used or conservatively reserved of 9,000**, with **507.220788 remaining** and 51 recorded requests, including 18 from the preceding session. One failed output-limit request retains its full conservative reservation (`pending=1`); it is not a running inference. Limits/reservations were not raised or cleared.
- This session made 33 provider calls across 17 diagnostic Ask attempts. Fifteen returned technically validated model answers; that is **not** fifteen semantic passes. Two attempts displayed fallbacks. Other Cloudflare account activity is outside the local ledger’s visibility.
- The API/frontend were restored locally at ports 8000/3001 with the retained data/retrieval changes. No deployment occurred.

## Artifacts and next work

Packet fixtures and builder: `apps/api/evaluation/answer_coverage/packet-cohort-2026-10-29/` and `build_packet_cohort.py`. Hosted outputs use `result-packets`, `general-quality-baseline`, `general-quality-feedback`, `source-role-coverage`, `quality-model-competence`, and `quality-glm-role-competence` names under `evaluation/answer_coverage/results/`, with sibling timing/quota records in `docs/performance/results/`. Three hash-verified engineering adjudications are in `docs/functional-results/`.

The separate fresh-PubMed source-conflict question was authored and frozen but **not executed** in this round. Do not claim its numerical direction/source-role tests passed.

Next, establish a bounded reasoning/output profile that can produce complete answers before testing that writer on the frozen general holdouts and the fresh-PubMed contradiction case. Preserve useful draft information through review and verify formulation, population, source role and numerical qualifiers. Prompt length alone has not solved those failures. Expand real API parser coverage (multi-arm/categorical/missing-result cases) before making broad ingestion-coverage claims. Deployment and the overall conversational-quality gate remain open.
