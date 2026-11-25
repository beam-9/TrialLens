# TrialLens Ask quality review — 24 November 2026

Answers were checked against the passages actually sent to Cloudflare and the frozen source inventory. A generated response counts as a pass only when it answers the requested parts with source-supported claims.

## HbA1c paper baseline

Capture: `apps/api/evaluation/answer_coverage/results/paper-numerical-feedback-2026-11-23.json`.

| Question | Displayed answer | Evidence and failure stage |
| --- | --- | --- |
| Indexed Results | Fail. The fallback counted passages without answering. | Both arm estimates and the signed Figure 2A contrast were in context. Draft and revision omitted both ± terms, linked the positive difference magnitude to negative confidence bounds, and overstated paper access. The sign check correctly rejected the revision. |
| Figure 2A | Substantially correct with an endpoint wording gap. | The displayed answer preserved the signed estimate, bounds, arms, and direction. The endpoint is least-squares mean percent change in HbA1c from baseline. |
| Simplification | Partial. Both arm estimates and uncertainty were preserved. | The interval was omitted. Caption evidence was absent from the exact follow-up packets, and the extractive parent could not supply eligible conversational carryover. |

## Independent STOIC and correction baseline

Capture: `apps/api/evaluation/answer_coverage/results/stoic-default-2026-11-24.json`. The frozen snapshot and both source XML hashes were verified. The run displayed three generated answers using six Cloudflare Free calls and 986.77 evaluation neurons.

| Question | Displayed answer | Evidence and failure stage |
| --- | --- | --- |
| Corrected counts | Fail. Correct counts, incomplete attribution and explanation. | The model had the correction and reported 11/73 usual care versus 2/73 budesonide for intention-to-treat, and 10/70 versus 1/69 for per-protocol. It cited just the original paper, despite the explicit request to use the correction. It named the open-label design without explaining its potential effect on care-seeking or outcome assessment. |
| Simplification | Fail. The per-protocol figures and correction disappeared. | The correction remained in the generation packets. This was an omission during generation. |
| Mortality | Pass. | The answer distinguished the urgent-care result from mortality and kept the mortality claim within the supplied evidence. |

The correction explicitly amended the summary counts. The frozen Results body reverses the per-protocol denominators, so the original abstract and visible Results wording should not be treated as interchangeable. These fixtures test historical research interpretation.

## Release status

Cloudflare Workers Free remains the selected inference profile. These quality captures leave open defects in numerical completeness, source attribution, and conversational continuity. Release readiness remains unverified.

## Linked interval revision

Capture: `apps/api/evaluation/answer_coverage/results/paper-linked-interval-2026-11-24.json`.

All four questions returned generated answers. The Results and simplification responses still omitted both ± terms and the interval. In this run the follow-up received both relevant captions after a conversational parent, so the interval omission persisted even when the evidence reached the model. Figure 2A again preserved the signed contrast and interval but conflated percent change from baseline with HbA1c level. The mortality answer correctly limited the inference to the outcomes studied. The result does not meet the numerical coverage requirement.

The API suite passed all 720 tests with loopback permitted. The rebuilt Cloudflare-profile API image returned HTTP 200 from `/health` in a network-isolated smoke test.

## Question coverage prompt experiment

The first evaluation-only prompt recovered both arm estimates with ± terms and the signed interval in the raw Results revision. The final validation rejected that response. The model used square brackets for the confidence interval and abbreviated the source ID. The caption and simplification cases also fell back. The mortality case generated a response. This experiment did not change the production prompts.

The second candidate reserves square brackets for complete citation markers and asks for confidence intervals in parentheses. That targets the observed formatting failure while preserving citation validation.

On the paper cohort the citation-format candidate produced two fallbacks and two generated answers. The rejected Results and figure outputs still had uncited evidence paragraphs. The simplification preserved both ± values but omitted the interval and followed an extractive parent. The mortality answer correctly denied a demonstrated reduction in deaths, then added an unnecessary secondary comparison. The candidate remains inactive.

The percentage check now applies implied units to attached confidence intervals on both sides of validation. An invented bound such as −0.64 is rejected even if the answer omits its percent sign. The full API suite, frontend lint and typecheck, and the rebuilt API health check passed.

The same citation-format candidate returned three fallbacks on STOIC. The rejected corrected-counts response supplied per-protocol denominators but cited the correction only for a dosing detail the question did not ask for. The simplification dropped the intention-to-treat counts. The published correction must support the corrected denominators directly, and a rewrite must retain both requested analyses.

## Broader production-pipeline holdout

The M0 holdout returned five generated answers. The protocol answer correctly distinguished planned enrollment, comparison and outcome from available results. The synthetic numerical answer preserved its core comparison and confidence interval, but overstated what a single endpoint established across the full 12 weeks. Its follow-up retained the figures and barely shortened the wording. The label safety answer omitted both trial denominators and the limitation on causal inference from voluntary reports. The mixed-source answer omitted the adult extended-release indication and lost the AXOS registry and ZITUVIMET pancreatitis qualifications in revision.

The separate personal-treatment case took the deterministic guard route with zero model calls. These findings come from reviewing the displayed answers and exact evidence packets.

The packet cohort stopped at `protocol-statistics` after a Cloudflare quota error during revision. The displayed fallback is a provider-limited observation, so it has no semantic pass. The other packet cases and the refreshed asthma cohort did not run. Local accounting showed 1,374.91 neurons remaining with one pending reservation, which does not establish availability on the Cloudflare account. The runner verified evaluation-store isolation and stopped without retrying or switching providers.
