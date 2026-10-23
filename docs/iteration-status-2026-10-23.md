# TrialLens iteration — 23 October 2026

## Decision

The functional repairs below are suitable to retain. **Answer-quality promotion and design progression are not approved yet.** Hosted candidate prompts improved some coverage but introduced material comparison errors; production instructions remain byte-for-byte the preceding baseline. The goal remains active. No deployment or aesthetic changes were made.

## Functional repairs

- Broad “benefits and limitations” questions now use the existing dual-intent retrieval route. In the frozen real query, the two manually relevant standalone indication/safety passages both reach the top eight (previously one did). Source diversity is contextual coverage, not proof of relevant treatment benefit.
- Accepted conversational answers rebuild ancillary provenance from their final citations. Context-only records no longer inherit an extractive answer’s `CITED` status or confidence judgments; excluded combination-product sources are removed from retained context. Abstentions and deterministic guards clear stale support claims. Citation identity checks remain explicitly distinct from claim verification.
- Repeated CLI experiments share a persistent evaluation-only SQLite ledger. Production stores and answer counters remain isolated. A `--prompt-file` candidate is temporarily applied and restored even on errors, allowing failed experiments to stay separate from production behavior. Public-fixture draft/revision text is retained for error analysis; credentials and response headers are not captured.
- Quantitative excerpt fallback now recognizes measured endpoint differences and units such as percentage points, mmHg and mg/dL. It preserves the supplied comparison instead of falsely claiming no statistics. Planned endpoints, dose-only text and sample sizes alone remain insufficient; the fallback does not turn endpoint differences into baseline changes. Twelve regressions cover these boundaries, including the frozen follow-up API path with a mocked quota failure.

## Hosted evidence, including failures

All calls used the explicitly configured Cloudflare model; there were no paid-provider fallbacks or local GPU model calls. The frozen inventory and historical baseline artifacts were preserved.

| Experiment | Result | Decision |
| --- | --- | --- |
| Expanded qualifier instructions, focused eight cases | 5 supported / 3 partial; two conversational generations rejected, and one overgeneralized multi-trial duration limitation | Failed; retained |
| One broad-question diagnostic | Rejected copied indication; draft/revision retention exposed a timeframe borrowed from a different outcome | Failed; retained |
| Expanded instructions with paraphrasing, full 18 cases | 16 generated answers + 2 deterministic guards; 13 supported / 5 partial; two critical comparison errors | Failed; production prompt restored |
| Isolated concise candidate, three selected cases | Two generated answers; numerical follow-up revision blocked before its request by conservative quota reservation | Incomplete and failed; not promoted |

The full candidate’s generated-answer median was **10.16 seconds**, p95 **25.34 seconds**. These are observed latencies for one small run, not a general performance guarantee. Engineering adjudication is source-backed but is neither independent biomedical expert review nor clinical validation.

The full run’s material errors were interpreting an endpoint group difference as a greater baseline reduction, and presenting a metformin-only hypoglycemia comparison alongside a different insulin add-on regimen. Follow-up safety coverage, actual simplification, requested numerical details and irrelevant content after abstention also need work. More supported verdicts do not compensate for these errors.

The evaluation ledger ended at **8,490.255 neurons used/reserved**, including a conservative 2,898.390-neuron carryover from earlier retained experiments. It has 509.745 nominal neurons left below its 9,000-neuron ceiling, but a complete two-pass answer can require a larger advance reservation; the last revision was therefore blocked without sending it. Do not reset the ledger or bypass reservations to continue testing. The provider’s account-wide free-plan allowance remains authoritative; other applications’ usage is not visible to this local ledger.

## Verification and limits

- Full backend suite after provenance, retrieval and evaluation-isolation changes: **187 passed**, two upstream deprecation warnings.
- A separate disposable **Python 3.11.15** environment passed the then-current 174 tests with pinned application dependencies; subsequent tests cover candidate-instruction restoration and the deterministic quantitative fallback repair. Existing local `.venv`, `.env` and research stores were untouched. The ordinary local runtime is still Python 3.9; the existing Docker runtime uses Python 3.11.
- `pip install ./apps/api` has a setuptools flat-layout discovery error. The existing deployment installs pinned requirements and copies source, so that packaging path is not a container blocker; packaging is not silently represented as verified.
- Final quantitative fallback regression evidence passed. **13/13 existing production-browser regressions passed in 15.2 seconds**, with no retries, using the isolated deterministic fixture API and no inference calls. An additional actual-API browser inspection confirmed final citation/context-only labels and verification limits. See [browser evidence](functional-browser-2026-10-23.md).
- Shared local prototype scope remains: no account/workspace ownership, no verified deployment host backup/restore, no clinical validation.

## Next experiments

1. Repair and verify the deterministic numerical fallback before spending more inference allowance.
2. Separate endpoint-difference language from baseline-change claims and prevent cross-regimen comparisons. Change one behavior per experiment and retain failed outputs.
3. Test follow-up preservation independently: simplify vocabulary while retaining benefit/safety scope and necessary population, comparator and time qualifiers. Do not force unrelated caveats merely to fill an uncertainty list.
4. Rerun affected cases and the complete frozen suite only when allowance permits. Promote only source-backed coverage with no material comparison errors, then start the prepared visual refinements.

The initial design audit is complete, with local before screenshots under `output/playwright/`. The user subsequently chose a **whole redesign: minimal research dashboard, improving clarity**. That supersedes the initial preserve-and-polish recommendation. Preserve product truth and functionality while replacing the visual composition. The audit’s task findings remain relevant: make the composer easier to reach, improve long-question typography, group Brief count/export actions, keep selected compact tabs visible and clarify retrieval scores. Implementation waits for the quality gate.

See [RAG error analysis](rag-error-analysis-2026-10-23.md), the immutable artifacts under `apps/api/evaluation/m0/results/`, and metrics under `docs/performance/results/`.
