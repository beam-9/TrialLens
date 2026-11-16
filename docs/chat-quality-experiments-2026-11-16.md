# Chat quality experiments — 16 November 2026

Chat is not complete. Production remains the two-pass Cloudflare Llama profile.
No paid API or local GPU inference was used. These are engineering diagnostics
on retained public snapshots and synthetic controls, not clinical validation.

## Changes with regression evidence

The pediatric indication check now recognizes correct mathematical age floors
(`≥12 years`, `>= 12 years`, `12+ years`) instead of rejecting those equivalent
forms. New symbolic forms must follow a pediatric phrase within the same clause;
an adult cohort or citation identifier cannot supply the boundary. Incorrect or
upper-bound ages still reject. This is a narrow validation repair, not proof of
formulation-specific medical entailment; legacy prose checks remain limited.

An inactive Gemma 4 candidate reuses the existing completed-chat response parser,
strict JSON schema, final answer guards and conservative quota ledger. Its
citation-bound schema restricts citation spelling during generation. It neither
aliases unknown markers nor establishes that a cited source supports the claim.
Tests confirm that final provenance validation still rejects an invalid marker
when a provider ignores the schema. Production's model and inference sequence
are unchanged.

Evaluation-only revision feedback can identify citations present solely in
uncertainty. On the sampled combined question, this did not recover requested
registry-role coverage. It is not promoted.

## Measured results

All timings below are individual loopback Ask API wall times with hosted
inference; provider cache state is unknown. Single-pass captures use an explicit
evaluation replay instead of a second provider call. Their internal trace still
labels that replay as revision; top-level experiment metadata identifies it.

| Experiment | Observation | Decision |
|---|---|---|
| Llama control / completeness revision | 24.36 / 21.44 s. Both omit requested registry explanation. | No demonstrated coverage improvement. |
| Llama answer-parts / uncertainty feedback | 27.92 s rejected / 32.12 s accepted. Accepted answer still omits requested registry role. | No promotion. |
| GPT-OSS medium, five quality cases | Two accepted, three rejected; 14.62–71.36 s. Source review found formulation-population broadening, an invented safety percentage and percent/percentage-point confusion. | No promotion. |
| Gemma two-pass, nonthinking | 27.88 s; final source-copy rejection and incomplete registry role. | No promotion. |
| Gemma thinking, 4096 / 8192 output caps | 78.68 / 95.44 s; both finish with `length`, no completed final answer. | No larger thinking budget. Failed-request reservations retained. |
| Gemma direct v3, five cases | Five technically accepted, 5.45–18.82 s. Several requested qualifications remain missing. | Promising latency, insufficient semantic coverage. |
| Gemma direct v4, five cases | Four accepted, one rejected; 4.31–21.29 s. Safety denominators/rates improved. Numeric case uses unknown `[demo]` and is correctly rejected. | No promotion; never substitute its raw draft for the displayed fallback. |
| Gemma v4 with citation-bound schema, numeric + simpler follow-up | Both accepted, 7.51 / 5.95 s. Retain 240 adults, placebo, 12 weeks, 0.5 percentage points and CI 0.2–0.8. | Narrow positive evidence only. |
| Same candidate, public posted-trial cohort | Protocol-only answer accepted in 7.98 s. Posted-statistics attempt reaches 1800-token cap in 39.67 s; runner stops before follow-ups. | Long-record reliability gate fails. Do not count unrun cases as passes. |
| Gemma v5 focused answer prompt, posted statistics | 40.47 s; again truncates at 1800 tokens. | Prompt length/focus guidance alone does not resolve the failure. |
| Gemma v4 bound candidate, public ATOMIC abstract | Accepted in 77.97 s. Preserves numerical pairs but incorrectly claims the narrative conclusion is supported by them. | Critical semantic failure despite validator acceptance. |

The ATOMIC capture retains HbA1c 0.35% versus −0.58%, increased-HbA1c proportions
62% versus 15%, and LDL-C −55.20% versus −7.69%. However, it then says the stated
improvement is supported by those data. The requested numerical/narrative
mismatch is not resolved by keeping numbers in source order. The existing order
guard does not test this logical relationship.

Independent read-only source review confirmed the direct v4 safety answer's
n=141/145 denominators and rates. It also identified missing requested
combination-label limitations and weak registry-rationale framing. The shorter
bound numerical answers preserve their substantive figures and demo status.
These checks do not establish a general accuracy rate.

