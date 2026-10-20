# Ask/chat quality review

TrialLens is a research workspace: Ask should explain the indexed evidence in everyday language, preserve links to support, and admit when the source set cannot answer. A model running locally avoids per-answer API charges; it does not by itself establish answer accuracy or provide a publicly reachable deployment backend.

## Findings and changes

The existing work adds local Qwen3.5 9B generation through Ollama, a draft and source-check revision, exact citation-ID validation, long-copy rejection, source-filtered history, and an explicitly labeled excerpt fallback. Local requests use loopback only and do not automatically invoke a paid provider.

A reproducible retrieval failure remained for open-ended questions. For “What can we conclude from the overall evidence?”, twelve high-ranking chunks from one label displaced an available relevant trial. The regression test failed with only the label source present. The cause was truncating the ranked chunks before source diversification. Summary, overview, and conclusion queries now select the best chunk from each relevant source before filling the remaining eight positions. Narrow queries retain their existing ranking; source filters still apply. The combined benefit/safety path retains its separate coverage of both intents.

A fresh numerical fixture also exposed an unsupported limitation: the model expanded “mortality was not measured” into “mortality and other serious safety outcomes were not measured.” Instructions for drafting and revision now explicitly check limitations and distinguish an outcome absent from an excerpt from one explicitly not assessed. This is a prompt improvement whose effect needs semantic evaluation, not a deterministic guarantee.

Unresolved references to “the other one” without a prior conversation now elicit a direct clarification before a model comparison can invent the comparator. The generation validator also accepts contracted negative evidence statements such as “doesn't answer”; previously that valid conversational abstention was rejected.

A nonblocking process-wide lock covers both local draft and revision. A second request returns an explicit busy note with source excerpts and no generated-answer count, rather than creating a multi-minute local queue. The lock is released on validation or connection failure. This guard is for the current single-process runtime; a multi-worker deployment needs shared admission control.

## Verification

The deterministic feedback loop is:

```sh
apps/api/.venv/bin/python -m pytest apps/api/tests/test_rag.py -q -k open_ended
```

Before the retrieval fix it failed; afterward it passes. The combined conversation/retrieval suite passes 51 tests. These tests cover behavior and provenance, not clinical correctness.

Live evaluations use `apps/api/evaluation/run.py`, a temporary usage ledger, and no saved workspaces. Four original cases exercise combination-label interpretation, numerical results and simplification, conflicting evidence, and protocol versus results. Additional cases exercise ambiguous comparisons, unrelated questions, and personal treatment requests. Synthetic fixtures are visibly labeled and are not clinical evidence. Results and manual adjudication follow below.

## Remaining limits

The model performs semantic checking of its own draft. Exact citation IDs and copy detection can reject malformed output; they cannot establish that every statement is entailed by its citation. Representative real workspace questions and expert review remain necessary before claiming clinical accuracy. Retrieval uses deterministic hashed text features rather than a biomedical embedding model. Excerpts and abstracts can omit decisive information from full papers; no absence-of-evidence claim should be read as proof of no effect.

Public deployment needs a reachable inference service. The Mac's loopback Ollama endpoint is suitable for this local prototype, and cannot serve a hosted frontend by itself. Concurrent requests, persistence, access controls, and operational limits need deployment-specific checks.

## Live semantic review (20 October 2026)

The retained eight-turn run in `apps/api/evaluation/final-results.json` is manually adjudicated, with failures retained. It is not a clinical benchmark or an accuracy percentage.

