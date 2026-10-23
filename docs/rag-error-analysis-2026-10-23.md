# RAG error analysis — 23 October 2026

The first hosted run fails its answer-quality promotion gate because it omits important qualifiers. Most omissions occur during generation, but the real broad question also exposes a retrieval-intent failure. Fixing only the prompt would leave that failure in place.

This is source-backed engineering review, pending independent biomedical expert review. It is not clinical validation. Inputs and original observations remain unchanged: `apps/api/evaluation/m0/inventory.json`, frozen snapshots, `cloudflare-first-answers.json` and `cloudflare-first-adjudication.json`.

## Method and boundaries

Read all 18 retained answers, adjudications and the relevant frozen passages before selecting a retrieval metric. Replayed retrieval and the current context builder deterministically against frozen data, using the retained preceding answer for follow-ups. Provider completion was replaced with an in-memory capture function and an explicit abstention; the usage ledger was replaced with a no-op. No model, HTTP provider, production store, credential or production usage counter was used.

The old run did not save provider messages. Reconstructed contexts use current context code, including the previously repaired truncation flag; they are not claimed to be byte-identical historical traces. Retrieved chunk IDs were checked directly against the retained answers before changing retrieval.

## Error separation

| Cases | Evidence present in reconstructed generator context | Failure and responsible stage |
| --- | --- | --- |
| `numerical-hba1c`, `numerical-simplify` | Entire 340-character EVAL-NUMBERS excerpt: 240 adults; 0.5 percentage-point endpoint difference versus placebo at 12 weeks; 95% CI 0.2–0.8 points lower; mortality explicitly not measured; later effects not established. | Generation omits adults and interval, repeats nearly identical wording on simplification. The endpoint wording must not imply a within-group baseline fall. |
| `addon-hba1c`, `addon-fasting-glucose` | Entire 659-character EVAL-ADDON excerpt: 180 adults with type 2 diabetes, continued stable metformin, intervention A versus placebo add-on, 24 weeks; HbA1c −0.8 versus −0.3 percentage points (difference −0.5); fasting glucose −24 versus −6 mg/dL (difference −18). | Generation retains numerical values but drops adults/time; fasting-glucose answer also drops the background regimen. These are not chunking misses. |
| `pediatric-floor` | Entire 6,294-character standalone tablet excerpt, including indication at text offset 74: adjunct to diet and exercise, adults and pediatric patients aged 10 and older with type 2 diabetes. Required indication passage is the first retrieved chunk. | Generation drops adjunct condition and repeats minimum age instead of supplying missing context. |
| `combination-add-on` | 10,000-character prefix of a longer label. The supplied excerpt contains the add-on-to-insulin table: 24 weeks at offset 8,017 and comparator value 8.2 at offset 8,607. The table is also the second retrieved chunk (`m0-combination-full` snapshot). | Generation drops the placebo + metformin + insulin comparator and time window despite their availability. Do not imply this is metformin monotherapy or pooled fixed-product efficacy. |
| `real-broad`, `real-simplify` | Before the retrieval fix, two standalone FDA-label records remain after combination exclusion: 6,131 and 6,294 characters, including indication, common GI reactions and relevant warnings. | Both stages: narrow label-heavy retrieval excludes other evidence types; generation still drops diet/exercise and safety/population context that is available. Follow-up must recheck sources rather than inherit omissions. |
| `filtered-followup` | Entire 159-character permitted PubMed excerpt: synthetic 80-adult trial, 2-point difference versus placebo at 6 weeks. Excluded registry source is absent. | Generation turns absence of longer-term detail into an unbounded statement that later effects are not established. Say the supplied excerpt cannot establish them. Source filtering itself works here. |

Other retained cases demonstrate useful guard behavior: unresolved comparator clarification, refusal of an individual treatment decision, protocol/results distinction, voluntary-report frequency limitations and combination identity. Preserve those behaviors while improving coverage. The first run's 9 supported / 9 partially supported verdicts and zero recorded critical inventions remain historical engineering observations, not an accuracy guarantee.

## Narrow retrieval repair and measurement

`Retriever.retrieve_conversation` recognized benefits together with safety/risks/harms/side effects, but omitted the common word “limitations.” Therefore the exact real broad question bypassed the existing dual-intent, source-diverse retrieval route. Added `limitations?` to that intent test; preserved ranking, source filters, maximum eight returned chunks and all narrow-question behavior.

