# Answer coverage benchmark

This is a small, deterministic, manually adjudicated benchmark for whether answers cover useful facts already present in supplied context. It targets overly brief answers that omit requested statistics, population/comparator/time qualifiers, safety tradeoffs, explanation, and follow-up continuity.

All records are authored synthetic engineering controls. They are not clinical evidence, do not represent real studies or products, and must never be presented as factual medical claims. No external inference or network access is needed.

`inventory.json` is the source of truth. Each case separates:

- `retrieval_relevant_source_ids`: exact source IDs needed; measure retrieval coverage against these independently.
- `required_facts`: answer-level semantic facts, each linked to a supporting source and an exact passage. Their completeness is a human rubric, not string matching.
- `forbidden_interpretations`: material errors to reject even when other facts are covered.
- `rubric`: relevance/coverage/faithfulness checks, including follow-up requirements where applicable.

Run `apps/api/.venv/bin/python apps/api/evaluation/answer_coverage/benchmark.py` from the repository root (or pass the inventory path). It validates inventory shape and passage/source links and prints case/category counts plus retrieval targets. The cases are divided before the context comparison in `splits.json`. After the production context helper lands, run `apps/api/.venv/bin/python apps/api/evaluation/answer_coverage/context_compare.py --split development` or `--split holdout` to compare first-eight baseline context with helper-selected context. This offline runner makes no model calls. For answer quality, supply generated answers to a human adjudicator using the rubric. Report retrieval recall separately from semantic coverage, faithfulness, and relevance.

Fourteen authored cases are a diagnostic set, not a representative sample or a basis for a clinical accuracy percentage. Expand and review with realistic user questions before release claims.

## Frozen offline context comparison

The 14 cases were partitioned 9 development / 5 holdout before running the context comparison. Corrected results are retained as `results/development-corrected.json` and `results/holdout-corrected.json`; they represent one deterministic run of the current local retrieval and context helper. No model was called. The earlier `development.json` and `holdout.json` outputs are preserved as superseded observations: their indexing attribution and baseline context reconstruction were flawed, so use only the `*-corrected.json` results below.

The corrected baseline passes the original first eight eligible input sources through the same production evidence-record builder as the helper candidate. This retains the builder's per-source and aggregate text budgets, matched passages, and truncation behavior. Passage indexing is checked against chunks from that exact source ID; context membership is checked against only that source's record text and matched passages.

- Development: first-eight baseline and ranked helper each included all 19/19 required passages; no passage was unindexed or omitted from selected context.
- Holdout: baseline included 8/10 required passages; ranked helper included 10/10. The difference came from `later_relevant_source`, whose required source is ninth in input order. Both approaches had 0 unindexed required passages; baseline omitted 2 from selected context and helper omitted 0.

This measures source/context availability only. It does not measure whether a model notices, correctly explains, or cites those passages, and it does not establish general performance outside these authored fixtures.

## Inactive answering and results-ingestion experiments

`../prompts/answer-completeness.json` and `answer-completeness-v2.json` are isolated evaluation candidates, not production instructions. Hosted outputs use the unchanged frozen M0 evidence via `hosted-cases.json`; generated answers were not stored in production workspaces. Technical acceptance is not a semantic pass.

`trial_results_candidate.py` is an inactive conservative formatter, tested with synthetic API-shaped records. It retains outcome, unit, timeframe, group identity, denominators and measurement/analysis context without calculation. Entire oversized or invalid outcomes are omitted and disclosed. A public NCT01563029 payload probe omitted all eight outcomes at the 1,200-character complete-outcome limit, so this prototype is deliberately **not integrated** into source ingestion. The next parser experiment must package complete numerical records without losing their group/denominator context; raising a limit alone is insufficient because ordinary chunking/context budgets can split the records again.

## 29 October: retained complete outcome packets

The inactive 1,200-character prototype remains frozen for the failed experiment. Production now uses `triallens/trial_results.py` with bounded complete 8,000-character outcome packets preserved through chunking and context allocation. The frozen public payload yields eight complete packets; the four-case `packet-cohort-2026-10-29` comparison distinguishes protocol-only content from measured results. Existing workspaces are not migrated. See `docs/chat-quality-2026-10-29.md` for measured findings, current limitations, rejected writer/model profiles, and accounting. The new source-role HTTP tests are separate from the earlier helper-only source-order control. The fresh-PubMed contradiction holdout remains unexecuted.

## 4 November: randomization coverage

The opt-in `--ci-coverage` experiment now asks revision to retain the cited randomized participant count when one source supplies a single interval and explicitly describes the assignment. The checker abstains when counts conflict or a passage describes assignment to a single arm. These pattern checks verify selected details and require source adjudication for overall answer quality.

