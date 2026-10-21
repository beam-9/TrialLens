# Ask baseline — M0

**Status: LOCAL BASELINE; M0 acceptance remains incomplete.** Measurements taken 20 October 2026 Vancouver / 21 October UTC. Baseline commit `031ff95daa553d874a8c2ef36ab7b18ec96e0e0f`; initially clean checkout. No candidate configuration has been selected or benchmarked, and M1/M2 have not begun.

The requested instrumentation and frozen evaluation infrastructure are implemented. One cold and twelve warm two-pass attempts completed, meeting the minimum timing sample. The full 18-turn suite stopped after 15 completed turns because system swap continued growing. Three turns remain incomplete/unrun. This report preserves that failure rather than declaring M0 finished.

## Changes and invariants

- `apps/api/triallens/performance.py`: request-scoped monotonic ASGI telemetry, **off by default**. Set `TRIALLENS_PERF_TELEMETRY=1` to emit one structured JSON record per Ask. Optional `TRIALLENS_PERF_MODEL_DIGEST` supplies trusted deployment metadata; absent metadata remains null. No model probe is added per request.
- `main.py` and `conversation.py`: clocks around storage reads, retrieval, extractive fallback synthesis, context construction, draft, revision, validation and persistence; provider final-response usage captured separately for each pass. Distinguishes busy, guards, model answer, validation fallback, provider errors and observed disconnect/cancellation. Disconnect detection is limited to events ASGI actually observes; a browser disconnect does not necessarily cancel a synchronous worker.
- `apps/api/evaluation/m0/`: hash-checked public-source snapshots, 18 ordered question turns, passage-backed expectations, adjudication rubric, isolated real-HTTP benchmark and retained outputs. No migration or product response field was added.
- Prompts, model, context/answer limits, two-pass strategy, source selection, citations, validation, lock behavior and usage accounting are unchanged. Local failure still cannot invoke a paid fallback.

Routine telemetry contains numeric timings/counts, non-sensitive trace IDs and bounded operational metadata, **not** questions, prompts, source text, history, answers, exception messages or credentials. Raw answers exist only in the explicitly identified public-fixture evaluation artifact. Missing provider counters remain null; zero counts remain zero. Duration fields labeled `_ns` are nanoseconds. `serialization_ms` spans route completion to ASGI completion, not browser paint or network transit.

The benchmark configures an explicit INFO handler. A flag-alone default-logging emission fix was added after the benchmark imported telemetry; its clocks and captured records were already working. The recorded instrumentation fingerprint identifies the measured code. Subsequent metadata-only hardening also ignores malformed usage values. Neither change alters prompts, payloads or measured normal-response pipeline behavior.

## Executed path and environment

All six source documents requested by the handoff were found under `docs/` and inspected, alongside the current implementation and retained failures. [Path audit](path-audit.md) traces browser click → asynchronous Next proxy → FastAPI synchronous threadpool → retrieval/context → two blocking Ollama calls → validation/SQLite accounting → atomic JSON persistence → serialization → browser JSON/React display.

