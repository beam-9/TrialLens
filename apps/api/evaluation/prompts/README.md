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
