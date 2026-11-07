# EGM installation and first TrialLens chat pass

## Installation and workflow verification

Installed and enabled the complete `egm@egm` plugin, version **0.1.1**, from
`https://github.com/google/elephant-goldfish-model`. The installed marketplace
snapshot is `e9e1f06aa4e26e95cd4ed37210a0632202c429e9`. Native
`codex plugin list --marketplace egm --json` reports `installed: true` and
`enabled: true`. Reviewer personas and document standards are present with the
skills. This is a Codex development workflow, not a TrialLens inference provider.

The package's `tests/unit` checks passed using its pinned pytest/PyYAML
dependencies in a temporary Python 3.12 environment. Two optional Copilot/Cursor
probes were skipped by their documented environment conditions. The first check
with TrialLens's Python 3.9 could not collect four plugin test modules because
they use newer type-annotation syntax. No TrialLens dependencies were changed.
Package tests do not prove every native EGM workflow or editor integration.

Applied the installed **egm-drift-report** workflow to the root README in
`apps/api/evaluation/answer_coverage`. A fresh native subagent received the
installed workflow/integration paths, target and explicit source reading list,
without this conversation transcript. It reported completed required reads.
Host instruction-file exclusion was not independently verified.

The [drift report](../2026-11-07_DRIFT_REPORT.md) identifies an obsolete
instruction saying to wait for the production context helper to land. Source
inspection and retained corrected comparisons show it already exists. Removed
that obsolete condition. The source/rubric inventory check still validates all
14 authored controls. This fixes documentation, not answer completeness.

## Same-model comparison after quota reset

Both runs used the normal Llama model, frozen M0 evidence and the same question:
what sources directly establish about intended use and limitations, separating
label claims from registry background/plans and keeping combination claims scoped.
The exact captured generation-context hashes match. Production stores were
isolated and the existing shared evaluation ledger and cap were preserved.

| Profile | Provider calls | Wall time | Neurons used | Outcome |
| --- | ---: | ---: | ---: | --- |
| Current draft/revision writer | 2 | 21.88 s | 504.345356 | Accepted technically; incomplete coverage |
| Inactive coverage-plan experiment | 1 | 57.20 s | 426.286685 | Plan rejected before writing |

The baseline accurately preserves the tablet indication's age floor and scopes
the type-1 limitation to ZITUVIMET. It also gives supported common adverse
reactions. It omits requested registry-role distinctions and meaningful serious
safety context. The adult extended-release formulation is not distinguished;
this is a coverage/precision issue, not an observed false age claim. Its generic
duration limitation does not explain the more relevant gap between a label's
indication and a quantified benefit. The needed label/registry material was in
the captured context, so these omissions are not established retrieval misses.

The planner returns six parts with 15 selected quotes. Offline replay through
the actual validator raises `Coverage support budget exceeded` (maximum 12
quotes); the captured trace confirms a validation fallback after one provider
call and no writing call. `response_shape.parse_error: null` means only that
the provider envelope parsed; it does not mean the plan passed validation.

Independent source adjudication also found that the plan adds comparison and
prevention topics without covering the explicitly requested registry role. A
prescribing-trend quote is assigned to **PubMed:42374733**, whose captured text
concerns clonal hematopoiesis. The quote belongs to **PubMed:42373540**. The exact
own-source quote check would reject that selection too, after the budget issue.
Increasing the quote limit or silently repairing attribution is not justified.

The independent reviewer read the exact question rubric and captured contexts,
then the authoritative timing trace and validator source. Its own validator
replay could not import pydantic under its chosen interpreter; the primary
agent separately executed the replay with TrialLens's virtual environment and
confirmed the rejection. Neither review establishes general clinical accuracy.

## Evidence and next design work

- [Baseline answer and context](../apps/api/evaluation/answer_coverage/results/egm-baseline-combined-2026-11-07.json),
  [baseline timing](performance/results/egm-baseline-combined-2026-11-07.json).
- [Planner response and context](../apps/api/evaluation/answer_coverage/results/egm-planner-combined-2026-11-07.json),
  [planner timing](performance/results/egm-planner-combined-2026-11-07.json).

No candidate is promoted. The next design review needs to explain how requested
parts stay complete without expanding into unasked topics, and how evidence
selection preserves source identity. It must account for the failed quote/claim
strategies already retained in the repository. Source membership, self-reported
coverage maps and successful JSON parsing are necessary checks, not entailment
or relevance verification. EGM's gated design-review workflow can challenge the
concrete next proposal before implementation; that full review loop has not
been run or claimed here.

The day's ledger records **930.632041 neurons used**, **8069.367959 remaining**,
three requests and no pending reservations. No paid API, local GPU inference,
quota increase or production-model change was used. Chat remains unqualified
for completion.
