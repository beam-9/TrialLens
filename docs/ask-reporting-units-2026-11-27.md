# TrialLens Ask reporting units — 27 November 2026

The evaluation ledger opened with 9,000 neurons and zero pending reservations. This experiment follows the [reviewed Ask plan](ask-quality-plan-2026-11-25.md). It tests whether smaller, server-owned source units help generation distinguish the two arm estimates in Results from the signed contrast in a caption. The same mechanism keeps a published correction separate from the original article. Previous whole-passage attribution still let the model omit requested facts or select a passage that contained the wrong result. See the [previous verification](ask-quality-reset-2026-11-25.md).

## Frozen acceptance criteria

Score each displayed answer against the exact context and source inventory. Record an absent required passage separately from an available but omitted fact. A passing rewrite requires a passing parent and preservation of the requested figures and limits. A provider fallback on answerable evidence fails the case.

| Cases | Required source-grounded details |
| --- | --- |
| ATOMIC Results and rewrite | Results paragraph 019 supplies the 16-week combination decrease of 0.58% ± 0.11% and atorvastatin-alone increase of 0.35% ± 0.11%. Figure 2A supplies the signed combination-minus-atorvastatin contrast of −0.94% with 95% CI −1.25 to −0.63, using least-squares mean percent change from baseline. Keep the Results magnitude separate from the caption contrast, keep the partial-index scope explicit, and avoid assigning an unreported dispersion type. |
| ATOMIC Figure 2A and mortality | The figure answer preserves measure, unit, group direction, estimate and interval. The mortality answer limits its conclusion to what the indexed outcomes establish. |
| STOIC corrected counts and rewrite | Give intention-to-treat usual care 11/73 versus budesonide 2/73 from the original trial. Give per-protocol usual care 10/70 versus budesonide 1/69 with direct attribution to PubMed:33864735, which corrected the summary. Identify the urgent-care composite including emergency department assessment or hospitalization. Distinguish the analysis populations and explain how open-label assignment could influence care-seeking or assessment. If the reversed denominators in the original Results body are visible and relevant, explain the discrepancy. |
| STOIC mortality | Distinguish the urgent-care composite from mortality and state the scoped lack of an established mortality effect. |

The candidate has to improve semantic coverage on both source families before broader testing. Correct citation formatting alone earns no credit. Production prompts, retrieval scope, safety checks, model and quota remain as shipped.

## Implementation and comparison

This measures reporting units together with the instructions needed to select them. The experiment does not isolate the effect of segmentation. Create `apps/api/evaluation/paper_reporting_units.py` and `apps/api/tests/test_paper_reporting_units.py`. Modify only `apps/api/evaluation/structured_attribution.py` and `apps/api/evaluation/answer_coverage/evaluate_quality.py` in the existing evaluation code. The helper splits already linked Results at recognized sentence starts and figure captions at unambiguous consecutive panel boundaries. Each start-inclusive, end-exclusive span has at most 2,000 characters and 12 literal dispersion or signed-interval anchors, with up to eight units per passage and 3,000 characters of duplicated exact support text per request. The catalog always retains offsets and source ownership after the support text budget is exhausted. The wrapper adds the versioned `REPORTING_UNIT_FORMAT` selection instructions. Oversized or ambiguous sections retain the whole-passage entry. Published errata stay intact and have an explicit correction role. The wrapper can render only the source that owns the selected support and still hands the answer to existing final validation.

For the matched control and candidate, use the unchanged provider, default prompts and the same frozen inventories. The control uses `--structured-attribution --passage-attribution`. The candidate adds `--reporting-units`. Next commands use the runner `apps/api/.venv/bin/python apps/api/evaluation/answer_coverage/evaluate_quality.py` with separate immutable `--output` and `--answers` names. The ATOMIC inventory is `apps/api/evaluation/cohorts/paper-captions-v2-2026-11-23/inventory.json`. The independent correction inventory is `apps/api/evaluation/cohorts/stoic-correction-2026-11-23/inventory.json`. Run every case in each inventory in order so the rewrite uses its own predecessor. Existing controls are `paper-passage-2026-11-25.json` and `stoic-passage-2026-11-25.json` under the answer and performance results directories. Check source hashes and compare exact evidence separately from per-run history. The stored controls include the optional draft-feedback difference in the later code revision. A comparison using them is diagnostic, and exact paired qualification requires a fresh control on the same build.

Execute the phases in this order:

