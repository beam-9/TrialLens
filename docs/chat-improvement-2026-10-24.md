# Chat improvement — 24 October 2026

## Shipped scope

The safe production changes are product scoping and Cloudflare response compatibility. **The production Llama model, generation prompts, two-pass strategy, citation/copy guards, 100-answer alert and free-plan cap remain unchanged. No candidate prompt or alternative model is promoted.** Deployment is still pending answer-quality work.

Previously, a broad single-ingredient question could exclude combination labels from model context but still show them in the excerpt fallback when generation failed. An API regression reproduced ZITUVIMET safety prose, citations and readouts inside the fallback for a broad metformin question. The shared product-scope function now filters sources, chunks and extraction rows **before** workspace retrieval and fallback synthesis. The same function still scopes model context. A truthful exclusion note survives quota failures, incomplete generation and unconfigured inference. Named combination products, brand aliases, historical combination follow-ups, explicit document selection and source-type filters remain supported. Historical stored answer text is not rewritten.

Cloudflare may return a legacy `response`, a chat-completion `choices` envelope, or both. The parser now accepts only one completed assistant choice, rejecting refusal/tool output, missing final content, length termination and conflicting envelopes. Redundant envelopes must decode to identical JSON objects. Reasoning fields are not returned. All existing answer-schema, citation and copied-passage validation still runs afterward. A live 64-token synthetic protocol probe confirmed matching dual envelopes; it used 46 input/6 output tokens and approximately 2.456 neurons. This verifies transport compatibility, not biomedical answer quality.

## Generation experiments and measured failures

All research calls used isolated frozen public/synthetic stores and a separate persistent evaluation ledger. Production stores/counters were hash-checked. No paid-provider fallback or local GPU model was called. Failed artifacts remain under `apps/api/evaluation/m0/results/`; corresponding timings are under `docs/performance/results/`. Independent engineering adjudications inspect exact submitted source context, paragraphs, uncertainty and visible demo metadata; they are not clinical validation or clinical accuracy rates.

| Candidate | Observation | Decision |
| --- | --- | --- |
| Llama comparison examples, six cases | 1 supported / 5 partial; no final critical error, but missing control rates, effect magnitudes and relevant risk/uncertainty coverage | Reject |
| Llama coverage-preserving revision, six cases | 3 supported / 3 partial; two critical-error cases, including unsupported risk frequency/mechanism and a false source-wide absence claim | Reject |
| Llama conversation-focused prompt, two real cases | Both partial; planned registry research presented as suggestive benefit; simplification remains weak | Reject |
| Qwen 30B, two-case plan | First answer's revision reached its 1,800-token cap; fallback, not a completed candidate | Incomplete; no promotion |
| GPT-OSS 120B | Initial bounded response/transport failures; after compatibility work, one of two answers accepted structurally, while another failed citation validation. Accepted prose was still overlong and contained unsupported risk wording | No promotion; not a successful quality run |
| GLM-Flash, reasoning on | First request exhausted its 4,096-token output budget; rejected | Incomplete; no promotion |
| GLM-Flash conversational profile | Two schema-accepted answers, both partially supported. Broad answer has three false absence claims; both repeat excessively and fail conversational simplification | Reject |

Observed two-pass answer latency ranges were approximately **7–16 seconds** for the first six Llama cases, **11–26 seconds** for coverage-focused Llama, and **52–76 seconds** for the two GLM conversational cases. These small, differing workloads are diagnostic observations, not controlled performance comparisons. Model generation/revision remains the substantial latency cost; transport acceptance and faster answers do not establish factual support.

The alternate models and unit rates were checked against [Cloudflare's model pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/). GLM's reasoning-off request uses the documented [chat-template option](https://developers.cloudflare.com/agents/models/ai-sdk/). Experimental models are an explicit CLI allowlist, share the same daily ledger, and restore model/rates/output limits on exit. No paid-plan-only model is allowlisted. The larger GPT-OSS output budget applies only to that isolated experiment; the production maximum remains 1,800 tokens.

## Evaluation improvements and limits

Four newly authored conversational holdouts are retained separately from the unchanged frozen inventory/rubric. `--cases-file` substitutes questions only; source snapshots remain hash-checked and unchanged. They test endpoint-versus-baseline interpretation, independent treatment settings, plain-language benefit/risk coverage and durability/survival gaps. These are authored evaluation questions, not collected real-user evidence.

The attempted production-prompt holdout run stopped on an intermediate dual-envelope parser error. That error was repaired and transport-probed, but the holdout answer is **not** adjudicated as a successful generation and the remaining holdouts were not executed. The original frozen suite was not broadly rerun after focused candidates failed.

The final evaluation ledger is **8,597.037 neurons used/reserved of 9,000**, leaving **402.963**. Five failed requests retain conservative reservations. The remaining amount does not cover a normal complete two-pass research answer. No ledger reset, refund or cap increase was used. This local ledger cannot verify other applications' account usage; Cloudflare's Free-plan allowance remains authoritative.

## Verification and next work

- **229 backend tests passed**, including 11 API product-scope regressions and complete/refused/truncated/ambiguous provider-response cases; two existing upstream deprecation warnings remain.
- **14 browser workflow tests passed in 15.4 seconds**, using deterministic fixture completions and no external inference. The final dual-envelope correction was subsequently verified by adapter tests and the live synthetic probe; no browser contract changed.
- A read-only agent reviewed source filters, document/history boundaries, parser fail-closed behavior, quota and privacy paths, including the final dual-envelope correction; no material regression was found.

Next experiments should improve question-relevant context and distinguish protocols, measured findings, product/formulation and evidence absence explicitly, then test the authored holdouts before a full frozen rerun. Repeating prompt variants or removing revision is not justified by these failures. A candidate must preserve useful detail, actually simplify follow-ups and avoid material unsupported claims before activation. Keep the current safeguards and zero-paid-inference constraint.
