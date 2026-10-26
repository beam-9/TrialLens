# Isolated prompt candidates

These files are retained experiments, not production instructions or approved answers. The frozen inventory/rubric are unchanged. Failed candidates must not be promoted because of schema validity, lower latency or a higher count of supported cases alone.

24 October results are summarized in `docs/chat-improvement-2026-10-24.md`. `comparison-examples.json`, `revision-coverage.json` and `conversation-focus.json` were evaluated and were **not promoted**. The first improved comparison wording but omitted required detail; later candidates introduced unsupported or false absence claims. Alternative Cloudflare models also failed quality/completion checks. Production instructions remain unchanged.

- `qualifiers-focused.json`: eight-case focused run and broad diagnostic. Reconstructed exactly by removing the subsequent paraphrase/outcome-association additions from the archived expanded candidate. It improved some qualifiers but produced rejected copied text and a multi-trial absence-scope error.
- `qualifiers-expanded.json`: full 18-case run under `cloudflare-qualifiers-final*.json`. The historical filename “final” means the final run of this iteration, **not approval**. Review found 13 supported/5 partial and two critical comparison errors.
- `concise-grounding.json`: candidate evaluated using `--prompt-file`; only two of three selected cases generated before the conservative quota blocked the follow-up revision. Numerical explanation still inferred baseline change and lost population context. It is not approved or fully evaluated.

The first two candidates were applied in a development process then reverted. Production `INSTRUCTIONS` and `REVISION_INSTRUCTIONS` match commit `bec138b`; the new CLI mechanism isolates future candidates and restores them on errors.

Example, only when free allowance permits (choose unused output names):

```sh
apps/api/.venv/bin/python apps/api/evaluation/cloudflare_run.py \
  --prompt-file apps/api/evaluation/prompts/concise-grounding.json \
  --output /private/tmp/triallens-new-metrics.json \
  --answers /private/tmp/triallens-new-answers.json \
  --case numerical-hba1c --case numerical-simplify
```

The CLI's persistent evaluation ledger defaults to ignored `apps/api/data/evaluation-usage.sqlite3`. Do not delete/reset it to bypass daily reservations. Provider-account quota applies across applications and ledgers. A draft completed before a blocked revision is retained for diagnosis but is never displayed as an accepted generated answer. No local GPU or paid-provider fallback is used.

`comparison-examples.json` preserves the baseline evidence rules while adding controlled wording examples of endpoint levels versus baseline changes and independent trial settings. Its examples are demonstrations, never evidence or facts to reuse. Its six-case evaluation is retained but does not clear the quality gate. Registry status/phase/date context is supplied separately by the application.

`--cases-file evaluation/m0/holdout-questions-2026-10-24.json` evaluates separately authored questions against the same hash-checked source snapshots, without editing the original inventory. `--model-experiment` supports only the explicit Cloudflare allowlist in the runner, with model-specific rates and the same daily ledger. Model/rate/output-limit overrides are restored even on errors. These switches are standalone evaluation controls, not production configuration or automatic fallback. Check current official model availability/rates before another run.

For a no-inference check of retained outputs, use `evaluation/replay_validation.py` with `--input` pointing to a retained paired-response artifact and `--output` to a new JSON path. It seeds hash-checked frozen fixtures and the original predecessor answers, mocks each recorded candidate through the actual Ask validation path, blocks provider HTTP and disables usage writes. It restores process globals afterward. Its acceptance counts measure deterministic safeguards only; they neither adjudicate claims nor measure a single-pass strategy's latency.

New hosted evaluation artifacts also retain `generation_context`: the exact public fixture evidence/topic/history/question object sent to the provider, plus the SHA-256 of its serialized request text. Both passes must use the same context hash. A null context means no provider request reached that evaluation seam (for example a guard or a pre-request quota rejection). Capture is confined to the isolated frozen-fixture runner; it never records authentication headers, credentials or production research history. Earlier artifacts are unchanged and are not backfilled from reconstructed contexts.

## Evidence-strategy experiments (25 October)

`--strategy-experiment verified-quotes` first requests citation-bound source passages, verifies exact membership, then writes an answer with the full original context retained. Initially any invalid quote rejected the whole selection; the retained updated experiment discards individual invalid quotes and rejects a nonempty plan if none can be verified. The final writer still promoted registry background into findings. It is **not approved**.

`--strategy-experiment reviewed-claims` drafts atomic claims, constrains citation IDs to supplied records, then requests a separate source-quote review. It renders only approved original draft words, without allowing replacement prose. Later necessary filters reject lost preclinical/case-report scope, unsourced rarity and numeric tokens absent from the review quote. These checks are not entailment proof. Retained runs include false-positive approvals, incomplete coverage and a wrong overall range; later offline post-filter observations are not new model runs. **No strategy is enabled in production.**

Experimental schemas, instructions and deterministic filters are in `evaluation/evidence_plan.py`; each hosted result pins that module hash. Source context remains identical across the two calls. Strategy validation failures stop an evaluation run instead of spending the remaining allowance on the next case. Existing final citation/copy guards still apply. Qwen3.8 and Granite are explicit evaluation-only model options, using documented rates and the unchanged daily ledger; Qwen's low reasoning/named schema profile does not alter the production Llama default. Neither model cleared the quality gate.

Full findings: `docs/chat-grounding-iteration-2026-10-25.md`.
