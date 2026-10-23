# Cloudflare hosted Ask candidate

Decision: implement **Cloudflare Workers AI** as the recommended small-pilot hosted option. This is a provider-fit decision, **not a claim of better biomedical accuracy or measured latency**. The 20 October native baseline remains unchanged, including its retained failures and incomplete memory gate. On 22 October the user explicitly requested comparing and implementing a hosted alternative because native inference heats the Mac; local M1 tuning is not being silently resumed.

## Comparison checked 22 October 2026

| Dimension | Cloudflare Workers AI | Groq Free |
|---|---|---|
| Inference location | Provider infrastructure | Provider infrastructure |
| Free allowance | 10,000 neurons/day on Workers Free; errors beyond quota | Model-specific limits; documented examples 8K tokens/minute, 200K/day |
| Two-pass long prompts | Consume daily allowance; no guaranteed answer count | May hit per-minute token ceiling even at low request volume; exact account limits vary and cached tokens can be excluded |
| Structured output | Native JSON-schema mode supported by selected model | Structured outputs supported by selected models; compatibility must be checked per model |
| Operational choice | One fixed model, direct API, no gateway/router or local model service | Viable alternative; no integration added in this change |
| Quality / actual latency | **Not yet measured for TrialLens** | **Not measured for TrialLens** |

