# Label scope experiment and population guard

## Decision

Add the narrow pediatric indication guard; keep the source-clause writer experiment inactive. General chat is not ready for the layout gate. A syntactically accepted answer is not necessarily a complete or accurate answer.

## Changes

`triallens/label_checks.py` finds complete indication sentences only in retained FDA label context, preserving exact character offsets and text hashes. It does not infer immediate-release formulation, ingredients, contraindications or populations from an absent statement.

The production final-answer validator now rejects a positive pediatric-use assertion if it omits a numeric age floor explicitly present in a cited indication clause. An unrelated matching number is insufficient. This prevents the previously accepted broad “adults and children” answer from dropping the age-10 boundary. There is no added provider call or model change. Rejected generation uses the existing source-excerpt fallback and does not increment the successful-answer count; completed inference still consumes provider allowance.

This is a targeted guard, not medical entailment validation. It does not establish pediatric contraindications, validate adult-only scopes, check all age phrasings, or validate uncertainty prose. Unrecognized or negative/unknown statements remain outside its scope. It can reject otherwise valid paraphrases whose age boundary it cannot recognize.

The optional evaluation flag `--label-scope` adds source-specific complete indication clauses with citation, offsets, retained-text location and hash. It adds narrow revision signals and rejects retained age/pooling signals. Stored sources, original passages, production prompts, model and request limits are unchanged. No production code imports evaluation modules.

## Measurements and adjudication

The compact diagnostic uses three verbatim indication sections from the frozen public-label snapshot, totaling 1,753 source characters. Its inventory records original snapshot hash and exact excerpt offsets. It is deliberately easier than full-context synthesis: a focused indication question and shorter evidence. It does not assess broad risk synthesis or prove the source-clause representation improves answers.

| Run | Local HTTP wall time | Actual provider calls | Review |
| --- | --- | --- | --- |
| Compact control, existing v6 prompt and default Llama | 24.59 s | 2 | Direct answer separates unqualified tablets, age 10 and older, adult extended-release indication and adult combination indication. No quantified efficacy invented. |
| Same compact evidence/question/model/prompt, source-clause candidate | 27.54 s | 2 | Main answer retains age boundary and product distinctions. **Not a quality pass:** uncertainty broadens the combination's pancreatitis-history gap to “these products” and changes its focus to effectiveness. No demonstrated benefit over control. |
| Independent numerical comparison holdout, v6 with numeric checks | 14.78 s | 2 | Direct answer preserves 0.5 percentage-point between-group difference, adults/placebo/12 weeks and synthetic-data attribution. **Incomplete:** revision drops the supplied 95% CI, 0.2–0.8 percentage points lower, despite the request for uncertainty. The draft contained it. |

The production guard was added after these measured runs. An offline regression now rejects the older full-context canary's age loss and accepts the compact answers' age wording; acceptance does not validate their other claims. The measured experiment implementation is archived as `measured_label_scope.py.txt`, and its hash matches the candidate artifact. Current experiment hashes also include its shared production helper.

Answer/context/provider traces: [control](../apps/api/evaluation/answer_coverage/results/label-scope-control-2026-11-01.json), [candidate](../apps/api/evaluation/answer_coverage/results/label-scope-candidate-2026-11-01.json), [numerical holdout](../apps/api/evaluation/answer_coverage/results/label-scope-numeric-holdout-2026-11-01.json). Corresponding HTTP timings are in `docs/performance/results/`.

Final evaluation ledger after these runs: 8,125.692182 neurons used/reserved of 9,000, 874.307818 remaining, 33 reserved requests, two prior conservative pending reservations retained. Six hosted calls were added, costing 722.167106 recorded neurons. No quota increase, paid provider, local GPU, extra repair call or model promotion occurred. Stop further large hosted runs until reset.

## Verification and next work

546 backend tests pass; two existing websockets deprecation warnings remain. New tests cover exact complete spans, fragment rejection, decimal punctuation, non-label exclusion, duplicate passages, offsets, context restoration after provider failure, the historical age-loss answer, unrelated numeric values, alternative medicine/age, valid and unknown wording, and the two-pass production guard's success/fallback accounting. `git diff --check` passes.

Expect browser regression after restarting the updated API with `.env`: the original asthma count question and simpler follow-up both returned HTTP 200, the correct counts/denominators and nonrandomized limitation, explicit no-inference status and an inspectable NCT00545844 citation. Source inspection opened successfully; no console errors were captured. Testing added answers but changed no sources, reviews or brief.

Next: add a coverage plan that identifies requested evidence fields before drafting and carries them into revision. The revision must preserve relevant supplied uncertainty bounds, denominators and population boundaries rather than remove them while correcting wording. Scope uncertainty statements to the same product/outcome as the underlying evidence. Test coverage checks independently from unsupported-number checks: a response can contain no invented numbers and still omit the crucial ones.

After quota reset, first rerun the original full-context formulation/population canary and the CI holdout with the new coverage experiment. Then test the complete five-case cohort, real PubMed contradictory-narrative case and posted mean outcome. Do not treat this compact diagnostic or the new rejection guard as evidence that the layout gate has passed.