The frozen four-case run used the default hosted model, the v6 candidate prompt and numeric checks. Compared with the November 3 numerical pair, both answers now retain the random assignment of 240 adults across the two groups. Both keep the reported 12-week comparison, confidence interval and synthetic-data label. The simpler follow-up repeats the finding and is longer than the first answer. The safety answer omits the trial denominators, the nausea/vomiting comparison and the limit on causal inference from postmarketing reports. The protocol case falls back after the model abbreviates its citation ID. The experiment stays opt-in.

The recorded numerical answers were replayed against the narrower participant-count matcher after the hosted run. It found the same count in both inputs and accepted both recorded answers. The single-arm rejection is covered by a regression test. See [captured answers and inputs](results/ci-design-coverage-2026-11-04.json) and [timing and usage](../../../../docs/performance/results/ci-design-coverage-2026-11-04.json).

## 4 November: default chat citation and revision changes

The default validator restores an omitted source prefix only for an exact, unique, nonnumeric external ID in the supplied context. The inline markers and citation list still have to agree after normalization. The captured protocol answers already used full IDs. The repair itself is verified separately with mocked responses and ambiguous ID checks.

Two four-case runs used the default chat prompts without experiment flags. The second revision added specific guidance for randomized counts and protocol details. All four final responses passed the production validator. Against the frozen sources:

- The numerical answers retained the comparison, interval and 240 adults randomized. The follow-up was 48 words versus 58 for the first direct answer. Demo attribution was in the uncertainty field and answer note.
- The protocol answer supplied the planned placebo comparison, 200 adults and symptom score at 16 weeks. It separated those plans from recruitment and result status and noted mortality was outside the listed outcomes.
- The safety answer supplied both denominators and both requested event comparisons. It explained the frequency limitation for voluntary postmarketing reports. The first run also explained the causal limitation, which the second run omitted. The second answer could distinguish observed trial rates from rates among all users more explicitly.

These are sampled cases. See [first run](results/chat-scope-2026-11-04.json) and [second run](results/chat-scope-v2-2026-11-04.json).

## 6 November: broader answer-quality checks

Needs revision before release. The run covered 13 distinct questions across five general holdouts, four public registry questions, one public PubMed question and three boundary questions. Repeated diagnostic runs are kept separately. Technical acceptance is recorded independently from source-based assessment.

| Reviewed question or scope | Source-based assessment |
| --- | --- |
| Combined label indications and limitations | Needs revision. The baseline revision removed safety information present in its draft and omitted requested registry-role distinctions. A candidate preserved common adverse reactions but still omitted serious warnings and other requested detail. |
| Numerical adverse reactions and voluntary reports | Reported trial percentages and denominators match the supplied label. Frequency limitations were explained. The causal-inference limit was omitted, so coverage remains incomplete. |
| Synthetic numerical comparison and simpler follow-up | Correct numerical comparison, interval, adult population, randomization and timeframe in the baseline. Demo attribution was present in the uncertainty field and UI generation note. |
| Synthetic protocol versus measured results | Correct planned comparison, symptom outcome, enrollment, timeframe and status. Mortality was outside the listed outcomes. Demo attribution was present outside the direct answer. |
| Public protocol-only numerical request | Correctly scoped the missing measured result to the supplied protocol. Its PM endpoint description differs from the posted results' PRIMARY AM endpoint. |
| Public posted primary PEF result | Correct FF50 and placebo mean changes, analyzed sizes and ANCOVA contrast. Independent review verified the complete source packet and snapshot hash. |
| Public result simplification | Baseline incorrectly described analyzed outcome group sizes as randomized counts. After revision guidance, the follow-up kept the reported contrast and interval without that assignment claim. |
| Unsupported public mortality outcome | Correctly said the supplied measurements do not establish a mortality benefit. A numeric-only uncertainty entry in the baseline was removed by the production cleanup. |
| Public ATOMIC abstract comparison | Needs revision. Both hosted attempts reversed the HbA1c numerical pair. The second added the LDL-C result but still failed the requested discrepancy explanation. A new final validation guard rejects those recorded reversed comparisons for explicit discrepancy questions. |
| Unrelated football question | Correctly said the indexed evidence cannot answer it. |
| Ambiguous comparison | Asked the user to name the treatments with no inference call. |
| Individual treatment decision | Returned the research-assistance boundary with no inference call. |

### Source verification and repairs

The public primary PEF packet reports FF50 change22.8 and placebo3.3 L/min, analyzed n118 and119, contrast19.5 L/min and 95% CI12.1–26.9. These are from outcome001, groups OG002 and OG000. The trial's secondary outcomes and pooled FF50/FF100 analysis contain different values and cannot replace this comparison. The analyzed denominators do not establish random allocation counts.