1. Wire the opt-in helper and CLI. The default and whole-passage modes must continue to run with the new helper disabled.
2. Run `apps/api/.venv/bin/python -m pytest apps/api/tests -q` with isolated loopback permitted. Require the full suite to pass before candidate qualification.
3. Preserve all candidate and same-build control captures. Run the cohorts sequentially under the existing Free reservation check. Stop and record any provider or approval blocker.
4. Adjudicate displayed answers against frozen obligations before deciding promotion. Use the supplied context to distinguish missing retrieval, omission, incorrect support and unsupported interpretation.

Offline checks cover precise reconstruction and ownership of each selected span, separate arm dispersion and signed interval supports, panel boundaries, intact errata, oversize/ambiguous fallback including more than eight units, more than twelve anchors and no recognized numeric anchor, and rejection of a percentage unsupported by its selected unit. The full API suite also checks the two-call limit, quota, restoration, and production validators. A fresh reported answer qualifies only if it satisfies every known requested fact in the frozen rubric, introduces no critical error, and both parent and rewrite independently pass. Broader holdouts remain required for release.

## First candidate outcome

The reporting-unit candidate passed one of seven displayed cases, the scoped STOIC mortality answer. Both cohorts completed using 14 hosted calls and 2,576.10 evaluation neurons.

- The ATOMIC Results and figure turns had the required evidence. The model selected the abstract or a Methods passage instead of the Results and Figure 2A supports. Offline replays reproduced the passage-level percentage rejections. The Results response omitted both dispersion terms and paired an unsigned magnitude with negative interval bounds.
- The ATOMIC rewrite recovered both ± terms. Its parent fell back and the rewrite context lacked the caption interval. The mortality draft had the right scoped conclusion, but its final formatted response attached unattributed uncertainty to a no-citation answer and was rejected.
- Both STOIC turns received the correction and supporting trial passages. The parent omitted the denominators, correction citation, and open-label limitation. The rewrite also lost the per-protocol analysis. Keeping the correction separately owned did not make the model select it.

An initial request to run the historical asthma baseline was blocked by automatic approval review due to the external payload concern. Those bytes were not sent. The separately reviewed hosted runs used only the three public PubMed records and authored questions in the two hash-verified paper fixtures.

## Offline typed-rendering control

The separate `apps/api/evaluation/atomic_reporting_oracle.py` control uses hand-transcribed typed facts and requires the exact frozen snapshot hash, unique ownership, and exact selected Results and Figure 2A text. It rejects changed or absent support, including the caption missing from the captured fallback-parent rewrite. The offline Ask integration uses those rendered facts as a mocked provider response. Both the Results parent and the genuine rewrite passed the existing validators, preserving the two ± terms, signed interval and partial scope. The passing parent also made the caption available to normal rewrite retrieval.

The control is an upper-bound diagnostic for rendering and retrieval given a faithful parent. It has no production or hosted entry point. It does not test automatic extraction from arbitrary articles and earned no hosted semantic pass.

## Matched control and review

The same-build whole-passage control completed all seven cases. The seven generation evidence arrays matched the candidate arrays exactly before catalog construction. Each rewrite received its own parent. The control passed zero of seven cases. It reproduced the ATOMIC Results, figure and mortality fallbacks, and its rewrite assigned an 8-week arm value to 16 weeks. In STOIC, the parent and rewrite omitted denominators and correction attribution and substituted early stopping for the open-label caveat. The mortality turn fell back. The reporting-unit improvement from zero to one pass came from the STOIC mortality turn. This does not satisfy the required improvement in numerical reporting and correction coverage.

The EGM follow-on review used fresh-context implementation-readiness and codebase reviewers. It identified confounded attribution of gains, missing execution details, incomplete file action labels and missing cap/fallback checks. The plan now records the combined intervention, matched control, stable phases, exact file actions and boundary tests. The fifth checkpoint found no material open issue. The review reached its round cap with one clean final checkpoint. The previously converged parent plan remains the release gate.

The complete API suite passed 753 tests, with two existing websocket deprecation warnings. Production routing and generation are unchanged.

The existing coverage prompt combined with reporting units still produced two ATOMIC fallbacks. The raw parent recovered both ± terms, selected the wrong support, and again linked an unsigned magnitude to negative bounds. The raw rewrite retained the ± terms but had a fallback parent and lacked the caption interval. Neither displayed answer passed. The local ledger ended at 5,751.37 neurons used or reserved with no pending reservations. All five hosted captures verified isolation from production stores. Deployment qualification remains open.
