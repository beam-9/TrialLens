# Isolated prompt candidates

These files are retained experiments, not production instructions or approved answers. The frozen inventory/rubric are unchanged. Failed candidates must not be promoted because of schema validity, lower latency or a higher count of supported cases alone.

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

`comparison-examples.json` is the next **unexecuted, unapproved** candidate. It preserves the baseline evidence rules while adding explicit controlled examples of endpoint levels versus baseline changes and of independent trial settings. Its examples are wording demonstrations, never evidence or facts to reuse. Registry status/phase/date context is now supplied separately by the application. Run focused cases first when the persistent allowance permits; do not promote from offline syntax checks.

For a no-inference check of retained outputs, use `evaluation/replay_validation.py` with `--input` pointing to a retained paired-response artifact and `--output` to a new JSON path. It seeds hash-checked frozen fixtures and the original predecessor answers, mocks each recorded candidate through the actual Ask validation path, blocks provider HTTP and disables usage writes. It restores process globals afterward. Its acceptance counts measure deterministic safeguards only; they neither adjudicate claims nor measure a single-pass strategy's latency.

New hosted evaluation artifacts also retain `generation_context`: the exact public fixture evidence/topic/history/question object sent to the provider, plus the SHA-256 of its serialized request text. Both passes must use the same context hash. A null context means no provider request reached that evaluation seam (for example a guard or a pre-request quota rejection). Capture is confined to the isolated frozen-fixture runner; it never records authentication headers, credentials or production research history. Earlier artifacts are unchanged and are not backfilled from reconstructed contexts.
