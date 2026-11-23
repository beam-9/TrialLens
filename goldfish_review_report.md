# Goldfish Annotated Review Report

**Target:** `docs/ask-paper-grounding-2026-11-22.md` (full file)

Status: awaiting user decision on proposed document edits. The code fixes below
were separately implemented and verified under the authorized development task.
No proposed document replacements have been applied.

Two fresh-context reviewers read the installed EGM personas and standards:
Codebase Details against the Re-Implementation Standard, and Implementation
Readiness against the Implementation Readiness Standard. They reviewed the target,
selected code, tests and frozen inventory. They did not run tests or edit files.
The primary agent independently ran the tests. Fresh conversational context was
established with `fork_turns=none`; exclusion of host instruction files is unverified.

## Prioritized Findings & AI Suggestions

### 1. [Codebase Details] — Severity: Blocker

- **Affected Scope:** target lines 36–38 and 61–63; `paper_text.py` XML parsing.
- **Discrepancy Description:** Unknown XML encodings can raise `LookupError`, bypass per-paper fallback, and cause the outer PubMed handler to return no abstracts.
- **Rationale:** This contradicts the documented preservation of abstracts on malformed full text.
- **AI Suggestion:** CONTEST — residual finding superseded by verified code repair.
- **Justification:** The initial finding was valid. The parser now catches `LookupError`; `test_unknown_encoding_does_not_discard_pubmed_abstracts` verifies that the abstract survives with `malformed_xml`. The original reviewer reread the repair and confirmed closure. This contests only the claim that the defect remains, not the initial review.
- **Proposed Edit:** None required to restore the target's stated behavior.

### 2. [Codebase Details] — Severity: Blocker

- **Affected Scope:** target lines 81–84 and 101–103; `conversation.py::build_evidence_records`.
- **Discrepancy Description:** Linking by text equality across all stored sections can attach an unretrieved body section to an abstract passage or attach multiple identical sections.
- **Rationale:** Text identity alone does not establish the origin of the retrieved passage.
- **AI Suggestion:** CONTEST — residual finding superseded by verified code repair.
- **Justification:** The initial finding was valid. Links now use the section identity of a validated retrieved packet. The ordinary/duplicate-text regression checks both cases, and the reviewer confirmed closure by rereading code and tests.
- **Proposed Edit:** None required to restore documented section-level provenance.

### 3. [Codebase Details] — Severity: Blocker

- **Affected Scope:** target lines 48–53 and 70–77; `rag.py::source_sections_for`.
- **Discrepancy Description:** Enriched sections can enter structured extraction through generic 420/360-character trimming despite abstract-derived scope wording.
- **Rationale:** This can expose a partial table through a second, unprotected path.
- **AI Suggestion:** CONTEST — residual finding superseded by verified code repair.
- **Justification:** The initial finding was valid. Full-text packet labels are excluded from abstract-derived extraction. The regression checks that body-only values and packet names do not enter extraction fields. The reviewer confirmed closure.
- **Proposed Edit:** None required to restore the target's stated extraction boundary.

### 4. [Codebase Details] — Severity: Major

- **Affected Scope:** target lines 30–68, parser/adapter contract.
- **Discrepancy Description:** Stage-dependent metadata, reason codes, exact identity/traversal rules, license limits, HTTP timeout/proxy behavior and failed-attempt accounting are underdocumented.
- **Rationale:** A reader cannot reproduce the implementation's boundary behavior from this document alone.
- **AI Suggestion:** PROPOSE FIX.
- **Justification:** The public ingestion contract benefits from explicit failure and resource semantics.
- **Proposed Edit:** Insert after the adapter behavior paragraph:
  > The adapter uses a four-second HTTP operation timeout, disables environment proxy inheritance and redirects, and enforces a seven-second total read deadline. Every attempted linked fetch consumes one of the two attempts, including failures; unlinked entries do not. Parser failure metadata always has status/scope/partial_indexing/reason; xml_sha256 appears once bounded input bytes have been accepted. Validated identity/license fields appear only after their parsing stages. Success additionally includes paragraph_sections/table_sections, indexed and omitted counts, and omission_reasons. License text is limited to 2,000 characters, four links and 500 characters per link, with license_truncated. Parser reasons distinguish oversized_or_invalid_xml, unsafe_xml_declaration, malformed_xml, xml_nesting_limit, missing_or_multiple_articles, missing_article_metadata, missing_or_ambiguous_article_ids, article_identity_mismatch, missing_body and no_supported_body_content. Article IDs must match their expected strings; pmc/pmcid aliases normalize a missing PMC prefix and must agree. Table validation rejects missing/nested tables, rows/cells, merged/nested cells, ragged rows or missing column headers before applying size/count limits. Section keys use source-document ordinals, not a new scientific outcome identity.

### 5. [Codebase Details] — Severity: Major

