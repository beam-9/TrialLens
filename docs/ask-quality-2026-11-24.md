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
