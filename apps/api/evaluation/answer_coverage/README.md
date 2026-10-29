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
