# Broader chat quality review — 6 November 2026

Chat is still being qualified. This iteration adds a source-based review and an
inactive coverage experiment. It does not promote a new model or change the
production answer pipeline.

## Evidence reviewed

An independent review rechecked 12 captured responses: five general questions,
three posted-trial questions, one PubMed synthesis question and three boundary
questions. Inputs were the `broad-default`, `broad-posted-recheck`,
`broad-pubmed-recheck` and `broad-boundaries` artifacts dated 2026-11-06 under
`apps/api/evaluation/answer_coverage/results/`. The review compared each question,
answer and uncertainty against the exact captured generation context. These are
reassessments of existing runs, not 12 new hosted generations or a representative
clinical validation sample.

Separately, an offline replay applied the current confidence-interval,
requested-comparison-order and percentage-presence checks to all dated captured
conversational outputs with evidence context. The
`offline-wording-replay-2026-11-06.json` artifact retains input file hashes,
validator/helper hashes, answer/context fingerprints and per-output results.

| Replay observation | Count |
| --- | ---: |
| Captured answer files | 11 |
| Conversational outputs checked | 22 |
| Outputs excluded (no evidence context or not conversational) | 7 |
| Historical outputs flagged | 3 |
| Reversed source-pair outputs | 2 |
| Unreported percentage outputs | 1 |
| Confidence-interval wording flags | 0 |

Repeated diagnostic outputs are separate observations, not independent questions.
The three flags reproduce known problems in the two PubMed rechecks and the
native single-pass safety answer. Absence of a flag does not establish correct
group attribution, numerical units, complete coverage or scientific entailment.
No model calls were made for this replay.

## Findings and their importance

The firm synthesis problems remain the combined-use/safety answer losing
requested safety and registry-role distinctions, and the ATOMIC answer reversing
the reported HbA1c pair rather than describing the source's ambiguous wording.
The ATOMIC recheck also omits the reported 0.94% contrast and 62%/15% proportions
while the question asks for numerical changes. The captured context contains
these figures, so this is a generation coverage problem. More numbers alone
would not fix the incorrect attribution or resolve the source's ambiguity.

The review found additional precision and usability opportunities:

- The synthetic simpler follow-up repeats the numerical answer verbatim. Its
  original is already short and accurate, so repetition alone is not a release
  blocker. It offers little additional explanation.
- The posted PEF answers retain the requested changes, analyzed denominators,
  contrast and confidence interval. Including children aged 5–11 with persistent
  uncontrolled asthma and clarifying that the endpoint averages daily AM PEF
  across the treatment period would better preserve applicability and endpoint
  meaning. Those details were not explicitly requested, so their absence is not
  graded as a critical error for these particular questions.
- The numerical safety answer gives a substantial supported adverse-event table
  and explains the frequency limit of voluntary reports. The additional 6%
  diarrhea discontinuation figure and approximately 7% vitamin-B12 observation
  over 29 weeks are relevant optional additions, not mandatory exhaustive-number
  coverage. The previously documented causal-inference qualification is still
  worth preserving when describing voluntary reports.
- The protocol and three boundary answers had no additional material finding
  in this review. This is a limited observation, not proof of general reliability.

Available evidence, written coverage and source attribution are evaluated
separately. None of these observations supports an overall accuracy percentage.

## Inactive next experiment: plan each requested part before writing

`apps/api/evaluation/coverage_plan.py` implements an opt-in `coverage-plan`
strategy in the existing isolated evaluation runner. It replaces the two normal
provider calls with planning and writing; it adds no third call or provider
fallback. Production does not import or enable it.

The first call identifies requested question parts and selects bounded exact
quotes from each quote's own source. It lists selected numerical values required
for those parts. Offline checks reject fabricated quotes, wrong-source quotes,
unreported required values, blank/duplicate parts and oversized support plans.
The second call writes ordinary prose and maps each planned part to answer
paragraphs. Checks reject omitted map entries, missing selected citations and
dropped required values within that part's cited paragraphs. Internal mapping
metadata is removed before the normal production final validators run.

Both calls receive the same original source/history context. The wrapper rejects
context/replay mismatches and restores provider state on errors. The evaluation
captures the plan with either chat or native Responses envelopes and hashes its
fixed prompt/check implementation. A separate `--prompt-file` is rejected for
this strategy because it would otherwise be silently ignored.

These checks cannot prove that the plan identified all requested parts, that its
quotes are relevant, that the selected numerical requirements are sufficient, or
that a mapped paragraph answers its part with the right group, unit and meaning.
Values appearing under the same citation can still belong to different outcomes.
Gaps require human assessment against partial-source scope. The experiment may
also increase output length, cost or latency, or hit the bounded output cap. No
hosted performance or answer-quality improvement is claimed yet.

## Qualification still required

The shared evaluation ledger remains at 8,567.708879 neurons used/reserved,
432.291121 remaining, 49 requests and two retained failed-request reservations.
This iteration spends no hosted inference allowance, raises no cap and uses no
paid API or local GPU. The remaining allowance does not justify another large
cohort run.

After the normal quota reset, run a small baseline/candidate comparison on the
combined benefits/safety question, numerical follow-up and public ATOMIC
question. Then evaluate the broader frozen M0 and public posted-result cohorts,
including previously unused questions. Keep source snapshots, request limits and
final safeguards fixed. Review every requested part, group/unit/denominator,
source-specific attribution, uncertainty and conversational usefulness; report
fallback rates, latency and actual quota alongside quality. Promote only after
those checks show a repeatable improvement without material new errors.

Automated verification for this implementation includes the normal service
acceptance/fallback path and isolated HTTP evaluation with mocked inference.
It does not substitute for the outstanding hosted and semantic qualification.

Validation: `apps/api/.venv/bin/python -m pytest apps/api/tests -q` passed
598 tests, with two existing websockets deprecation warnings. `git diff --check`
also passed. Localhost integration tests required sandbox escalation; all model
responses in those tests were mocked and used temporary ledgers/stores.