For the exact frozen real-broad query:

| Measurement | Before (retained trace) | After (deterministic replay) |
| --- | --- | --- |
| Returned passages | 8 | 8 |
| Distinct sources | 3 | 7 |
| Source types | FDA labels only | FDA labels, PubMed, trial registry |
| Combination-label passages | 5 | 1 |
| Distinct remaining sources after excluding combination label | 2 | 6 |
| Recall@8 for two manually relevant standalone passages | 1/2 | 2/2 |

The small manually curated relevant set is `m0-real-chunk-006` (standalone indication, age floor, adjunct condition) and `m0-real-chunk-019` (standalone trial GI safety context), both from `m0-real-source-07`. Recall@8 here measures this one coverage requirement, not corpus-wide retrieval accuracy. Both remain available after excluding ZITUVIMET.

More types do not automatically mean better biomedical evidence. Additional sources include prediabetes prevention uptake, other interventions and trial plans. They may explain gaps or study context; they must not become proof of a metformin monotherapy benefit. Do not enforce a quota of source types in final citations. Establish relevance first, then cite distinct relevant evidence where available.

Regression coverage uses both a controlled long-label/short-completed-trial example with two benefits-and-limitations phrasings and this frozen real-workspace passage set. It also verifies source filters, duplicate avoidance and the eight-passage bound. Command: `apps/api/.venv/bin/python -m pytest apps/api/tests/test_retrieval_coverage.py apps/api/tests/test_rag.py apps/api/tests/test_m0_fixtures.py -q` — **24 passed**.

## Recommended generation experiment

Make a concise general instruction apply to both draft and revision: preserve each selected finding as a complete comparison, with its population, treatment/background regimen, comparator, outcome/unit and observation window whenever supplied. Retain uncertainty intervals when explaining a quantitative effect; never invent missing qualifiers. Keep trial findings separate from indication language, and retain adjunct diet/exercise when stating an indication. This is a semantic coverage requirement, not a fixed response template or a request to reproduce every statistic.

Ask the revision to repair missing necessary qualifiers before shortening. Its current preference for 1–2 paragraphs and 100–180 words can compete with the broader “preserve” instruction. Permit enough space for the actual question, and remove repeated caveats before removing population/comparison context. When a user asks for a simpler answer, change vocabulary and explain the endpoint in ordinary language while retaining the underlying constraints.

Bound negative claims explicitly to the supplied study/excerpt. “This excerpt reports six weeks, so it cannot tell us about longer-term effects” is faithful; “effects beyond six weeks are not established” can imply a global literature conclusion. An explicit “not measured” statement may be preserved only when the source actually says so.

Run the known failed cases first, preserving outputs and provider costs, then run all 18 frozen cases with actual generated predecessor answers. Review relevance and each claim/qualifier independently from schema/citation validity. Do not tune chunk size, add embeddings, add a model stage or relax citation safeguards unless the resulting trace demonstrates a remaining retrieval failure.

## Ground-truth cautions

The inventory does not explicitly make a confidence interval mandatory in every numerical response. The adjudication reasonably flags its omission when assessing explanatory completeness, but should not silently turn every absent interval into a critical factual error. Population and comparison/timeframe omissions already justify the relevant failures. Apply claim-level entailment rather than exact word matching.

The real-broad requirement asks for relevant distinct sources “when available.” Its heterogeneous snapshot does not establish that every source type supplies relevant metformin treatment results. A good answer can explain why a registry plan or observational uptake paper does not quantify the requested treatment effect; it need not cite unrelated material to pass a diversity count.

Synthetic disclosure currently appears in generation metadata even where it is missing from the direct response. Review both, but improving the response should make that context intelligible to anyone reading or exporting the answer independently. A follow-up must not acquire permission to use prior generated text as evidence.

## Separate provenance issue

The old answer object contains extraction-stage supporting fields even after replacing its main response with generated text. `source_readouts` can therefore say “CITED” for an excluded ZITUVIMET label or for a generated abstention with no citations. This is a server-owned attribution defect, distinct from retrieval recall and model faithfulness. Final-answer provenance must follow accepted citations; any retained retrieval/extraction material must be explicitly labeled as such. Do not describe citation membership as a verified claim-level entailment judgment.
