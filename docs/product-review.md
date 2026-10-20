# TrialLens product assessment

Assessment updated 20 October 2026. Reviewed the current implementation and iterated with separate chat-quality, design/browser, and deployment agents. This report supersedes the September prototype assessment; retained evaluation traces include earlier failures so improvements are inspectable.

## Purpose and what to keep

TrialLens helps biomedical researchers move from a question to understandable, inspectable evidence, then retain useful findings for a research handoff. Its strongest features are the source-level evidence table, supporting passages, citations, review controls, document inspection, recent workspaces and saved-answer brief. Keep the mineral palette, restrained teal and condensed headings: a quiet research utility suits this task.

The product is an evidence navigation workspace. Indexed abstracts, registry descriptions and regulatory excerpts are a bounded source set, not a comprehensive literature review or a clinical treatment recommendation. Accurate writing must preserve that distinction.

## Completion assessment

The core workflow is implemented, including persistent question history, source-scoped follow-ups, citation inspection, reversible saved notes and Markdown export. The Brief now serves a distinct purpose: a researcher selects useful answers, sees current review gaps and next steps, and exports working notes. It no longer duplicates the first abstracts automatically.

The next appropriate milestone is a **trusted private pilot**. A public multiuser launch still needs a chosen inference host and protected access architecture, plus deployment-host smoke tests. The shared installation has no accounts or workspace ownership. Publishing a frontend alone does not make the local model available. An arbitrary completion percentage would hide these concrete gates.

## Functionality and trust improvements

- **Conversational Ask:** local Qwen3.5 9B drafts and revises against supplied evidence, supports follow-ups, validates exact citation identifiers and rejects long copied passages. Invalid or unavailable generation visibly falls back to source excerpts. It never automatically switches to paid generation.
- **Open-ended retrieval:** broad summaries diversify relevant sources before truncation; combined benefit/safety questions retrieve both facets. Narrow question rankings and source filters remain covered by regressions.
- **Clarification and limits:** unresolved comparisons ask which treatments the user means. Unsupported questions can give conversational explanations of what is missing. Numerical fidelity, product identity, absent outcomes and contradictory findings are checked with live diagnostic fixtures; see the separate semantic review for actual results and remaining errors.
- **Usage:** the persistent 100-generated-answer alert remains. Successful local answers count at zero API cost. Optional paid mode retains the US$0.10 cumulative cap. Single-process admission control prevents overlapping local generations from queuing indefinitely.
- **Evidence discovery:** empty searches never manufacture demo records. Source-service failures are distinguished from no matches and reported as coverage warnings. A failed empty refresh preserves existing evidence.
- **Provenance:** new FDA records use stable identifiers and exact API record links, retain safety/clinical-study sections and label metadata. PubMed XML parsing preserves inline text and numerical values. Old source snapshots are not silently relabeled as newly fetched evidence.
- **Persistence:** full mutations hold a process file lock; complete snapshots replace JSON atomically. Concurrent saves preserve all records in the regression. Identical-source refreshes retain source IDs and reviewed extraction corrections; changed evidence requires fresh review.
- **Interface:** current research focus stays visible, actionable errors appear at the workspace, local generation has honest elapsed feedback, mobile tabs use matching keyboard orientation and controls have comfortable touch targets. Reduced motion and keyboard focus are respected.
- **Deployment path:** browser requests use a same-origin server proxy. Compose packages a private shared installation with persistent data/model volumes and only a loopback web port. Instructions cover provisioning, access protection, backups and rollback.

## Verification and limits

67 backend tests, 8 production-browser regressions, ESLint, TypeScript and a clean-install production build pass. Manual browser checks also verified source inspection, Brief save/export/remove and restored QA flags. Browser evidence is recorded in the linked design review. Production dependencies report zero published advisories; nine build/lint-toolchain advisories remain documented separately in the deployment review. Structural validation and passing mocked-provider tests are not measurements of biomedical accuracy. The real local-model diagnostic cases are small and partly synthetic; they do not justify an accuracy percentage.

The JSON store is suitable for the current small shared pilot after its locking fixes; a transactional, ownership-aware database remains the better public multiuser architecture. Ingestion is bounded (currently five PubMed matches, five registry summaries and three labels), registry posted-results tables are not ingested, and full papers may contain decisive information absent from abstracts.

The four QA-generated browser answers are visibly marked with their failed or partial semantic review and remain unsaved; original user answers were preserved.

No public deployment was performed. Docker configuration is validated, but the Docker daemon was unavailable for image/startup/restore testing. A chosen host must pass real inference, restart/persistence, access-boundary and slow/error-path checks before users are invited.

## Detailed evidence

- [Chat quality and retained semantic failures](chat-quality-review.md)
- [Design and browser review](design-review-2026-10.md)
- [Deployment readiness and release gates](deployment-readiness.md)
- [Private pilot operations](private-pilot.md)
