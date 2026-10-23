# Backend functional evaluation — 22 October 2026

This audit exercises isolated temporary JSON stores and usage ledgers through the real FastAPI app, with public/synthetic fixtures and provider HTTP mocked. It performs no live inference, credential inspection, source refresh against external services, or production-data writes. It evaluates functionality before design changes.

## Reproduced defects and changes

| Finding | Severity | Reproduction and disposition |
|---|---|---|
| Re-running extraction silently removes review status and manually corrected result text. | P2 | PATCH an extraction to reviewed with corrected result; POST `/extract`; the same source returned unreviewed generated text. Fixed by carrying identity and user-editable fields into rebuilt rows while refreshing generated detail fields. Corrections saved without changing review status are also retained. |
| Conversation source-scope validation treats `null` (all source types) and `[]` (no source types) as identical. | P2 | Ask with one value, then follow up with the other and the previous answer ID: previously HTTP 200 in both directions. Fixed: HTTP 400 asks the caller to start a new conversation. Existing set-based equivalence for reordered explicit source types remains. |
| Partial refresh deletes prior evidence for a failed connector when another connector succeeds. | P1 data loss / P2 overall deployment finding | Previously stored PubMed and registry records; mocked registry unavailable with PubMed success; registry record disappeared. Reproduced by this workflow suite; separate ingestion audit owns preservation and stale-evidence warning fixes. |
| Whitespace-only condition passes API length validation and is saved as an empty topic. | P2 | POST a condition consisting of three spaces: previously HTTP 200 with an empty stored condition. Reproduced here; root audit owns normalization and broader input-validation coverage. |

Before fixes, focused workflow tests produced deterministic failures for these cases. They require neither a GPU model nor hosted inference. The combined API/store/conversation/Cloudflare/workflow/context subset passed **58 tests in 0.86 seconds** after changes, including nine new API workflow cases and four new context cases. See the root audit's final verification record for the final full-suite count.

The extraction endpoint has no historical per-field edit provenance. Preservation therefore retains all seven existing editable values for unchanged stored source IDs, including values not explicitly marked reviewed. Derived source details can still rebuild. Updating changed source evidence remains ingestion's responsibility.

## Verified integrated workflows

- Workspace creation, mocked ingestion, extraction retrieval and reviewer correction.
- Research Ask filtered to PubMed: only that source type is retrieved or cited.
- Follow-up history linkage with the same explicit scope.
- Document Ask: all returned retrieved passages belong to the chosen document.
- Rejection of document/workspace history scope changes and a document excluded by the source-type filter.
- Rejection of a short question, a missing extraction and cross-workspace answer/document IDs.
- An explicit empty source filter produces no citations or retrieved passages.
- Save and remove answers from Brief; current reviewer counts are rebuilt rather than served from a stale Brief cache.
- Reopening `JsonStore` preserves history, exact retrieved provenance, reviewed corrections and Brief membership.
- Refreshing to a replacement source collection preserves saved answer/citation/retrieved-passage snapshots and makes Brief warn that historical citations need checking.
- Re-extraction preserves reviewed and unreviewed manual corrections while regenerating missing derived details.

Existing tests additionally cover atomic JSON publication and simulated interrupted writes; cross-instance write serialization; empty ingestion preserving stored evidence; unchanged refresh keeping source identity/review; unknown citations and citations in limitations rejected; copied source passages rejected; incomplete/rejected provider responses; provider failure without local or paid failover; one generated-answer count for two passes; personal-treatment and ambiguous-question guards; local busy lock release; persistent atomic Cloudflare quota reservation and daily reset; no credentials or source prose in ordinary usage records. These are structural/functional checks, not evidence of clinical accuracy.

## Provenance findings

1. **P2: stale extractive provenance accompanies a successful conversational answer.** A replay of the frozen `real-metformin` snapshot through the real Ask route with a deterministic mocked generation produced final citations `[]`, while `source_readouts` still contained three `CITED` notes, including `openFDA label:FDA-LABEL-metformin-1` for excluded ZITUVIMET. The generation context correctly excluded the combination product. These notes are rendered under the current UI's “Source matching notes”; supporting/quality/reasoning fields also originate in the earlier extractive fallback rather than being regenerated from the accepted final response. They must be clearly separated or reconciled before claims of final-answer provenance consistency. The main citation allow-list safeguard itself remained effective in this replay.
2. **P2, fixed: `content_truncated` described deduplication rather than content loss.** With a short complete source and a retrieved passage equal to its abstract, captured generation context contained the complete source in `text`, removed the redundant passage, but reported `content_truncated=true`. This can cause an unnecessary partial-excerpt caveat. Loss is now calculated before deduplication. The regression first failed on the complete-source case, then passed after the fix. Three additional cases verify that source-prefix cutoff, passage cutoff and omitted passages caused by the existing character budget continue to report actual truncation. No model request, source selection or character budget was changed.

## Answer quality and deployment limits

The retained hosted evaluation completed 18/18 cases, with 16 structurally accepted model answers and two deterministic guards. Source comparison judged nine supported and nine partially supported outputs. Population/comparator/timeframe omissions and evidence-absence wording remain unresolved; this functional audit does not infer they are repaired from mocked-provider tests. Independent expert review remains outstanding. See `docs/performance/cloudflare-first.md` and its retained source-backed adjudication.

The `/health` response indicates configured credentials, not successful remote authentication or current provider availability. Existing successful hosted tests establish that the connection worked at evaluation time. The Free-plan confirmation and local quota guard do not verify provider billing state or account-wide consumption by other applications. No live availability/quota or larger-scale concurrency/load claim is made here.

Brief export is browser-owned Markdown generation; its actual download, source links and caveat retention belong to the root/browser workflow audit, not this API-only check. Production deployment, authentication/access control and supported Python runtime checks remain separate launch gates.
