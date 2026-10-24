# TrialLens primary workspace

## Scope and mode

- Target: `apps/web/app/page.tsx`; related implementation: `apps/web/app/globals.css` and `apps/web/app/layout.tsx`.
- Mode: Operate; user-authorized replacement visual world.
- Surface: single-page research dashboard for biomedical researchers and evidence reviewers.

## Audience, job, action, and constraints

Create or reopen a condition/intervention workspace, inspect extracted evidence, ask scoped citation-grounded questions, inspect source passages, and collect selected answers in Brief. Build workspace is the creation action; existing workspaces remain accessible from the index or mobile recent-workspace disclosure.

Preserve API contracts, route anchors, filters, review actions, loading/empty/error states, document inspection, conversations, usage limits, saved answers, and brief export. Sources include PubMed, ClinicalTrials.gov, FDA labels, and FDA adverse-event style records. Deterministic sample fallbacks remain distinguishable from live evidence. TrialLens is evidence navigation only, not medical advice or clinical decision support. Answer quality and deployment remain pending; visual completion does not establish either.

## Approved direction

- Chosen world: **A — Registry / The Evidence Registry**; grounded direction 6, seed `7c7f8aa4`.
- User language: minimal, clean, intuitive research dashboard; not cluttery.
- Approved comp: `/Users/beam.t/.codex/generated_images/01a079a4-6b0c-7d33-a374-a82d0b7fa0a6/exec-cbf87a13-1352-46fd-8ea4-dd3c269e89e1.png` (A only).
- Built direction contract: `apps/web/app/layout.tsx`.
- Global visual authority: `DESIGN.md`; sidecar: `.impeccable/design.json`.

## Fidelity inventory

| Ingredient | Implemented expression |
| --- | --- |
| First viewport | 72px desktop header with compact builder, 216px persistent research index, dominant evidence table and right inventory; 64px mobile header |
| Typography | Geist throughout; compact 25px introduction, 20px view headings, readable 15px answer text |
| Palette | Cool near-white and gray surfaces, graphite text, restrained teal; semantic dark theme |
| Working panels | Flat open sections, thin separators, regular small corners, no decorative hero |
| Index | Five views with matching hash/reload state; stable workspace entries with a moving selection highlight; source counts beside Evidence and in the index for other views |
| Evidence | Source-type filters, disclosed review filters, inspectable extraction table and source sheet |
| Ask | Question composer, one readable cited answer, caveats, source links, optional supporting disclosures and expandable history |
| Brief | Explicitly saved research answers, export/remove controls, disclosed workspace context |
| Mobile | Sticky horizontal tab strip; loaded creation collapsed into New workspace; stacked fields, wrapped content, local table scrolling |
| Theme | Accessible switch, localStorage and cookie persistence, server cookie initialization, system fallback |
| Motion | Framer shared-layout selection spring 440/38; hover 2px/180ms; pane 240ms; answer reveal 180ms; GSAP inventory 220ms/25ms stagger; cleanup and reduced-motion support |

## Evidence and status

Measured browser QA is recorded in `docs/design-dashboard-browser-results-2026-10-23.json`. Rendered evidence is recorded in `output/playwright/design-final-viewport-desktop-evidence.png`, `output/playwright/design-final-viewport-desktop-ask.png`, `output/playwright/design-final-viewport-desktop-brief.png`, `output/playwright/design-final-viewport-mobile-ask.png`, `output/playwright/design-final-viewport-mobile-dark-ask.png`, and `output/playwright/design-final-viewport-mobile-text200.png`.

An independent fresh finish review passed all five areas with no material findings before this documentation pass. This records that review result without asserting biomedical answer quality or deployment readiness. Documentation was extracted from the implemented CSS, page, layout direction contract, PRODUCT.md, and shared controls; no new browser review was performed during documentation.

## Latest interaction verification

Opening a workspace updates metadata in place and retains entry order. Related evidence and conversation load before display changes. Current selection is a no-op. Existing desktop switches preserve scroll position. All five view hashes restore selection on reload. Workspace labels use unitless line spacing; the table uses 58em minimum width and scalable text/actions for enlarged type. See docs/design-compact-browser-results-2026-10-23.json for measured motion and confirmation evidence.
