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

- 38 backend tests pass, including provider timeout/unavailable mode, output validation, invented citations, copied passages, follow-up retrieval, source-scope enforcement, cross-workspace rejection, save/remove brief lifecycle, and current review counts.
- TypeScript and production build pass. Google Fonts require network during build.
- Browser exercised existing workspace, Ask, saving to brief, and follow-up retention with the real local API. Console showed no warnings/errors during this flow. The downloaded Markdown was inspected and contains the saved answer, citations, generation mode, gaps, and next steps.
- Independent baseline browser assessment covered desktop and mobile. Mobile navigation relies on horizontal scrolling and its last items are not initially visible. The source diagram is partially obscured by the launcher; these are lower-priority design follow-ups.

## Local model and answer-quality review

The user chose local generation after an OpenAI request returned `credit_balance_exhausted`. Ollama 0.32.14 and Qwen3 8B (approximately 5.2 GB) are installed on the development Mac with 16 GB RAM. Local generation is the default. The launcher starts a loopback-only runtime with cloud features disabled; the client sends no authorization header and never falls back to a paid provider. Tests cover those boundaries and reject cloud model tags.

The persistent 100-generated-answer alert includes successful local answers at zero API cost. Optional OpenAI mode retains the separate US$0.10 cumulative cap; switching providers does not reset it. Local test answers count toward the alert.

Live testing uses a temporary copy of the existing metformin workspace, preserving its saved answers. Initial tests found clinically meaningful wording errors: combination-label warnings were attributed to metformin alone, and “not studied” became “not recommended.” Citation formatting checks did not catch these semantic errors. Instructions were tightened to preserve product identity, distinguish missing information from contraindications, recheck prior claims, and keep citations attached to the source that supports each claim. These are prompt mitigations, not a proof of medical reliability.

Final live rerun: all three responses passed structural validation and were conversational, taking 48, 58, and 94 seconds. API spend remained US$0.00. Semantic review still failed: the model repeated the pancreatitis restriction error and combination-product attribution errors despite the updated prompt. These answers are not evidence that chat quality is resolved; further model or grounding changes are required before deployment. Six successful local test generations are recorded in the persistent counter.

Local generation is appropriate for a research prototype with source inspection. Public release still needs a representative semantic evaluation, including numerical fidelity, contradictory sources, missing evidence, and follow-up accuracy. Static reliability targets are not measured accuracy. Public hosting also needs its own inference architecture: deploying the frontend cannot connect visitors to this Mac's loopback model.

The JSON store remains a local prototype without authentication, multi-process transactional writes, or deployment-specific rate limiting. These need a deployment architecture decision when deployment starts; this review does not claim public-production readiness.