The ATOMIC abstract reports the pair “0.35% vs. -0.58%, respectively” and an LDL-C pair of -55.20% versus -7.69%. Its narrative interpretation and HbA1c wording require explicit qualification. Source authority alone does not resolve that internal wording. The broad numerical-order guard runs only when the question explicitly asks about a discrepancy, examines each cited source, and rejects reversal when the two percentage values each occur once in the paragraph. It does not verify group identities, handle every number format or prove entailment. It can conservatively reject a valid reordered explanation. Both observed reversed answers are rejected in regression checks, including through the normal final-validation path.

Production revision guidance now preserves requested coverage and distinguishes analyzed participants from randomized enrollment. Numeric-only and citation-only uncertainty fragments are removed after citation validation. Unknown citations still fail validation. The larger `coverage-preserving-v1.json` profile remains an inactive experiment.

### Evidence and limits

- Baselines [general](results/broad-default-2026-11-06.json), [posted trial](results/broad-posted-results-2026-11-06.json), [PubMed](results/broad-pubmed-2026-11-06.json) and [boundaries](results/broad-boundaries-2026-11-06.json).
- Rechecks [posted trial](results/broad-posted-recheck-2026-11-06.json), [PubMed](results/broad-pubmed-recheck-2026-11-06.json) and [inactive coverage candidate](results/broad-coverage-candidate-2026-11-06.json). Matching timing and quota artifacts are under `docs/performance/results/`.
- Expect browser QA of the actual asthma workspace passed for the zero-inference count answer, simpler follow-up and original-source inspection. Both asks returned HTTP200 with no console errors. Test answers were added, with no source, review or brief edits.
- The source-order guard was added after the hosted PubMed attempts. Its prevention result comes from regression replay and mocked provider integration. Remaining open-ended synthesis requires further evaluation.
- Final evaluation ledger for this round records 6,616.251717 neurons used/reserved, 2,383.748283 remaining and40 requests. No pending reservations remain. No paid inference or local GPU was used.

Next work should address complete multi-source synthesis and faithful numerical group attribution. Preserve the tested safety boundaries and explicit fallbacks while those gaps are resolved. These samples do not establish an overall accuracy percentage.

## 6 November: numeric validation and single-pass writer experiments

The native medium-reasoning writer preserved the disputed HbA1c pair and explained the numerical/narrative conflict. Two numeric-check defects initially obscured its performance. A nonbreaking hyphen before a negative number was read as a positive value, and the source's written “one hundred eighty-five” did not support the answer's 185. Normalization now recognizes leading typographic hyphens while preserving ranges and identifiers. The evaluation checker recognizes complete spelled-out hundreds, skipping larger-number and decimal fragments. Regression replay no longer flags those recorded percentages or the sample size as unreported. This removes false validation failures; it does not verify the answers' meanings.

Source review still found issues. The first native answer omitted requested study-size/proportion details. The scoped candidate included them but attributed AMPK activation to the 2017 review, whose supplied text does not mention it. The source-specific qualification gate remains open.

The explicit `--single-pass` experiment tests one provider response through the existing final validators. The service's revision timer represents an in-memory replay, and the metadata labels that distinction. The wrapper verifies the replay context and rejects changes without making another provider call. This experiment cannot be combined with revision/repair experiments. It is inactive in production.

The five-case native trial processed four cases before stopping on an incomplete protocol response. Its combined answer retained more requested material, but described unqualified tablets as immediate-release. Its safety answer invented a ≤45% range where the source says ≤5%. The numerical case failed final validation, including a missing paragraph citation and a shift from percentage points to percent. The protocol request exhausted its bounded output allowance. The follow-up case was not executed. The lower-cost GLM single-pass attribution request also reached its output cap and returned incomplete output. Neither writer was promoted.

A production percentage check now rejects a value absent from the paragraph's cited source context. It accepts recognized percent/per-cent wording, ranges and negative signs. For several citations it checks their combined reported values when each source contains recognized percentage figures. It does not establish which group or endpoint owns a value and skips sources without recognized percentage figures. This conservative check may reject legitimate rounded or derived figures; the answering instructions require reported values. Regression replay rejected the observed invented 45% while accepting the reviewed default and posted-result samples. Mocked generation tests verify the final acceptance/rejection path.

Artifacts and captured input contexts are [native medium](results/attribution-native-medium-2026-11-06.json), [native scoped](results/attribution-native-scoped-2026-11-06.json), [native single-pass](results/native-single-pass-2026-11-06.json) and [GLM single-pass](results/attribution-glm-single-2026-11-06.json), with matching timing/quota artifacts under `docs/performance/results/`. The numeric checker and replay wrapper were tightened after the hosted runs and their affected behavior rechecked offline.

The evaluation ledger ends this iteration at 8,567.708879 neurons used/reserved, 432.291121 remaining and49 requests. Two conservative reservations remain for failed provider responses. No further large hosted runs are justified under this day's cap. Multi-source completeness, reliable source-specific attribution, and a fully qualified writer are still required before declaring chat complete.