- **Affected Scope:** target lines 70–85, indexing/context contract.
- **Discrepancy Description:** Packet admission, ranked source filling, passage priority, budgeting, duplicate reclamation, abstract prefix cap and provenance fields leave choices implicit.
- **Rationale:** These details affect whether complete evidence reaches the model.
- **AI Suggestion:** PROPOSE FIX.
- **Proposed Edit:** Insert after the context paragraph:
  > A paper packet requires a PubMed source, paper_packet_version=1, available indexing metadata, a section in the parser-emitted paragraph/table lists and a stored section value. Ranked retrieved sources fill the eight source slots before remaining sources. Within a source, complete packets precede ordinary passages, keeping at most four. The remaining 28,000-character source-text budget is shared among remaining sources; a complete ranked packet may borrow enough room to fit, but cannot exceed the remaining global budget. Packets that cannot fit are omitted whole. Duplicate passage space is reclaimed for the abstract prefix, which is capped at 10,000 characters. A paper passage link carries matched_passage_index and its actually retrieved section. Full-text provenance exposes only PMCID, URL, XML hash, bounded license/missing/truncated flags, scope and indexed/omitted counts. It does not duplicate all section lists into the model context.

### 6. [Codebase Details] — Severity: Major

- **Affected Scope:** target lines 87–91; budget and fetch-cap tests.
- **Discrepancy Description:** The initial short-packet/single-record tests did not exercise verified-packet budget exhaustion or ranked two-attempt accounting after a failure; the inventory did not grade semantics.
- **Rationale:** The original verification scope was narrower than the stated guarantees.
- **AI Suggestion:** CONTEST — residual coverage gap superseded by added checks.
- **Justification:** Added tests exercise an intact packet that cannot fit, ranked failed fetches consuming the cap, and preservation of abstracts. `evaluation/cohorts/paper-grounding-2026-11-22/adjudication.json` records actual semantic judgments separately. They do not establish clinical accuracy. Current test results and reviewer resync are below.
- **Proposed Edit:** None needed for the original test-coverage claim; semantic gate instructions are addressed in item 7.

### 7. [Implementation Readiness] — Severity: Major

- **Affected Scope:** target lines 105–110 and 118–121, executable verification.
- **Discrepancy Description:** No exact runner invocation, output/adjudication locations or passage-backed per-case acceptance criteria are supplied.
- **Rationale:** A fresh engineer must choose how to run and judge the abstract/body comparison.
- **AI Suggestion:** PROPOSE FIX.
- **Proposed Edit:** Add a verification subsection with the following command and criteria:

```sh
apps/api/.venv/bin/python apps/api/evaluation/answer_coverage/evaluate_quality.py \
  --inventory apps/api/evaluation/cohorts/paper-grounding-2026-11-22/inventory.json \
  --output docs/performance/results/paper-grounding-default-2026-11-22.json \
  --answers apps/api/evaluation/answer_coverage/results/paper-grounding-default-2026-11-22.json
```

  > Preserve existing captures; use new result filenames for any rerun. Consult the cohort's adjudication.json. Abstract-only answers must scope availability and not call a positive change a decrease. Full-text Results answers must preserve the source's combination-arm decrease 0.58%±0.11%, atorvastatin-arm increase 0.35%±0.11%, reported difference 0.94%, 16-week timeframe and P<0.0001. Do not calculate a missing interval, invent the dispersion type, or claim the abstract/body wording is identical. Follow-ups must retain the requested groups, figures and source limits. Mortality answers must not infer a death-risk benefit from HbA1c/LDL-C findings. Route acceptance is not semantic acceptance. Existing captures are diagnostics, not a passing release gate.

### 8. [Implementation Readiness] — Severity: Major

- **Affected Scope:** target lines 112–116, rollback sequencing.
- **Discrepancy Description:** A full revert can expose retained paper sections through older ordinary chunking; saying they need refresh does not specify safe order or verification.
- **Rationale:** Rollback must preserve stored work without creating an unprotected evidence path.
- **AI Suggestion:** PROPOSE FIX.
- **Proposed Edit:** Replace the rollback sentences with:
  > To stop future enrichment, revert sources.py to a84b340 while retaining paper_text.py and the packet-aware RAG/context code for already stored evidence. This requires no data deletion. Before a full code rollback, disable public Ask access and back up the data store. Refresh affected workspaces through the enrichment-disabled backend's normal POST /workspaces/{workspace_id}/ingest path. Verify that active sources and chunks no longer contain full-text packet sections before reverting packet handling and reopening Ask. Provider failures/no matches can retain old evidence, so a successful HTTP response alone is insufficient; keep compatible packet handling until the check passes. Preserve archived evidence revisions, annotations and saved answers through the existing store replacement path. No automatic store restoration or user-work deletion is authorized by this plan.

## Measured work completed before the resolution gate

- 671 API tests passed; two existing websocket deprecation warnings.
- All three initial code blockers were fixed and independently reread by the Codebase Details reviewer.
- The default-model four-case HTTP comparison returned four conversational routes in 17.84, 18.89, 15.34 and 10.06 seconds. This is not four semantic passes.
- Full-text indexing corrected the sampled treatment-arm direction relative to the abstract-only answer. It retained all seven Results paragraphs, with 21 body paragraphs total; the oversized table was omitted whole.
- Source-based answer review still found missing ±0.11% dispersion in the main result and follow-up. The generic uncertainty-prompt candidate also omitted these figures and is not promoted. The between-arm interval in figure captions was outside the selected evidence; the parser explicitly excludes figures. Caption-text ingestion is a concrete next experiment, separate from image/OCR interpretation.
- No paid inference, local GPU, quota bypass or deployment. Browser workflow and a second independent paper remain unchecked.

Requested next decision: approve these document repairs, request an interactive
breakdown, comment on the target/report, or continue without applying them.
