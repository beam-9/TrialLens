# Chat quality: 1 November 2026

## Decision

The general conversational quality gate remains open. Do not promote an experimental model or start the layout redesign on the assumption that chat is finished. The useful production change is a narrow, zero-inference renderer for complete registry participant-count outcomes; it is not a general answer engine.

## Delivered and verified

- Complete reported categorical counts can be rendered directly, with their denominators, missingness, original group labels, citation, study context and nonrandomized single-group causal limitation. No percentages, changes, paired transitions or effect sizes are calculated.
- Eligibility requires one explicit trial ID, an exact outcome title, baseline/week count intent, known single-group/nonrandomized design, a complete retrieved outcome packet identical to the stored source, and a narrow request vocabulary. Unknown qualifiers, subgroups, competing endpoints, analyses, mean outcomes and incomplete tables fall through to the existing synthesis path.
- Simplification and repeated simplification preserve the same figures and limitation. A new trial or population cannot inherit the prior answer's table. Personal-treatment decisions are guarded before this route.
- The route works without configured inference and does not touch the inference usage ledger. It is explicitly labelled as reported statistics rather than generated explanation.
- Other work in this iteration preserves complete outcome identity and study design, normalizes Unicode citation brackets without inventing IDs, and adds isolated numeric/coverage/outcome-ownership checks. Experimental code remains outside the production writer.

Final API suite: **526 passed**, two existing websockets deprecation warnings. Initial sandbox-only HTTP tests failed because localhost socket binding was denied; all passed with socket access. `git diff --check` passed.

Final isolated HTTP measurements: original answer **26.15 ms** server time, simpler follow-up **19.12 ms**; both returned HTTP 200, `reported_statistics`, no fallback, no provider calls. See [metrics](performance/results/reported-count-route-final-2026-11-01.json) and [answers](../apps/api/evaluation/answer_coverage/results/reported-count-route-final-2026-11-01.json). This is a two-question local measurement, not a general latency benchmark.

Expect browser verification used the actual asthma workspace. Original question, simpler follow-up and repeated simpler follow-up all preserved Week 0: uncontrolled 312, controlled 0, missing 1, denominator 313; Week 8: uncontrolled 72, controlled 229, missing 0, denominator 301. Each showed no AI inference, one inspectable NCT00545844 citation, and the causal/individual-transition limitation. The original included montelukast added to inhaled corticosteroids. Source inspection showed the design, outcome and original-source link. All final Ask requests returned 200. One usage request returned 502 during an intermediate API restart and recovered. No sources, reviews or brief were changed; browser testing added answers.

The browser first exposed a follow-up regression after scope tightening: an internal history prefix was treated as question content. The fix now selects the last validated original count question; unit tests, isolated HTTP and all three browser asks passed after restart. The running API loads the saved `.env` configuration.

## Hosted experiments and error analysis

Frozen source context separates generation failures from retrieval failures. A supplied source ID and matching numbers do not prove the source entails the claim.

| Experiment | Measured result | Decision |
| --- | --- | --- |
| Native GPT-OSS, v5 control | Five cases fell back; Unicode bracket mismatches explained some rejections, but invented frequency and scope errors also occurred. | Fix citation formatting; no model promotion. |
| Native GPT-OSS with numeric feedback | Safety details improved; copied wording, cross-trial attribution and invalid provider output remained. | Keep inactive. |
| Snippet outcome review | Lost design limitation or crossed primary/secondary outcome support. | Keep inactive. |
| Complete-outcome review | Reviewer removed invented percentages but omitted baseline missingness and lost design/time support. | Keep inactive; complete packets remain valuable input. |
| Qwen thinking enabled | Output reached the 1,800-token limit. | No token-cap increase or promotion. |
| Qwen without thinking | Completed two passes, but copied 28 consecutive source words and was correctly rejected. | Do not weaken the copy safeguard. |
| Default Llama, v6 plus bounded-repair option | 32.19 s; two actual calls; automated checks accepted it, but review found a pediatric indication broadened across formulation/product labels and omission of the age-10 boundary. | Semantic failure; no prompt promotion. |
| Qwen, v6 plus bounded-repair option | 41.48 s; draft completed, reservation check blocked the normal revision call. No complete final candidate. | Inconclusive, not a quality pass. |

The evaluation-only repair option permits at most one additional call after a complete, schema-valid revision with identified mechanical failures. It does not retry partial/provider failures, bypass quota, or relax the final citation/copy/CI checks. Neither latest canary reached that third call.

Raw answer and request-shape traces are under `apps/api/evaluation/answer_coverage/results/*2026-11-01.json`; matching timings are under `docs/performance/results/`. They include source context and hashes, not credentials or reasoning text.

Final evaluation ledger: 7,403.525076 neurons used/reserved of the application cap of 9,000; 1,596.474924 remaining; 27 actual reserved requests, two conservative pending reservations retained. Remaining budget was insufficient for the Qwen revision's worst-case reservation. No paid fallback, cap increase, pending-reservation deletion or local GPU inference was used for the hosted experiments. Stop further large hosted runs until the ledger's UTC day resets.

## Next experiments and layout gate

1. After reset, test a compact source-specific fact representation for label formulation, ingredient/combination, exact population boundary and source role. Preserve original passages alongside it; do not replace evidence with unchecked extracted claims. The Llama canary demonstrates why a larger prompt alone is insufficient.
2. Re-run the broad scope canary before spending quota on a whole cohort. Separately adjudicate age/formulation, combination warnings, protocol versus results, numerical ownership, missingness and follow-up fidelity. An automated acceptance is not a semantic pass.
3. If the canary passes, run the five general holdouts, real PubMed numeric/contradictory-narrative case and posted mean-outcome case. Report every fallback and omission. Avoid tuning only to NCT00545844.
4. Promote only a bounded, verified profile; keep the current free-tier quota, source fingerprints, citation inspection, original-source links and deterministic factual route.
5. Move to layouts when these representative cases have no unresolved critical scope/numeric errors and browser follow-ups remain accurate and useful. Deployment is a later decision.

Unresolved risks: exact-title statistics eligibility is intentionally limited; aggregate count rendering does not solve open-ended synthesis. Refresh search churn can drop a useful retained trial. General answers can still conflate populations/formulations despite correct citation syntax. Provider latency, incomplete responses and quota reservations remain availability constraints. No claim of clinical validation or general chat readiness is made.
