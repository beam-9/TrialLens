# Evidence dashboard refinement

## Design review and direction

TrialLens is a React/Next.js web research workspace. The screen's job is to help researchers scan source-level extractions, find the relevant record and inspect its attribution. Its defining element remains the evidence registry and its persistent workspace index. Apple's accessibility, hierarchy and motion principles apply here; native macOS window/menu conventions do not.

The existing understated surfaces, system-style Geist typography, teal primary action and stable workspace order work well. Keep them. The main craft issue was oversized excerpt rows competing with navigation and hiding the next source below the fold. Text search was missing, and switching tabs remounted the entire content frame. This iteration improves that workflow rather than introducing decorative dashboard metrics or a new visual identity.

References read:

- `layout.md › Visual hierarchy`: “Use progressive disclosure to make layouts cleaner and easier to interact with.” Full result text and safety notes remain available through an explicit disclosure and Inspect.
- `lists-and-tables.md › Content`: “Keep item text succinct so row content is comfortable to read.” Four-line previews reduce initial row density without deleting stored text.
- `motion.md › Providing feedback`: “Aim for brevity and precision in feedback animations.” Panels enter in 180 ms with opacity and a 4 px translation; the header and workspace context stay in place.
- `motion.md › Best practices`: “Make motion optional.” Framer Motion respects the user's reduced-motion preference; CSS also removes transitions and smooth scrolling.
- `accessibility.md › Speech`: “Let people use the keyboard alone to navigate and interact with your app.” Keep Base UI tab semantics and keyboard behavior, labelled search, visible focus, and disclosure state.
- `sidebars.md › Best practices`: “In general, show no more than two levels of hierarchy in a sidebar.” Existing view and workspace groups stay shallow and in stable order.

Also reviewed typography, color, designing-for-macOS and cross-platform references. Sources are the local Apple Design skill's `references/hig/` files; these are the headings actually used for the changes.

## Compact design system

Existing semantic tokens are retained. Measured text contrasts against the main content surface:

| Role | Light | Dark | Light / dark contrast |
| --- | --- | --- | --- |
| Content surface | `#fdfdfa` | `#1c231e` | — |
| Secondary surface | `#f4f5f0` | `#171e19` | — |
| Primary text | `#2d312d` | `#ebefe7` | 12.97 / 13.78 |
| Secondary text | `#62695f` | `#b4bfb0` | 5.56 / 8.42 |
| Action / selected state | `#30554e` | `#9ec5b5` | 8.13 / 8.49 |
| Input boundary | `#858e80` | `#81937f` | Structural role, not text |

Geist remains the single face. Workspace title 24 px, view title 20 px, table/navigation 13 px, utility labels 12 px; mobile search uses 16 px to avoid input zoom. Hierarchy uses weight and spacing. New search-clear and disclosure controls meet 44 px touch height on compact layouts; mobile tabs increase from 42 to 44 px.

Regular layout: persistent header and index frame the dominant evidence table. Compact layout: horizontal scrolling view tabs, disclosed workspace controls, full-width search and an independently scrollable table.

```text
Regular                         Compact
Header: builder + utilities      Header
Index | Workspace context       View tabs →
      | Source filters           Workspace controls
      | Search       Row count   Context + source filters
      | Evidence previews        Search + row count
      | Expand / Inspect         Evidence table ↔
```

Product-specific restraint: preserve source IDs, inspection and review controls; avoid adding charts or unsupported evidence-quality scores. Remove the always-open secondary excerpt text from the initial table view, with a visible “Expand result & safety note” action where applicable. This is a preview, not a new scientific summary. No answer-quality or source-content changes are implied.

## Implementation

- Search titles, citation IDs, extracted result/supporting text and safety text locally; combine with existing filters. Live matching-row count, labelled clear action and recoverable empty state. No network or inference call on search.
- Expand/collapse each result with an accessible name, `aria-expanded` and `aria-controls`. Original supporting source and review actions remain available.
- Keep the workspace frame mounted. Individual Base UI tab panels use Framer Motion for a short entry, retaining panel roles and active selection. Workspace selection continues to travel between stationary rows.
- AnimatePresence handles the search-clear and optional safety-note fades. No animated heights, stagger delays on frequent table interactions, continuous motion or new dependencies.

## Verification

Lint, TypeScript and production build pass; `git diff --check` passes. Expect browser verification passed:

- Source-ID search returns the matching row, a nonexistent query returns the recoverable empty state, and Clear filters restores all 11 matches. “See more” reveals all 11 rows.
- Result expansion reveals the safety note and updates `aria-expanded`; collapse restores the preview. Inspect opens NCT00545844 and its original-source link.
- All five views expose exactly one matching visible tab panel. Desktop navigation is vertical; compact navigation is horizontal. Arrow-key focus follows that orientation, with manual activation. Switching diabetes → asthma retains workspace order.
- At 320 and 390 px the document and body widths equal the viewport. The table and tab strip scroll inside their own containers. All compact tabs measure 44 px tall.
- Dark appearance remains legible. Reduced motion sets scroll behavior to `auto` and CSS transition duration to 0.00001 s; the new Framer transitions use zero duration. No continuous or staggered motion was added.
- No console errors or failed requests were captured. Recorded requests returned HTTP 200; repeated read-only workspace/usage requests were observed. No source, review, brief or answer data was changed.

The evaluation ledger stayed at 8,125.692182 / 9,000 neurons used or reserved, with 33 requests. This UI work made no inference calls. The quota had not reset when checked; chat quality remains a separate unresolved workstream.

Screenshots: [desktop](ui-results/2026-11-02/evidence-desktop.png), [compact dark / reduced motion](ui-results/2026-11-02/triallens-mobile-dark-reduced-motion.png). Testing overlays are excluded only from screenshot capture. Low-end physical hardware, frame-rate profiling and assistive-technology audits were not performed; desktop browser checks do not imply those validations.
