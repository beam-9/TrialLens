# Ask caption evidence — 23 November 2026

Status: caption ingestion and verified figure selection implemented. Answer-quality
checks remain diagnostic; Ask is not certified ready for deployment.

## Change and boundaries

The preceding paper-body experiment missed confidence intervals available only in
figure captions. The existing JATS parser now retains complete text-only captions
with their source labels, inline numerical notation and paragraph word separation.
It does not interpret images, fetch image URLs, perform OCR or calculate statistics.

Each packet is at most 8,000 characters, with six captions and 16,000 combined
characters per article. Body figures, figure groups and article-level floats are
supported, including figures embedded in body paragraphs. Abstracts, references and
supplements remain outside the traversal. Unsupported formula, alternatives and table
markup cause a whole-caption omission. Superscript/subscript markup is retained
explicitly so exponents cannot silently become subtraction. Duplicate labels are
rejected; missing labels are never invented.

Metadata adds `caption_sections`, `caption_labels`, `indexed_captions` and
`omitted_captions`. Omission reasons include missing_or_ambiguous_caption,
ambiguous_caption_label, unsupported_caption_markup, caption_size_limit,
caption_count_limit and caption_total_size_limit. Original paper identity, hash,
license metadata and partial-indexing disclosure remain intact.

The existing atomic-packet path carries captions whole through indexing and both
Ask passes, or omits them whole when the evidence budget cannot fit them. Structured
abstract extraction remains separate. Caption paragraphs become whitespace-separated
text in chunks; packet contents and inline notation are retained, without clipping.

Explicit requests for Figure 6 or Fig. 6B prioritize the matching parser-recorded
source label. Panel suffixes select the complete figure caption, not an inferred
panel fragment. Priority requires the retrieved packet to match its stored section.
The parser ordinal alone, or a caption sentence mentioning another figure, cannot
establish identity. A verified label match does not require shared topic words.
Legacy paper records without caption metadata retain their earlier behavior.

## Verification and frozen diagnostics

697 API tests passed, with two existing websocket deprecation warnings. Tests cover
unsupported markup, limits, labels, image non-fetching, exact context attribution,
retrieval of the sixth of six otherwise identical captions, abbreviation handling,
label impersonation and tampered packets. An independent reviewer reread the repaired
code and found no remaining blocker in parsing, selection or evidence assembly.
These checks verify plumbing and safeguards, not clinical answer accuracy.

ATOMIC (PMID 38763510, PMC11307122) uses the same original XML hash as the previous
experiment. The parser retains five captions, including Fig. 2/3 intervals; one
captionless figure is explicitly omitted. Attribution and CC BY-NC license metadata
remain in the frozen snapshots.

Two new immutable diagnostic cohorts preserve the initial and repaired behavior:

- `apps/api/evaluation/cohorts/paper-captions-2026-11-23/`
- `apps/api/evaluation/cohorts/paper-captions-v2-2026-11-23/`

The initial run yielded three conversational routes and one excerpt fallback. An
explicit Fig. 2A request did not select Fig. 2A among the four model passages. This
motivated verified-label retrieval. Broad Results answers still omitted uncertainty.

Run the repaired cohort through the actual isolated HTTP API with:

```sh
apps/api/.venv/bin/python apps/api/evaluation/answer_coverage/evaluate_quality.py \
  --inventory apps/api/evaluation/cohorts/paper-captions-v2-2026-11-23/inventory.json \
  --output docs/performance/results/paper-captions-v2-default-2026-11-23.json \
  --answers apps/api/evaluation/answer_coverage/results/paper-captions-v2-default-2026-11-23.json
```

Use new output filenames for reruns; existing captures must remain immutable.
Production model, prompts, quotas and validation remain unchanged. All hosted calls
use the existing Cloudflare Free integration and shared evaluation allowance; no
paid inference, local LLM, production workspace mutation or deployment is introduced.

## Measured answer findings and next experiment

The repaired run returned three conversational answers and one excerpt fallback.
Wall times were 26.53, 20.49, 17.69 and 17.40 seconds in case order. Independent
semantic review grades two passes (figure-specific interval, mortality boundary),
one partial answer (broader Results) and one failure (simplification fallback).
The figure answer now correctly states −0.94% with 95% CI −1.25 to −0.63 for the
specified groups at 16 weeks. It should identify the change-from-baseline estimate
more precisely. The two runs are small diagnostics, not a statistical improvement
claim or a passing release gate.

The Results answer still omits both reported ±0.11% terms and attaches negative
confidence bounds to a positive effect magnitude without explaining the signed
contrast. It also overstates article availability before acknowledging partial
indexing elsewhere. The simplified follow-up falls back to passage counts and
unrelated excerpts. These are unresolved user-facing quality defects. The exact
per-case judgments are in the repaired cohort's adjudication.json.

Next, test an evidence-backed revision mechanism that preserves each requested
estimate with its own groups, timeframe, units and reported uncertainty, distinguishing
a reported magnitude from a signed contrast. Missing requested figures must not be
silently discarded. Validate the mechanism against a second independent paper and
existing holdouts before changing production generation behavior. Keep citation,
numerical, partial-source and treatment safeguards active; do not fix rejection by
weakening them. Browser workflow remains unchecked.

Across both new diagnostic runs, 16 provider calls used/reserved 2,419.292378 local
neurons; 6,580.707622 of the 9,000 local daily allowance remained at completion.
This is the application's evaluation ledger, not a provider-account-wide usage audit.