Native Ollama **0.32.14**, Apple **M2 Pro / 16 GiB**, macOS **26.5.2 arm64**. Model `qwen3.5:9b`, 9.7B parameters, **Q4_K_M**; digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`. Loaded `ollama ps` actually reported **100% GPU**, 5.7 GB, context 16384. This is a residency report, not measured GPU utilization. Exact samples: [environment.json](environment.json).

Existing request settings: `temperature=0`, `think=false`, `stream=false`, `num_ctx=16384`, `num_predict=1800`, `keep_alive=10m`; HTTPX timeout 180 seconds per operation/inactivity phase, not a strict total deadline. Next proxy timeout is 390 seconds. Existing native launcher already enabled single parallel generation, Flash Attention and q8_0 KV cache; these are not new optimization results. Source context remains capped at eight sources / 28,000 characters. Three history turns and revision/schema overhead consume additional tokens.

The local virtualenv actually runs **Python 3.9.6**, although `pyproject.toml` requires **>=3.11**. It was not upgraded during M0; verification on the declared runtime remains outstanding.

## Method and latency

Measurements use serial loopback HTTP through the real FastAPI Ask route, frozen public sources, a temporary JSON store and separate temporary SQLite ledger. No source refresh or live ingestion occurred. The provider destination is restricted to the exact local Ollama chat URL; `.env` is not loaded by the runner. Original workspace-store and usage-ledger hashes were verified unchanged after interruption.

Cold means this model was explicitly unloaded and the loaded-model list was empty. The native Ollama server and OS file caches were **not** restarted. Warm cases are heterogeneous, run once in fixed fixture order, with cache/history effects. The API boundary includes serialization; **browser click-to-paint and Next proxy latency were audited, not measured by this run**. The frozen store is about 0.5 MB, smaller than the developer store, so its storage timings do not establish production-scale performance.

| Group | Completed n | API p50 | API p95 | Outcome |
|---|---:|---:|---:|---|
| Cold two-pass | 1 | 65.230 s | 65.230 s | 1 model answer |
| Warm two-pass attempts | 12 | 26.458 s | 47.555 s | 11 model answers, 1 validation fallback |
| Deterministic guards | 2 | 0.022 s | 0.045 s | clarification and treatment guard |

Percentiles use nearest rank; the warm p95 is the largest observation in a small sample, not a stable service-level estimate. `model_answer` means structural checks passed, not factual correctness. The fallback is included in attempted two-pass latency but excluded from successful model answers. Restricting warm samples to the eleven model answers happens to give the same p50/p95. Interrupted request 16 has no completed trace and contributes no inferred latency/token count.

| Stage | Cold request | Warm aggregate across 12 attempts | Share of warm wall |
|---|---:|---:|---:|
| Storage reads | 5.486 ms | 91.301 ms | 0.027% |
| Retrieval | 11.513 ms | 33.000 ms | 0.010% |
| Extractive synthesis | 15.683 ms | 38.654 ms | 0.012% |
| Context building | 0.448 ms | 2.870 ms | <0.001% |
| Draft | 38.663 s | 189.726 s | 57.05% |
| Revision | 26.479 s | 142.324 s | 42.80% |
| Validation | 7.352 ms | 24.347 ms | 0.007% |
| Persistence | 21.996 ms | 258.598 ms | 0.078% |
| Total API wall | 65.230 s | 332.569 s | 100% |

The two model calls account for **99.84% of aggregate warm latency**. Revision is substantial, but draft consumes more time. The cold model calls report 6.122 seconds loading, 16.703 seconds prompt evaluation and 42.202 seconds decoding. Keeping a model warm alone cannot remove that warm decoding/prompt work. Phase shares use sums over the same observations; independent phase medians are not added together.

All **26 completed model calls** supplied usage metadata and ended `done=true, done_reason=stop`. Per-call input counts ranged **864–4696 tokens**, output **132–471 tokens**; summed provider input counts 58,933, output 5,974. These sums include repeated/cached prompts and are not billing or unique-evidence counts. Message-content lengths were 4,274–21,065 characters; serialized message lengths 4,442–21,388. Generation speed was **20.63–23.72 tokens/s**, median **22.35**. Reported prompt processing ranged 266.37–1922.88 tokens/s, median 537.75; cache reuse makes this unsuitable as an uncached hardware throughput claim.

Maximum observed final-response input plus actual output was **5067 tokens**, below 16384. The native log segment between cold unload and cleanup unload contained 27 slot records with `truncated=0`, zero nonzero truncation flags and no other truncation warning. It includes the interrupted native request. This is **no observed truncation**, not proof that all future contexts fit: pre-truncation token length is unknown, and the character budget is not a token guarantee.

Machine-readable per-request timing, counters, settings and summary: [baseline.json](results/baseline.json).

## Stop condition and cleanup

Pre-load system swap was **3837.56 MiB**. It rose to **7788.12 MiB**, including **1140 MiB over 149 seconds** after a temporary plateau; swapout counters also grew. Kernel pressure stayed at level 2 during loaded samples (no level 4 observed), while Activity Monitor's sampled pressure chart was green. These observations are retained separately. The loaded runner remained 100% GPU.

The handoff's “unbounded swap/offload” stop condition was applied conservatively to sustained growth without an observed stable plateau. This is not proof of mathematically unbounded growth, a memory leak or inference-only causality: other desktop applications were running. No unrelated applications were closed and no runtime settings were changed to bypass it.

SIGINT interrupted `addon-fasting-glucose` (turn 16). `filtered-first` and `filtered-followup` were not run. Completed records were already persisted. The HTTP client interruption left a sync worker active at the harness's five-second cleanup boundary, producing the explicit `Isolated worker still running` error; the harness refused to restore real store/provider references while that worker was active. The standalone process ended; original workspace and ledger hashes remained unchanged. This cancellation path is safe isolation but not graceful worker draining, and needs care before unattended long runs. Automatic protection currently rejects critical level-4 pressure; sustained-growth monitoring was independent/manual and remains necessary.

The model was unloaded to restore its initial state. Independent verification found `/api/ps` empty and kernel pressure back to **1**, wired memory about 2.76 GiB. Swap allocation still occupied 7578.31 MiB; allocation persisting after unload does not imply the model remains loaded. No further inference was attempted.

## Evidence quality

[Inventory](../../apps/api/evaluation/m0/inventory.json) freezes **18 turns / 9 snapshots**, including the retained fourteen-source metformin workspace and marked synthetic numerical/comparator controls. Original `final-results.json` and `workspace-browser-results.json` remain unchanged and hash-checked. [Rubric](../../apps/api/evaluation/m0/rubric.json) records support separately from critical errors; [answers](../../apps/api/evaluation/m0/results/baseline-answers.json) retain all fifteen completed outputs.

[Adjudication](../../apps/api/evaluation/m0/results/baseline-adjudication.json) compares every completed output to frozen source passages: **5 supported, 10 partially supported, 0 overall unsupported**, with **6 critical errors across 5 answers**. These are Codex engineering assessments **pending independent human/expert review**, not clinical validation or an accuracy percentage. Guards are among the supported cases. The two-pass same-model revision does not independently establish entailment.

| Case | Support | Critical / material finding |
|---|---|---|
| real-broad | Partial | Drops pediatric age >=10; calls unknown-frequency postmarketing risks “rare” |
| real-simplify | Partial | Again broadens pediatric population; loses prior safety limitations |
| combination-identity | Supported | Preserves combination-product identity |
| numerical-hba1c | Partial | Correct numbers; probability-like interpretation of confidence interval needs statistical review |
| numerical-simplify | Partial | Correct numbers; repeats probability-like confidence-interval interpretation |
| mixed-significance | Partial | Comparison nuance remains limited |
| protocol-deaths | Partial | Strengthens mortality not being a listed outcome into not measured/assessed |
| unrelated-question | Partial | Abstains but recaps unsupported scope of absent long-term evidence |
| ambiguous-followup | Supported | Clarifies without model call |
| personal-treatment | Supported | Personal decision guard without model call |
| pediatric-floor | Supported | Preserves age floor in isolated control |
| postmarketing-frequency | Partial | Validation fallback is labeled but indication excerpt does not answer frequency question |
| b12-time-window | Supported | Preserves approximately 7% and 29-week timeframe |
| combination-add-on | Partial | Correct 15.3% vs 8.2%/24-week figures, then incorrectly denies the metformin+insulin-background comparator |
| addon-hba1c | Partial | Preserves add-on comparator/endpoint; omits adult population context |

The fasting-glucose and source-filtered-history live checks remain **unverified** because their three turns did not complete. The age, frequency, absence-of-evidence and follow-up failures reproduce known baseline risks. The new frozen combination/add-on probe additionally exposes comparator-scope failure; no configuration change was made to cause or fix it. Existing ancillary fields can still label excluded ZITUVIMET evidence “CITED” or name it as a strongest row even when final answer citations exclude it. Existing `content_truncated` metadata can also reflect passage deduplication rather than actual short-source loss, leading to misleading “truncated abstract” caveats. These are documented M0 findings, left unchanged to keep the baseline interpretable.

## Acceptance and next experiments

| Gate | State |
|---|---|
| Existing-path audit, opt-in telemetry, frozen fixtures | Implemented |
| One cold + at least ten warm model attempts | Met (1 + 12; eleven warm model answers) |
| Full frozen suite | **Not met: 15/18 completed** |
| Independent human/expert adjudication | Pending |
| Stable sustained host memory profile | **Not established; conservative stop** |
| Product semantics/settings unchanged; paid calls zero | Preserved |
| M0 fully complete / M1 started | **No / No** |

Next three actions, in order:

1. **Resolve the baseline stop before more inference.** Agree a quiet-desktop native test session, retain this run, monitor swap/pressure, finish the three incomplete turns with predecessor history, and repeat representative cases to establish stability. Preserve failed outputs and obtain independent source review. Verify supported Python >=3.11 separately. Improve benchmark interruption/drain handling before unattended runs; measure actual browser/proxy overhead separately without conflating it with these API samples.
2. **After M0 closes, run M1 one variable at a time.** Compare current 16384 context with 12288 as a candidate, measuring actual draft/revision token headroom, truncation, memory and the same QA qualifiers. Smaller context is a hypothesis, not a promoted setting. The largest observed request is not the maximum permitted production context. Existing 10-minute residency already keeps these calls warm; longer keep-alive does not address measured warm decode time. A 600-token cap would not shorten these observed <=471-token outputs and could harm harder cases.
3. **After that gate, compare M2 strategies/models against the unchanged two-pass control.** Draft and revision both deserve measurement. Conditional revision or a smaller model needs repeated frozen-suite comparisons, independent review, zero new critical errors and 30+ finalist warm samples before promotion. Citation syntax alone cannot justify skipping revision. Retrieval replacement or database migration is not supported as the first latency intervention by this measured breakdown.

No deployment readiness is claimed. The existing app still needs host-specific access control, persistence/restore and failure-path verification for a trusted private pilot. **Paid inference API usage: $0** for this benchmark; hardware, electricity and hosting are separate costs.

## Reproduction and verification

From repository root, with the existing native model installed (do not resume inference until the stop condition is addressed):

```sh
apps/api/.venv/bin/python apps/api/evaluation/m0/benchmark.py \
  --output /tmp/triallens-m0-rerun.json --answers /tmp/triallens-m0-rerun-answers.json