A subsequent native GPT-OSS medium single-pass v5 comparison answered the ATOMIC
case in **34.43 s**. It retained the three arms, 185 participants, 16-week
timeframe, both numerical outcomes and increased-HbA1c proportions, and explicitly
identified the numerical/narrative conflict. It kept the older reviews separate.
This is a positive targeted result, not enough to promote the profile; independent
source review found that baseline percent-change framing should be explicit, and
the 2017 review scope is underspecified. Long-record tests remain necessary.

The native single-pass v5 posted cohort was not a pass: protocol statistics
(6.56 s) and posted statistics (17.36 s) were rejected for missing inline
attribution; the protocol draft also adopted the question's morning endpoint
instead of correcting it to the source's afternoon endpoint. The simpler
follow-up was accepted (14.19 s); the mortality question did not reach inference
because its conservative reservation exceeded remaining quota. A follow-up based
on a rejected predecessor is not evidence of reliable conversational continuity.
The native v6 combined attempt likewise did not reach inference.

A consolidated v7 prompt reduces instruction text from 1006 to 578 words while
retaining the evidence-only, citation, statistical, source-role, demo and
treatment-boundary requirements. Its combined attempt (19.40 s) was rejected;
source review also found the same incorrect extension of the tablet pediatric
indication to the extended-release formulation. It remains inactive.

The smaller native v7 controls returned three accepted answers and one rejected
safety answer (11.75–23.62 s). The safety draft again invented a 45% upper
frequency, which final validation rejected. Offline replay of the existing
mechanical feedback correctly identifies 45 as absent from the cited source.
The numerical comparison preserves percentage-point units, population, comparator
and timeframe. The simpler follow-up needs tighter interval wording and loses
its demo qualifier in the body (the product generation note still flags demo
evidence). The protocol answer likewise lacks a body demo qualifier and makes
an overly broad absence statement about measured data. Technical acceptance is
not a semantic pass for these cases.

The final Gemma v7 two-pass experiment reused existing exact label-scope
clauses and mechanical/numeric feedback. It kept the tablet and extended-release
populations separate, but still copied long source passages and wandered into
unrequested findings. It placed a ClinicalTrials.gov citation beside an unrelated
PubMed hazard ratio; restricting citation spelling does not establish attribution.
The final answer was rejected (211.08 s). Offline feedback replay confirms the
long-copy failure. This context/revision profile is not promoted either.

Final evaluation ledger: **8549.972661 neurons used or conservatively reserved,
450.027339 remaining, 51 requests, four retained failed-request reservations**.
All model processes in this round are terminal; no cap was raised or reservation
cleared. Remaining allowance is below many native-profile input/output reservations.

## Bottlenecks and next gates

Generation dominates latency and quality failures. Requested evidence is in the
captured contexts, but writers omit it, drift into unrelated records, or
misinterpret its meaning. The second pass can delete relevant qualifications.
Larger reasoning budgets have not solved these sampled problems.

Next experiment should organize the existing source context rather than append
more instructions. Reuse exact formulation indication clauses and linked
outcome-packet identities to separate source roles and requested comparisons.
Retain full group-linked outcome packets and all source-scope/truncation flags;
do not trim away denominators, comparison definitions or contradictory results.
Compare this against the retained unchanged-context baseline on long posted
tables, combined benefits/safety/registry questions and the public abstract
discrepancy, then add independent questions before any promotion. A candidate must improve coverage and source
fidelity, not just return valid JSON. Do not raise quotas, bypass truncation
rejection, infer unreported outcomes, or promote on synthetic tests alone.

Evidence: matching answer/context captures under
`apps/api/evaluation/answer_coverage/results/` and timing/quota captures under
`docs/performance/results/`, named `revision-*`, `answer-parts-*`,
`uncertainty-coverage-*` and `gemma4-*` for 15–16 November.

Validation: **631 API tests pass**, with two existing websocket deprecation
warnings. A restricted run could not bind the loopback test server; rerunning
with loopback enabled passed the complete suite. Browser UI was not changed or
retested in this iteration. No production-model promotion or deployment.

Provider-profile references checked 16 November: [Gemma model parameters](https://developers.cloudflare.com/workers-ai/models/gemma-4-26b-a4b-it/) and [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/). The candidate uses the existing Free-plan attestation and local quota; neither independently verifies account billing status.
