# Local generation evaluation

Run from the repository root:

```sh
TRIALLENS_LOCAL_MODEL=qwen3.5:9b apps/api/.venv/bin/python apps/api/evaluation/run.py
```

Use `--case combination_label` to investigate one failure and `--output /tmp/results.json` to retain results. Ollama must be running and the selected model downloaded. The runner forces the local provider, uses a temporary usage ledger, and never saves a workspace. It does not load the application's `.env` or require a paid key.

The combination-label excerpt comes from the development workspace's ZITUVIMET label record. Other cases are deliberately synthetic evaluation fixtures, not clinical evidence. Their purpose is to check whether numbers, uncertainty, comparison arms, and trial status survive generation. Each result includes explicit semantic criteria for manual review.

A conversational response means only that output validation passed. Read every answer and limitation against the supplied sources, record a pass/fail for each criterion, and retain failures. Do not turn this tiny diagnostic set into a claimed clinical accuracy rate. Recheck realistic workspace questions too: short fixtures cannot represent retrieval noise, full context, or the product's complete behavior.


Retained runs include early failed baselines, the manually adjudicated eight-turn fixture run (`final-results.json`), and actual before/after browser chains (`workspace-browser-results.json`). The latter verifies the combination-label scope fix while retaining residual age, frequency and follow-up omissions. These files describe particular model/code revisions; do not treat old outputs as a fresh run of the current configuration.