```

Use fresh output paths to preserve retained results. Follow-up dependencies execute in inventory order; `--case` subsets must include their predecessor. The harness does not automatically validate sustained swap stability or unload the model after every run; monitor and explicitly verify cleanup. The interrupted baseline command ended with an isolation-cleanup error, not successful suite completion.

Final verification (no additional model inference):

| Check | Actual result |
|---|---|
| `cd apps/api && .venv/bin/python -m pytest tests -q` | **93 passed**, two upstream websockets deprecation warnings |
| `apps/api/.venv/bin/python -m pytest apps/api/tests/test_rag.py -q -k open_ended` | **1 passed**, 18 deselected |
| `cd apps/web && npm run lint` | Passed |
| `cd apps/web && npm run typecheck` | Passed |
| `cd apps/web && npm run build` | Passed |
| `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3002 npm run test:e2e` | **8 passed**, fresh production build, 10.7 seconds |
| `docker compose config --quiet` | Passed; packaging check only |
| `git diff --check` | Passed |

The backend includes 20 telemetry tests, three fixture-integrity tests and three benchmark tests. Tests cover missing/malformed usage, zero tokens, telemetry off/on contract equivalence, concurrency/lock release, provider exceptions, ASGI events and real-HTTP fixture isolation. Localhost socket verification needs permission to bind in restricted sandboxes. Browser regressions ran through the Expect tool; Ask responses were mocked and cover the success/error UI without further inference. The temporary production server was stopped, and `/api/ps` remained empty afterward. Deterministic/mock tests do not establish biomedical accuracy. Real local semantic observations are the fifteen retained outputs above; no native timeout/disconnect/busy stress run was added after the memory stop.
