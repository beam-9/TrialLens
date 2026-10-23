# Cloudflare first hosted evaluation

22 October 2026 (America/Vancouver). **Status: connected hosted candidate, not pilot verified.** User explicitly selected the hosted alternative to avoid native GPU load. Model `@cf/meta/llama-3.3-70b-instruct-fp8-fast`, unchanged draft + revision instructions, temperature 0, maximum 1800 output tokens per pass. Code baseline before evaluation: `345924d`.

## Connection and scope

The locally saved configuration passes the launcher check. One frozen numerical smoke case successfully completed both hosted passes in **9.345 seconds API wall**. The full frozen suite then completed **18/18 cases**: **16 model answers**, one clarification and one personal-treatment guard, **zero provider errors or excerpt fallbacks**. Structural acceptance does not imply factual correctness.

The runner (`apps/api/evaluation/cloudflare_run.py`) loads only hash-checked public evidence, invokes the real Ask route over loopback HTTP, and permits provider POSTs only to the configured Cloudflare model endpoint. It reuses the existing isolated HTTP/store seam, switches to Cloudflare before Ask, and never invokes native model metadata, load, unload or generation. No source refresh, user history or production usage counter participates. Real workspace-store and usage-file hashes were unchanged by evaluation. Credentials/account identifier are absent from result artifacts; `.env` remains Git-ignored with mode 600.

The provider's hosted residency and cache state are unknown. These results have **no claimed cold/warm classification**. Timing includes API storage/retrieval, HTTP model calls, validation, persistence and serialization; it does not measure browser click-to-paint. Source selection/prompt semantics were not tuned between these observations and the retained native baseline. Different models/tokenizers, dates and cache conditions limit causal interpretation.

## Latency

| Sample | n | API p50 | API p95 (nearest rank) |
|---|---:|---:|---:|
| All hosted generated answers | 16 | 10.638 s | 22.784 s |
| Hosted attempts matching native warm cases | 12 | 10.654 s | 19.334 s |
| Retained native warm two-pass attempts | 12 | 26.458 s | 47.555 s |

Matched-case median decreased **59.7%** and p95 **59.3%** in this single pass. The native matched sample includes one validation fallback; hosted matching cases all produced structurally accepted answers. The native cold broad answer took 65.230 seconds; the hosted broad answer took 22.784 seconds, but provider coldness is unknown and they must not be called equivalent cold-start measurements. Small, once-per-case samples are not stable production percentiles or an availability promise. No faster/safer default is promoted from latency alone.

| Stage, summed across 16 hosted model answers | Time |
|---|---:|
| Storage reads | 113.809 ms |
| Retrieval | 46.697 ms |
| Extractive synthesis | 57.555 ms |
| Context construction | 2.830 ms |
| Draft requests | 111.279 s |
| Revision requests | 79.465 s |
| Validation | 5.387 ms |
| Persistence | 217.949 ms |
| Total API wall | 191.230 s |

The 32 hosted calls still dominate latency. Their wall times include provider queueing, networking and inference; provider decode/load/prompt nanosecond durations are unavailable, so generation tokens/s cannot be compared to native decode throughput. Ollama-specific telemetry fields correctly remain null.

Reported counts across full suite: **64,270 input tokens**, **5,164 output tokens**; per-pass inputs **841–4658**, outputs **80–451**. Maximum reported input plus output **4825**, below the advertised 24,000 context. This is not a token guarantee for the application's largest possible context, nor proof against hidden provider truncation. No completed call hit the 1800-token output cap; universal finish metadata is absent on the native Cloudflare endpoint. Preserve these limitations when comparing quality.

## Allowance and isolation

Using reported token counts and the documented model rates, the evaluation ledger calculates **2771.565 neurons** for the full suite plus **126.825** for the smoke: **2898.390 neurons total**. This is a token-rate calculation, **not an independent Cloudflare account-dashboard measurement**. Zero usage reservations remain pending in the suite ledger. Both runs used isolated ledgers so user-saved answer counts were not incremented. The provider account's own Free-plan quota remains account-wide and authoritative; other apps' consumption is outside these artifacts.

**Paid inference API spend: $0 under the confirmed Workers Free setup.** No OpenAI or local model generation was invoked. Hardware/electricity/web hosting remain separate. The change removes local model computation by routing inference to Cloudflare; no temperature, fan speed or sustained system-memory benchmark was performed for this hosted run.

## Evidence quality and release gate

All outputs are retained in [full-suite answers](../../apps/api/evaluation/m0/results/cloudflare-first-answers.json), with timing in [full-suite metrics](results/cloudflare-first.json). The [source-backed engineering adjudication](../../apps/api/evaluation/m0/results/cloudflare-first-adjudication.json) uses the same frozen rubric, compares native failures and remains pending independent human/expert review. This is not clinical validation, an accuracy percentage or an independent model fact-check.

The full review found **9 supported / 9 partially supported / 0 unsupported overall**, with **zero critical invented assertions observed**. On the fifteen cases shared with the native run, the hosted review has **8 supported / 7 partial**, versus native **5 / 10**, and zero versus six critical assertion flags. Do not convert these small engineering categories into accuracy rates. Omitted qualifiers remain material even when no explicit contradictory assertion is assigned a critical category.

Age 10+ is preserved in the real broad answer; invented “rare” postmarketing frequency and statistical-significance disagreement wording are avoided. Material coverage gaps remain: the combination/add-on answer omits the 8.2% comparator and 24-week time window; HbA1c add-on omits adults/time window; fasting-glucose answer omits adults, time window and metformin background. Numerical simplification is nearly verbatim repetition. A complete HTTP suite and fewer critical flags do not erase those omissions. **Do not declare the quality/pilot promotion gate passed.** The interrupted native M0 cases remain incomplete as native observations; hosted completion does not retroactively finish that baseline.

The user's local `.env` now explicitly selects Cloudflare, so starting with `apps/api/run.py` does not start Ollama. The website and API were started locally with the saved configuration, and same-origin `/api/health` reports configured Cloudflare inference. This is local activation of an explicitly chosen candidate, not a public deployment. No per-user authorization or verified backup/restore was added.

## Verification and reproduction

- Backend suite: **145 passed**, two upstream websockets deprecation warnings.
- New evaluator tests: two passed, including real isolated loopback HTTP with mocked provider, predecessor validation, immutable/distinct output paths, endpoint restriction, credential-free metrics and store/ledger restoration.
- Existing Cloudflare UI: ten production-browser regressions, lint, typecheck and build passed in implementation commit `345924d`; no frontend code changed in this evaluation.
- Real hosted semantic run: 18/18 completed; review limitations above remain release blockers.

To reproduce **only on a confirmed free account**, using new artifact paths:

```sh
apps/api/.venv/bin/python apps/api/evaluation/cloudflare_run.py \
  --output /tmp/triallens-cloudflare-rerun.json \
  --answers /tmp/triallens-cloudflare-rerun-answers.json
```

The command consumes free allowance, loads the local server-only `.env`, and never invokes the native-only M0 benchmark. It stops on a hosted provider failure instead of spending the allowance repeating configuration errors. Follow-up subsets require predecessors in inventory order. Existing artifacts are never overwritten.

Next work: preserve this control run, test a separate reversible approach to retaining required comparator/time/population qualifiers without making answers mechanical, then repeat full source-quality comparisons. Obtain independent review and repeated finalist latency samples before deployment. Keep unrelated retrieval/database changes out of this provider experiment.
