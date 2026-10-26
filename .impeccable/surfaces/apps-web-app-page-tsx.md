---
version: 1
slug: "apps-web-app-page-tsx"
primary_target: "apps/web/app/page.tsx"
related_targets: ["apps/web/app/layout.tsx", "apps/web/app/globals.css"]
---

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
- User language: minimal, clean, intuitive research dashboard; not cluttery. The visual refinement follows the three user-pinned references: soft desktop panels and a quiet sidebar, warm cream with ink, and rounded selection. The Registry information architecture remains in place.
- Approved comp: `/Users/beam.t/.codex/generated_images/01a079a4-6b0c-7d33-a374-a82d0b7fa0a6/exec-cbf87a13-1352-46fd-8ea4-dd3c269e89e1.png` (A only).
- Built direction contract: `apps/web/app/layout.tsx`.
- Global visual authority: `DESIGN.md`; sidecar: `.impeccable/design.json`.

## Fidelity inventory

| Ingredient | Implemented expression |
| --- | --- |
| First viewport | 18px desktop inset around a 1560px research window with 22px corners; 72px header with compact builder, 224px persistent research index, dominant evidence table and right inventory; 64px mobile header |
| Typography | Geist throughout; compact 25px introduction, 20px view headings, readable 15px answer text |
| Palette | Warm cream canvas (#ecede8), paper (#fdfdfa), soft gray-green secondary surface (#f4f5f0), dark ink (#2d312d), muted deep teal (#30554e); semantic dark theme |
| Working panels | Quiet secondary sidebar, paper-white 16px panels and inventory, 12px rounded selection, thin separators; no decorative hero |
| Index | Five views with matching hash/reload state; stable workspace entries with a moving selection highlight; source counts beside Evidence and in the index for other views |
| Evidence | Source-type filters, disclosed review filters, inspectable extraction table and source sheet |
| Ask | Question composer, one readable cited answer, caveats, source links, optional supporting disclosures and expandable history |
| Brief | Explicitly saved research answers, export/remove controls, disclosed workspace context |
| Mobile | Sticky horizontal tab strip; loaded creation collapsed into New workspace; stacked fields, wrapped content, local table scrolling |
| Theme | Accessible switch, localStorage and cookie persistence, server cookie initialization, system fallback |
| Motion | Framer shared-layout selection spring 440/38; hover 2px/180ms; pane 240ms; answer reveal 180ms; GSAP inventory 220ms/25ms stagger; cleanup and reduced-motion support |

## Evidence and status

Measured browser QA is recorded in `docs/design-dashboard-browser-results-2026-10-23.json`. Rendered evidence is recorded in `output/playwright/design-final-viewport-desktop-evidence.png`, `output/playwright/design-final-viewport-desktop-ask.png`, `output/playwright/design-final-viewport-desktop-brief.png`, `output/playwright/design-final-viewport-mobile-ask.png`, `output/playwright/design-final-viewport-mobile-dark-ask.png`, and `output/playwright/design-final-viewport-mobile-text200.png`.

The 2026-10-26 refinement was verified in desktop/mobile Evidence and Ask, dark mode, and enlarged text. See `docs/design-refinement-2026-10-26.md` and `docs/functional-results/soft-registry-round2-2026-10-26.json`. Evidence text expands fully; long identifiers may still wrap at 200%. This visual check does not establish biomedical answer quality or deployment readiness.

## Latest interaction verification

Opening a workspace updates metadata in place and retains entry order. Related evidence and conversation load before display changes. Current selection is a no-op. Existing desktop switches preserve scroll position. All five view hashes restore selection on reload. Workspace labels use unitless line spacing; the table uses 58em minimum width and scalable text/actions for enlarged type. See docs/design-compact-browser-results-2026-10-23.json for measured motion and confirmation evidence.
