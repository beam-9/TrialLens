---
version: 1
slug: "apps-web-app-page-tsx"
primary_target: "apps/web/app/page.tsx"
related_targets: ["apps/web/app/layout.tsx","apps/web/app/globals.css"]
---

# TrialLens primary workspace

## Scope and mode

- Target: `apps/web/app/page.tsx`
- Mode: Operate
- Surface: the single-page workspace launcher and research evidence workspace

## Audience, job, action, and constraints

- Biomedical researchers and evidence reviewers define a condition and intervention, retrieve public evidence, inspect extracted source rows, ask cited questions, and review source detail.
- The primary action is `Build workspace`. Reopening a prior workspace is secondary.
- Preserve every existing API workflow, route anchor, filter, review state, loading state, empty state, and error state.
- Keep the medical-scope disclaimer and do not invent evidence or commercial claims.
- Ship persistent light and dark modes with a keyboard-accessible switch in the top-right utility area.

## Approved direction

- Direction: Evidence Ribbon, composition C.
- Approved comp: `.impeccable/mocks/evidence-ribbon-c.png`.
- Memorable moment: one diagonal provenance current links the research focus, four source families, extraction workspace, and selected-source detail.
- Carry forward from composition B: source streams visibly converge before synthesis.

## Fidelity inventory

| Ingredient | Commitment | Medium |
| --- | --- | --- |
| Navigation | 64-72px, single line, wordmark left, primary anchors centered/right, theme switch at far right | semantic HTML and Lucide icons |
| Display type | compressed grotesk silhouette, high weight, maximum 6rem, no serif | local `Arial Narrow` style stack with system fallback |
| Body type | neutral sans with clear dense-data legibility | existing local Geist font plus system fallback |
| Evidence current | wide diagonal field with four thin provenance streams converging into one | responsive CSS geometry and motion-safe transforms |
| Workspace launcher | crisp labels and inputs inside a softly irregular flow zone, not a floating generic card | semantic form and CSS mask/radius |
| Application shell | narrow vertical tab rail on desktop, horizontal scrollable rail on mobile, broad content field | existing Base UI tabs and semantic content |
| Selected source | right-side inspection sheet preserving focus and keyboard behavior | existing Base UI sheet |
| Theme | cool near-white light mode and deep graphite dark mode; mineral teal remains the only accent | CSS semantic tokens and persisted class preference |
| Corners and lines | 14-18px panels, small pills only for compact statuses, 1px rules | shared CSS tokens |
| Elevation | soft offset depth without glow; borders and shadows are not stacked indiscriminately | shared CSS tokens |
| Motion | one authored source-convergence entrance plus direct interaction feedback | Framer Motion and reduced-motion fallbacks |

## Unresolved decisions

- None blocking. The comp's numbered instructional labels will not be copied because the live workflow and controls already make the order explicit.
