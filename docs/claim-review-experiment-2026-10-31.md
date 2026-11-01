# TrialLens claim-to-source experiment — 31 October 2026

## Outcome

The experiment improved retention of real trial counts and exposed a missing source-data field, but did **not** establish satisfactory general chat quality. The repaired-claims writer and alternate models remain evaluation-only. The production change retained from this round is explicit, bounded registry study-design grounding.

The final numerical tests retain baseline 312/313 uncontrolled, 0 controlled and 1 missing assessment, versus week-8 72/301 uncontrolled, 229 controlled and 0 missing, without introducing calculated percentages. Earlier versions lost denominators or added rates. The strongest paired follow-up keeps key counts and a causal limitation now supported by explicit registry metadata. Other answers still omit requested qualifications or fail to simplify; these are not full release-gate passes.

## Experiment and iterations

The existing two-call budget is preserved. The first call drafts independent prose claims. The second can repair each claim, select same-source support and discard unsupported material. Server checks preserve original citation ownership, require every draft index once, verify passage membership and numerical coverage, and catch explicit cm-versus-cm/year conflicts. Original final citation, confidence-interval, copy and incomplete-response safeguards remain active. No extra model calls, paid fallback or local GPU inference were added.

Free-form support quotes failed because the model returned short or incomplete excerpts. Code-generated, bounded exact passages with IDs resolved that transport problem. A subsequent schema change required explicit claim indices and exact review cardinality. A real check bug treated NCT identifier digits as outcome values, dropping a valid denominator sentence; identifiers are now checked separately for source identity. Mechanical pre-review warnings flag unreported numeric tokens and unit conflicts so the reviewer can remove unsupported clauses while retaining sourced counts.

These checks are necessary conditions, **not entailment proof**. A model can select genuine text and still apply a p-value to the wrong outcome, alter product scope or omit the main limitation. Some partial answers still pass structural validation. No production writer was promoted on that basis.

## Measured observations

Ten saved runs cover 16 Ask attempts and 32 provider calls across several explicitly recorded versions. Twelve attempts returned technically validated model answers and four returned excerpt fallbacks; technical status does not imply semantic accuracy. All recorded production-store isolation checks passed.

| Saved comparison | Result | Median wall time |
| --- | --- | --- |
| Initial repair canary | No accepted claims; malformed/insufficient support | 19.29 s |
| Anchored Llama canary | Core figures retained, but demo/n and clarity gaps | 11.29 s |
| Indexed GLM real statistics/follow-up | Some added counts/design context, but cross-outcome significance error and lost follow-up limitation | 12.53 s |
| Indexed GPT-OSS real statistics/follow-up | Correct categories, then denominator/numeric clauses lost to checks | 15.03 s |
| GPT-OSS after ID fix and numerical warnings, same pair | Counts and denominators retained; no invented rates; source-wide design claims still inadequately grounded | 14.41 s |
| Paired explicit-design diagnostic, four questions | Metadata reaches model and supports one follow-up's causal caveat; initial answer can still omit that caveat | 7.77 s |

The paired diagnostic uses one public trial with versus without design metadata. It is a different source cohort from the earlier multi-source asthma workspace, so its lower latency is not evidence of an optimization speedup. Provider caching/residency is unknown. The general five-case attempt stopped after the **first** case hit validation; the other four cases were not executed in that run. The separate fresh-PubMed contradiction case remains unexecuted.

## Retained source-grounding improvement

ClinicalTrials.gov's public NCT00545844 record explicitly reports INTERVENTIONAL, NON_RANDOMIZED, SINGLE_GROUP, masking NONE and registered enrollment 313 ACTUAL. Previously TrialLens kept phase and outcome packets but omitted these design fields, encouraging inference from visit labels alone. The new parser indexes only present, bounded registry values and forwards them in the cited record even if a design chunk was not retrieved. Registered enrollment is explicitly distinguished from outcome analysis denominators. Missing fields and allocation N/A never become invented no-control claims. See the [official registry API](https://clinicaltrials.gov/api/v2/studies/NCT00545844) and [API documentation](https://clinicaltrials.gov/data-api/api).

Original M0 and prior source snapshots remain unchanged. A new paired public-source cohort and reproducible builder are under `apps/api/evaluation/answer_coverage/design-cohort-2026-10-31/` and `build_design_cohort.py`.

## Actual workspace and verification

- **438 backend tests passed** in 7.23 seconds, with two existing websockets deprecation warnings. Tests cover exact/foreign support, whole-index coverage, native Responses support capture, wrong numbers/units, identifier handling, sparse/malformed design fields, N/A allocation, registry enrollment limits and metadata reaching model context without a matching chunk.
- After a private permission-restricted backup, the existing asthma workspace was refreshed using the normal ingestion endpoint. The limited search returned a different five-trial set and dropped the previously useful NCT00545844 record. That record was directly revalidated from the public API and retained alongside the new results. The workspace has **11 sources/rows: five PubMed and six registry studies**, with design metadata for all six trials and all six posted outcome sections retained for NCT00545844.
- All saved answers and briefs retain their pre-refresh hashes. Previous evidence/review versions remain archived. Private data and backups are excluded from Git.
- Browser verification loaded the 11-source workspace, inspected NCT00545844's explicit design section and original-source link, and confirmed Ask input remains available. No browser Ask was submitted; inference observations come from isolated evaluations.
- The local API was restarted with source-design grounding. Live inference remains the existing Llama profile, 1,800 output tokens, 9,000-neuron ceiling and 100-answer alert. The latest evaluation ledger recorded 4,704.668430 neurons used/reserved of 9,000, leaving 4,295.331570, with 43 total requests including earlier work. One previous incomplete-response reservation remains pending; it is not running inference. Caps/reservations were not cleared. Other Cloudflare account activity is outside this ledger's visibility.

## Remaining work

1. Bind numeric claims to a particular outcome and its analysis, not merely a matching passage from the same source. The primary-category/secondary-ACQ p-value mistake is a concrete regression case.
2. Require useful requested coverage after rejected/repaired claims: denominator, population, treatment, comparison, uncertainty and relevant limitation. Current structural checks can leave an accurate but unhelpful partial answer; accept/reject must account for that loss.
3. Separate revalidation of known workspace records from discovery search. Search windows can churn; the direct retention above was an explicit one-time repair, not a general fix. A future blind refresh can drop a previously useful record again.
4. After those gates pass, rerun broad/formulation safety cases, the fresh-PubMed contradiction case and complete posted-result questions before any writer activation or deployment.

Raw outputs, exact contexts, model/profile settings, timing and source/code hashes are retained under the usual evaluation/results paths. `docs/functional-results/claim-repair-adjudication-2026-10-31.json` records the per-case engineering findings and limits. This small authored diagnostic is not clinical validation or a calibrated accuracy estimate.
