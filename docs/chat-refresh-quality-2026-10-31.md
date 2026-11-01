# TrialLens evidence refresh and chat quality — 31 October 2026

## Retained changes

Evidence refresh is recoverable. `JsonStore.replace_workspace_evidence` archives the preceding source and extraction versions in the same atomic transaction. Changed source content does not inherit prior approval: reviewed rows become needs-review rows, while unchanged sources retain their existing manual review. Prior annotations remain in the archive instead of being reapplied to changed evidence. A provider that is unavailable or returns no matches cannot silently remove its prior cohort while other providers refresh. Saved answers record cited-source fingerprints, and Brief generation warns when their source versions have changed (or legacy version tracking is unavailable).

The authorized asthma/inhaled-corticosteroids refresh completed on 29 October after a local, ignored, permission-restricted backup. It retained 10 sources and produced 37 chunks, 10 new unreviewed rows and six complete posted-outcome packets. Two previously reviewed records that fell out of the refreshed search remain in the revision archive. All saved answers and briefs across the store retain their pre-refresh hashes, rechecked on 31 October. The private database/backup and researcher annotations are excluded from Git. A separate aliased public-source snapshot supports reproducible quality evaluation; M0 fixtures remain unchanged.

A narrow final-answer check now rejects explicit confidence-interval-as-true-parameter probability wording, including adjacent-sentence references and the observed “true effect is likely to fall within this range” error. It also supplies feedback to the evaluation-only revision experiment. Correct repeated-interval construction and Bayesian credible-interval examples remain negative controls. This wording check is **not** a general statistical or claim-entailment validator; it cannot establish factual accuracy merely by passing.

The GPT-OSS adapter now supports its gated native Responses profile and excludes reasoning from the returned/stored answer. An evaluation-only reasoning-effort option allows low/medium/high comparisons without changing live settings. Incomplete responses, unknown/uncited citations, long source copies and existing product/patient safeguards remain rejected. No paid API or local GPU fallback was added.

## Measured findings and decisions

Source retrieval delivered the reported figures in the refreshed-source diagnostic. The main failures occurred during writing/revision: omitting meaningful denominators and certainty, conflating an add-on before/after observation with an isolated treatment effect, misreporting height change in cm as growth velocity in cm/year, and asserting that unmentioned outcomes were never measured.

| Experiment | Observed outcome | Median Ask time |
| --- | --- | --- |
| Current Llama writer, three frozen refreshed-asthma questions | Core displayed counts correct, but all three materially incomplete | 13.85 s |
| V4 writer + revision feedback, same three questions/model | More text, but causal-attribution/unit errors; no quality passes | 28.68 s |
| GLM + compact V5 writer, five general frozen questions | Four technical model answers, one copy-guard fallback; only the safety-frequency answer met the engineering rubric | 12.32 s across all attempts |
| Native GPT-OSS, V4 low/medium numerical canaries | Completed responses still made unsupported absence/statistical claims | 10.63 / 19.21 s |
| Native GPT-OSS, V5 high numerical canary | Incomplete at 4,096 output tokens; safely rejected | 36.12 s |

These are small engineering diagnostics with exact captured source context, not clinical validation or calibrated accuracy rates. Generated outputs and displayed fallbacks are adjudicated separately. The new CI wording check would reject the saved GLM numeric and follow-up finals; their original recorded status is preserved rather than rewritten.

The current asthma broad answer spent approximately 18.02 s drafting and 9.54 s revising, versus 0.037 s retrieving. Longer instructions doubled the three-question median while worsening accuracy. Keep model work as the latency focus; do not remove revision safeguards or optimize retrieval latency at the expense of evidence coverage.

**No candidate writer or model was promoted.** Live defaults remain Llama, 1,800 output tokens, the existing production instructions, 9,000-neuron daily ceiling and 100-answer alert. The safeguards and refresh/versioning changes are retained. Deployment and satisfactory general conversational quality remain open.

## Verification

- Complete backend suite: **396 passed**, 6.29 s, with two existing websockets deprecation warnings. The first restricted-sandbox run failed only on localhost socket binding; the subsequent permitted full runs passed.
- Browser smoke on the actual refreshed asthma workspace: Evidence/Sources show 10 records (5 PubMed, 5 registry), including NCT00545844. Source inspection renders details/passages and original-source links. Ask input and filters load. No captured console errors or failed requests; duplicate development GETs returned 200. No Ask was submitted during this smoke.
- Local API and frontend restored on ports 8000/3001. Existing answer/brief hashes remain unchanged. Browser verification checks the shell and refreshed evidence; isolated hosted runs supply the inference observations.
- Every hosted evaluation records production-store isolation, frozen-source/context hashes, prompt/code fingerprints and quota status. All recorded isolation checks passed. The latest 31 October run reported 689.881354 neurons used or reserved out of 9,000, with 8,310.118646 remaining and 11 provider requests. The incomplete high-effort request retains its conservative reservation (`pending=1`); it is not a running inference. Other Cloudflare account activity is outside this ledger's visibility. No limits or failed reservations were cleared.

## Next experiments, in order

1. Evaluate a compact claim-to-source fact review within the existing two-call budget. Review numerical clauses, units, source-specific sample sizes, missingness and causal language against their exact source passages before accepting final prose. Compare against the frozen baseline; prompt length and model size alone did not solve this.
2. Use the frozen real add-on trial across broad, numerical and simplification questions as an attribution stress test. A successful response must retain changed denominators and the before/after limitation through follow-ups. Include review subgroup estimates so overall review enrollment cannot substitute for estimate-specific enrollment.
3. Only after those gates pass, run the separate fresh-PubMed contradiction case and the four complete-packet questions, then an actual browser Ask and deployment checks. The fresh-PubMed contradiction case was authored but remains unexecuted; do not claim it passed.

Detailed observations, artifact/context hashes and current CI-check results are in `docs/functional-results/chat-refresh-adjudication-2026-10-31.json`. Raw answer artifacts are under `apps/api/evaluation/answer_coverage/results/`; timing/isolation/quota records are under `docs/performance/results/`. The earlier 29 October report describes the earlier UTC-day quota and packet results, not the new day's allowance.