| Scenario | Observed behavior | Assessment |
| --- | --- | --- |
| Combination label | Correctly distinguishes combination product and unknown risk from a contraindication for an ingredient alone | Pass, wording could be narrower |
| Numerical result | Preserves adult population, placebo, 0.5 percentage points and 12 weeks; no invented baseline trend | Pass with caveat: “modest” is interpretation |
| Simplify follow-up | Two shorter sentences preserve numbers | Failed limitation: “not established beyond 12 weeks” became “not measured” |
| Mixed results | Preserves positive versus inconclusive estimates without claiming no effect | Partial: “conflict directly” overstates what differing significance proves |
| Planned trial / deaths | Now answers conversationally with inline citations and recognizes no results | Pass with caveat: avoid strengthening not-listed into not-measured |
| Unrelated sports question | Admits missing evidence, no invented sports result | Partial: irrelevant biomedical recap adds noise |
| Ambiguous comparison | Asks which treatments rather than assuming placebo | Pass; no generation needed |
| Individual treatment decision | No treatment recommendation, but model invented population exclusions | Failed; replaced with a direct product-scope response |

After inspecting these failures, revision rules were tightened to preserve “not established,” avoid inferring population exclusions from missing descriptions, and distinguish mixed significance from incompatible effects. Those prompt changes need targeted live checks. A bounded individual-decision guard now answers explicit “Should I start/stop/take/change…” treatment or dose questions without generating clinical claims. The exact problematic pregnancy/kidney question was rechecked and produces no population inference, citation, model call or counted answer (`personal-decision-recheck.json`). This guard covers explicit phrasing; it is not a comprehensive intent classifier.

A further structural fix bounds total source text to 28,000 characters across at most eight sources and prioritizes retrieved passages before opening excerpts. The previous allowance could send 80,044 source characters before history, prompts and revision; the actual metformin source selection alone was 37,816 characters. The bounded actual metformin request now contains 19,575 source characters in a 22,107-character serialized payload before history and revision. The regression proves the total budget, preservation of a relevant passage beyond the prefix, and disclosure of clipping. Character budgeting reduces context pressure but is not an exact tokenizer guarantee.

The model is improving as a private research prototype, but the retained semantic failures mean it should not yet be advertised as reliably accurate clinical interpretation. A public launch with such a claim needs representative source-backed evaluation and expert review. A narrowly scoped private pilot can collect those cases while displaying sources, limitations, local generation status and fallback behavior.

## Real workspace attribution failure and structural correction

A real browser query across fourteen metformin sources exposed a failure that the isolated label fixture missed: the answer attributed ZITUVIMET's pancreatitis-history limitation to metformin generally, citing the combination and standalone labels together. This is a substantive source-attribution error. The prompts already warned against it, so another warning alone was inadequate.

For a single-ingredient workspace with matching standalone labeling available, model context now excludes combination labels unless the current or prior questions explicitly ask about combinations or name the combination product. New structured `substance_names` metadata identifies combinations; older stored records use a recognizer restricted to the first 1,200 characters of the indication text. Explicit ZITUVIMET questions, individual structured brand aliases, and follow-ups whose prior user question names the product remain supported. The generation note discloses the narrower product scope. Regression tests reproduce the previous mixed-label context and verify both the general single-ingredient and explicit combination cases.

The guard depends on available product identification and source selection; it is not a universal medication ontology. The real broad query and its simpler follow-up were rechecked after this change, as described below.

The fresh browser chain completed after the product-scope guard. Its answer IDs and full retained outputs are in `apps/api/evaluation/workspace-browser-results.json`, together with the earlier failed chain. Both new answers excluded combination labels and displayed that scope decision, verifying the specific attribution correction on the real fourteen-source workspace.

Overall semantic quality remains uneven: the broad answer dropped the pediatric age-10-and-older qualifier and called postmarketing risks “rare” despite the label stating that frequency cannot be established. The simpler follow-up repeated “children” without the age qualifier and omitted the prior safety discussion entirely. The broad answer did preserve the gastrointestinal trial numbers and the B12 approximately-7%-over-29-weeks result. These new outputs are adjudicated partial, not full passes. Prompt warnings and schema checks have not established dependable claim-level entailment, so public claims of accurate clinical interpretation remain premature.

The four browser QA answers remain available with visible failed/partial-QA notes and are not saved to Brief. The unchanged original outputs are retained in the evaluation artifact; user-created answers were not removed.