Sources: [Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/), [Groq limits](https://console.groq.com/docs/rate-limits), [Cloudflare JSON mode](https://developers.cloudflare.com/workers-ai/features/json-mode/). Quotas are account-wide, changeable and not a service-availability promise. Hardware, internet and web/API hosting are separate from free inference.

The fixed initial candidate is [`@cf/meta/llama-3.3-70b-instruct-fp8-fast`](https://developers.cloudflare.com/workers-ai/models/llama-3.3-70b-instruct-fp8-fast/): 24,000-token context, documented native JSON-schema support. Choosing this larger model is a hypothesis about suitability, not proof of quality. No automatic model router, smaller-model downgrade, fine-tune or training on papers is introduced.

## Setup — human account steps

1. Create/sign into [Cloudflare](https://dash.cloudflare.com/). Keep the account on **Workers Free**. Do not enable Workers Paid, prepaid AI Gateway credits or automatic top-ups for this zero-spend setup.
2. Follow [Workers AI → Use REST API](https://developers.cloudflare.com/workers-ai/get-started/rest-api/). Copy the Account ID and use **Create a Workers AI API Token**. Prefer the official account-scoped template; current custom-token instructions require Workers AI Read and Edit.
3. Put these values in **`apps/api/.env`**, which is Git-ignored. Never place the token in browser code, a `NEXT_PUBLIC_` variable, logs or chat:

```dotenv
TRIALLENS_CHAT_PROVIDER=cloudflare
CLOUDFLARE_ACCOUNT_ID=<32-character-account-id>
CLOUDFLARE_API_TOKEN=<account-scoped-workers-ai-token>
TRIALLENS_CLOUDFLARE_FREE_PLAN_CONFIRMED=true
```

4. Run `apps/api/.venv/bin/python apps/api/run.py --check`, then restart the API with `apps/api/.venv/bin/python apps/api/run.py`. This provider does **not** start or contact Ollama. Existing shell variables override `.env`, so remove an old `TRIALLENS_CHAT_PROVIDER=ollama` override if present. `/health` shows configured/extractive and selected model; configured means credentials have the expected shape, **not** that a real request succeeded.

The free-plan flag is an **operator attestation**, not a billing-plan lookup. The application cannot guarantee $0 billing on a paid Cloudflare account or account for other applications' consumption. Cloudflare's Workers Free account limit is the authoritative spending boundary. No automatic account upgrade or paid fallback exists in TrialLens. The application-level quota below is an additional conservative guard, not a substitute for keeping that account free.

## Data handling and answer path

Questions, up to three prior question/answer turns, selected source excerpts and the draft are sent to Cloudflare over HTTPS for draft and revision. This is a change from local-only processing; no entire workspace database is uploaded. Standard Workers AI inference is documented as no training and no retention after processing, with limited exceptions. Enabling AI Gateway logging/caching or other stateful services changes retention; this implementation does not enable them. See [Cloudflare data usage](https://developers.cloudflare.com/workers-ai/platform/data-usage/). Do not treat this pilot configuration as approval to process patient-identifying data.

Retrieval, source filters, eight-source/28K-character context budget, product scoping, treatment/ambiguity guards, prompts, revision instructions, JSON parsing, citation checks and long-copy rejection remain server-owned. Only the final accepted answer increments the existing 100-answer alert; no paid OpenAI reservation is made. Cloudflare failures return clearly labeled source excerpts, never the unreviewed draft, an automatic local run or a paid provider.

This is native REST JSON-schema mode, with a fixed endpoint and model. Both string JSON and structured-object responses are handled. Refusals, tool calls, provider errors, indicated incomplete/length results and reaching the 1800 output-token cap are rejected. Native results do not always expose a finish reason; absence of a truncation indication is **not a universal completeness guarantee**. Existing validation still cannot establish claim-level entailment. No unvalidated streaming text is displayed.

Actual reported input/output counts feed opt-in numeric telemetry; missing counters remain unknown. Local GPU/Ollama timing fields remain null for Cloudflare rather than being fabricated. The current model has a different tokenizer from Qwen: native baseline token counts do not prove all Cloudflare prompts fit. Context-overflow behavior and absence of source truncation require live tests.

## Daily quota and persistence

An additive `cloudflare_requests` table in the existing usage SQLite file tracks opaque request ID, UTC day, reserved micro-neurons and pending status. No questions, sources or answers are stored in it. A transaction reserves budget **before each pass**, with a fixed 9,000-neuron daily application ceiling (below the provider's documented 10,000). Published rates for this model are 26,668 input / 204,805 output neurons per million tokens.

Reservations deliberately use serialized UTF-8 byte length plus overhead and maximum output; **this is a conservative allowance calculation, not a measured tokenizer count or guaranteed universal token bound**. Valid provider usage settles the reservation. Missing/malformed usage, failures and timeouts retain the full reservation; interrupted attempts therefore reduce available quota until the next UTC day. A failure can consume quota without incrementing the successful-answer count. No automatic retries are sent. Other apps sharing the Cloudflare account are outside this ledger. Preserve this SQLite file across restarts and replicas; a separate installation does not share its local counter.

`/usage` adds numeric Cloudflare quota status, separate from the existing optional OpenAI dollar ledger. Its nested `available` flag means quota tracking is readable, not that credentials or the provider have been live-verified. The UI names hosted inference and preserves the 100-answer alert; it does not pretend that old OpenAI balances describe Cloudflare. Single-process admission remains nonblocking. The SQLite quota coordinates reservations using that shared file; it is not a distributed inference lock.

## Optional packaging

`compose.cloudflare.yaml` is a **standalone** alternative to `compose.yaml`; it runs only the API and website, with no Ollama container:

```sh
docker compose --env-file apps/api/.env -f compose.cloudflare.yaml config --quiet
# Only when ready to run this hosting profile:
docker compose --env-file apps/api/.env -f compose.cloudflare.yaml up --build -d
```

It defaults to the existing `triallens_data` volume to preserve workspace/Brief/usage state; set `TRIALLENS_DATA_VOLUME` to the actual existing volume if different and verify a backup first. Never run both profiles against the same live data simultaneously. Configuration validation is not deployment verification. Website remains loopback-only; trusted pilot access still requires authenticated HTTPS gateway/VPN including `/api`.

## Validation status and activation gate

Mocked adapter, quota/concurrency and Ask integration tests exercise both passes, scopes, guards, schema/citation/copy failures, missing usage, provider outage and no fallback. These establish implementation behavior, **not model accuracy or real speed**. No paid requests or local model inference were run for this change.

**Connection is now verified by a full 18-turn live evaluation; quality promotion remains blocked by required qualifier omissions.** See [first hosted results](../performance/cloudflare-first.md). Keep this candidate explicit; it does not become the code's default provider automatically. Fresh `.env.example` recommends it, while unconfigured installs show labeled source excerpts. The existing native default remains available only through explicit local configuration when using the example. Subsequent comparisons must evaluate frozen M0 cases in an isolated store and usage ledger, preserving failed outputs and previous-answer dependencies; do not use the native-only `evaluation/m0/benchmark.py` for Cloudflare. Measure hosted p50/p95, per-pass tokens, quota consumption and all critical factual categories before a pilot promotion. Do not claim the unresolved native M0 suite has been completed by mocked Cloudflare tests.


## Verification of this implementation

- Backend: `apps/api/.venv/bin/python -m pytest apps/api/tests -q` — **143 passed**, two upstream websockets deprecation warnings. Includes 44 adapter/quota tests and six hosted conversation tests (one parametrized twice).
- Frontend: `npm run lint`, `npm run typecheck`, `npm run build` — passed.
- Production browser: **10 passed** via Expect against fresh preview port 3002, including two added hosted status/quota/fallback/follow-up regressions. All Ask responses mocked.
- `docker compose --env-file apps/api/.env -f compose.cloudflare.yaml config --quiet` — passed; no containers deployed.
- `git diff --check` — passed.

Test API was forced into Cloudflare mode with an empty token; no local model could start. Temporary servers were stopped after verification. Real hosted results, hosted latency, account quota and biomedical improvement remain unverified until setup is complete. No native benchmark artifacts were overwritten. Unrelated local research files were excluded from this change.


## First live evaluation

The saved Cloudflare setup was connected and the full 18-turn frozen suite completed on 22 October. See [measured latency and outstanding quality gates](../performance/cloudflare-first.md). The implementation is locally active through explicit `.env` selection; comparator/timeframe/population omissions still prevent a clean pilot-quality promotion. Earlier pending-setup statements above describe the initial integration stage, not the current connection status.
