# TrialLens product review

Review method: independent design assessment (design_review) and detector/browser assessment (design_evidence), followed by implementation and functional verification. Baseline UX score: 24/40. The detector returned zero findings; that did not prove the product flows worked well. The browser detector overlay was unavailable because the supported browser evaluation API is read-only. No overlay server or temporary overlay artifacts were created.

## Purpose and what to keep

TrialLens should help a researcher move from a biomedical question to an understandable answer with inspectable support, then retain useful conclusions for a research handoff. Keep the source-level extraction table, citations, review controls, document inspection, recent workspaces, keyboard submission, mineral palette, restrained teal, and condensed section headings. These provide a distinct and useful evidence-navigation foundation.

## Problems and changes

- **P1: Chat was a sentence/template assembler.** It could output incomplete fragments while looking like a synthesized answer. Added an optional language-model generation layer instructed to explain findings conversationally and respond to follow-ups. Citations are checked against supplied records; copied 28-word runs, invalid structure, and incomplete responses trigger a visibly labeled fallback. This checks provenance and formatting, not semantic correctness.
- **P1: Follow-ups had no memory.** Answers now persist and remain available in the interface. Server-owned answer chains provide up to six prior turns; referential retrieval retains earlier research questions. New conversation and source-scope changes establish fresh context. Scope and workspace membership are validated on the backend.
- **P1: Source filters leaked.** The selected type previously filtered retrieved chunks but left all extraction rows eligible for synthesis. The endpoint now applies scope to sources, chunks, and extraction rows together.
- **P1: Brief duplicated abstracts.** Replaced arbitrary first-abstract snippets with deliberately saved answers, current review gaps, next steps, cited source links, and Markdown export. Saved material is clearly described as working notes.
- **P1: Reliability looked measured.** Static percentages are now labeled targets and scenario statuses are unmeasured. They are not evidence of accuracy.
- **P2: Research scope was easy to lose.** Ask now displays the condition/intervention and its own explicit source selector.
- **P2: Generic FDA links overpromised.** Answer links to API documentation are now labeled source documentation. Some ingested FDA records still lack a record-specific URL; improve this in ingestion before promising complete original-document provenance.

## Verification

- 29 backend tests pass, including provider timeout/unavailable mode, output validation, invented citations, copied passages, follow-up retrieval, source-scope enforcement, cross-workspace rejection, save/remove brief lifecycle, and current review counts.
- TypeScript and production build pass. Google Fonts require network during build.
- Browser exercised existing workspace, Ask, saving to brief, and follow-up retention with the real local API. Console showed no warnings/errors during this flow. The downloaded Markdown was inspected and contains the saved answer, citations, generation mode, gaps, and next steps.
- Independent baseline browser assessment covered desktop and mobile. Mobile navigation relies on horizontal scrolling and its last items are not initially visible. The source diagram is partially obscured by the launcher; these are lower-priority design follow-ups.

## Required before considering chat resolved

No `OPENAI_API_KEY` or `TRIALLENS_CHAT_MODEL` is configured in the inspected environment. Real conversational answer quality is therefore **not verified**. Mock responses prove integration behavior only. Configure the backend, then evaluate real answers for directness, semantic citation support, numerical fidelity, missing-evidence behavior, combined benefit/safety questions, and multi-turn references. Include retrieved passages outside the first 10,000 source characters and contradictory sources. Do not deploy on the strength of the static reliability targets or mocked generation tests.

The JSON store remains a local prototype without authentication, multi-process transactional writes, or deployment-specific rate limiting. These need a deployment architecture decision when deployment starts; this review does not claim public-production readiness.
