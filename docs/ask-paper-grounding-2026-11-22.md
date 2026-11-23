# Ask paper grounding — 22 November 2026

Status: implementation and source-ingestion tests complete; hosted answer-quality
checks are in progress. This is not a claim that Ask is complete or ready to deploy.

## Problem and research

TrialLens fetched only the top five relevance-ranked PubMed abstracts. It could
not retrieve results that appeared only in the paper body or tables. Separately,
the November 16 experiments showed omission, incorrect attribution and numerical
misinterpretation even with relevant evidence present. More data alone cannot
establish answer accuracy; both ingestion and interpretation need verification.

The research supports keeping related evidence together and evaluating retrieval
separately from generation. QASPER studies multi-paragraph paper answers;
Lost in the Middle demonstrates position sensitivity. Their findings motivate
our context tests, but do not establish clinical accuracy for TrialLens.
Citation membership is also distinct from claim support, as evaluated by ALCE.

Primary references:

- [QASPER](https://aclanthology.org/2021.naacl-main.365/)
- [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/)
- [ALCE](https://aclanthology.org/2023.emnlp-main.398/)
- [Europe PMC open-access full text](https://dev.europepmc.org/downloads/openaccess)
- [JATS table wrapper](https://jats.nlm.nih.gov/articleauthoring/tag-library/1.4/element/table-wrap.html)

## Implemented file boundaries and behavior

Create `apps/api/triallens/paper_text.py` and `apps/api/tests/test_paper_text.py`.
The parser API is `parse_paper_text(xml: bytes, expected_pmid: str,
expected_pmcid: str) -> (sections, indexing_metadata)`. No inference or numerical
calculation occurs here. It validates the article's own PMID and PMCID against
those selected by PubMed. Ambiguous or mismatched identities fail closed.

XML input is capped at 2 MiB and 64 levels of nesting. Internal DTD subsets,
entity declarations, null-byte encodings and malformed XML are rejected.
External-only JATS DOCTYPE declarations are removed without resolution.
Metadata retains the original XML SHA-256, article identifiers, a bounded license
statement/link list, and explicit missing/truncated license flags.

Body paragraphs preserve inline text and section ancestry. Results precede
Methods, Discussion and other sections when filling limits; stable section keys
retain source-document paragraph ordinals. At most 24 paragraphs and 16,000
paragraph characters are retained, with each paragraph at most 8,000 characters.
Abstracts, references, figures and supplements are excluded from body prose.

At most six supported tables are retained as complete semantic table-wrapper
XML, including caption, headers, row/cell relationships and footnotes. Body and
article-level floats are inspected. A table must have a nonempty column-header
row, rectangular rows and no merged or nested cells. Unsupported or oversized
(above 8,000 characters) tables are omitted whole, never guessed or flattened
into ambiguous values. Omission counts/reasons and partial indexing are explicit.

Modify `apps/api/triallens/sources.py`. `PubMedClient` retains each original
abstract, PMID, PubMed URL and ranking. It reads an existing `ArticleId` with
`IdType=pmc`, accepts only a `PMC` identifier followed by positive decimal digits,
and fetches at most two linked papers per source refresh, sequentially, from
`https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML`.
Article text cannot choose a URL or initiate another fetch. Redirects are disabled.
Each full-text read has a seven-second overall deadline and a 2 MiB decompressed
limit. A failed, unavailable or unlinked paper keeps its abstract and records an
unavailable reason; later papers beyond the cap record `fetch_limit`.

Successful metadata adds `full_text` and `paper_packet_version=1`, plus the
emitted sections under the existing `metadata.sections` dictionary. No source
identity is replaced and no existing source is deleted. Missing license metadata
is disclosed; it is not a reuse authorization. Article-level terms remain relevant.

Modify `apps/api/triallens/rag.py`. `atomic_passage_limit` recognizes explicit
parser-emitted paragraph/table section lists, alongside existing registry
outcomes. These packets are indexed intact instead of being split at 92 words.
Ordinary passages retain their existing path. Packet normalization changes only
whitespace, preserving footnotes and numerical qualifiers. Content-scope wording
distinguishes abstract-only records from partial enriched articles. Existing
structured extraction summaries still derive from abstracts; they must not be
represented as a full-text extraction.

Modify `apps/api/triallens/conversation.py`. Keep exact citation/source admission,
eight-source/four-passage limits and the 28,000 source-text character budget.
Verify an atomic passage against its own stored section and omit altered or
oversized fragments. Use the existing all-or-omit budget allocation. Supply
section-to-passage links, bounded full-text provenance, abstract/body distinction,
and partial-context flags to both generation passes. Citation grounding, numerical
checks, source-copy rejection, treatment boundaries and quota accounting remain.

Create `apps/api/tests/test_paper_pipeline.py` and the generated frozen cohort
`apps/api/evaluation/cohorts/paper-grounding-2026-11-22/*.json`. These verify
fetch fallback, exact identity/provenance, complete packet retrieval, context
budgets, footnote retention and delivery of new results to both Ask passes.
The mocked generation test establishes plumbing, not semantic answer accuracy.

## Real-paper diagnostic and rollout checks

ATOMIC is PMID38763510 / PMC11307122. Its Europe PMC XML was fetched from the
fixed endpoint; its SHA-256 is recorded in the cohort inventory and source metadata.
The article license is CC BY-NC 4.0; the retained excerpt snapshot preserves its
attribution and license. The parser retained all seven Results paragraphs among
21 selected body paragraphs and omitted 11 paragraphs by budget. Its one large
table exceeded the complete-packet limit and was omitted, with the reason recorded.
The indexed body describes the HbA1c changes by arm differently from the abstract's
reported ordering. Answers must name the consulted section rather than silently
repairing the abstract or treating either ordering as universally verified.

The frozen abstract/full-text snapshots use separate workspace/source IDs to
prevent state overlap. They preserve the same PMID and the original abstract.
The comparison keeps the production model and prompts unchanged and runs through
the actual isolated HTTP Ask API, including follow-up and unsupported-outcome
questions. Review each displayed answer against its captured context; valid JSON
or an accepted generation route is not a semantic pass.

No paid API, local GPU, new inference provider, source migration or deployment is
introduced. Existing workspaces need an explicit normal source refresh to gain new
content; saved answers retain their original source revisions. Reverting these
changes stops future enrichment; existing enriched source records would require
refresh under the older code before their stored full-text sections disappear.

Remaining release gates: finish the hosted comparison; audit arm/value/direction,
units, timepoint, missing uncertainty, source-scope claims and conversational
follow-ups; add another independent open-access paper; check the actual browser
workflow; and run broader existing answer holdouts before claiming Ask complete.
