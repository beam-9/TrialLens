# Registry design verification — 23 October 2026

## Scope and result

The user approved composition A, **Registry**, and requested a minimal, intuitive research dashboard with restrained Framer Motion and GSAP interactions. They explicitly authorized design work while free inference evaluation waits for the daily allowance reset. The earlier instruction to finish answer-quality work before design is superseded for this phase; answer-quality promotion and deployment remain pending.

The replacement removes the decorative hero and provenance field. A persistent research index, recent workspaces and source inventory frame the evidence table. Ask puts its composer before the current answer and previous questions. Secondary review filters, suggested questions and diagnostic evidence notes use native disclosures. Brief prioritizes chosen answers, export and an actionable empty state; workspace context is secondary.

The user then requested stable workspace ordering, smoother selection/hover transitions and closer fidelity to the supplied Registry comp. The desktop creation form now lives in a compact 72px header, duplicate header links are removed, and source inventory sits beside the evidence table on wide screens. Once a workspace is loaded, mobile collapses creation under **New workspace** and retains the horizontal five-view index beneath a 64px header. Narrower screens place inventory below the table. Source filter counts come from the current source records.

Reopening updates workspace metadata in place instead of moving the chosen entry to the top. Existing entries retain their positions; newly created workspaces can still enter the recent list. Workspace records, evidence and saved conversation load together before the display changes. Existing desktop workspace switches preserve scroll position, and selecting the current workspace does not refetch it. A pending indicator names the workspace being opened.

Source inspection, review actions, filters, conversation source scope, follow-ups, citations, saved answers and export retain their existing API behavior.

## Motion

- Framer Motion reveals a newly accepted answer over 180ms using opacity.
- Shared-layout spring highlights travel between stable workspace entries and between views. Hover feedback moves an available workspace row by 2px over 180ms. Incoming workspace/view content uses a 240ms opacity/3px transition; asynchronous loads do not clear the old content midway through the switch.
- GSAP uses a scoped `useGSAP` hook to update the four source counts over 220ms with a 25ms stagger, then clears temporary transform/opacity styles.
- Both respect reduced motion. GSAP match-media and hook cleanup revert on updates/unmount. There are no decorative loops, scroll effects or perpetual page animation.

## Verification

- TypeScript and ESLint pass.
- Production build passes. A sandbox CSS-worker port restriction initially caused Turbopack to cache an error; replacing the generated cache and rebuilding with the required local-process permission succeeded. No application workaround was added.
- The closer-comp iteration exposed an existing 350ms scroll fallback: near the top of the compact page it assigned `#workspace`, causing the hash listener to select Evidence after Ask. The fallback was removed; explicit tab selection now owns its route anchor. Browser coverage was strengthened to assert selection persists beyond that delay, including on a loaded workspace. The first compact-layout run had 10 passes and four Ask/follow-up failures from this delayed hash reset; it was not represented as a pass. The corrected run passed all 14 tests.
- **14/14 browser tests pass in 16.8 seconds**, with no retries. Tests cover creation/validation, source and review filters, inspecting and reviewing rows, scoped Ask/follow-ups, failure recovery, saved answers/export, theme persistence, responsive navigation, the 100-answer alert and quota fallback. Existing assertions were updated for the new heading, disclosures, tab navigation and current-answer save location. A regression covers stable workspace order/current selection, and delayed assertions verify a selected tab and its anchor remain selected after 500ms. Reduced-motion transition durations are checked.
- Integration tests use the existing isolated fixture API, temporary stores and deterministic responses. Outbound inference is blocked. No real Cloudflare answers or local model calls were made in this phase; these tests establish application behavior, not generated-answer quality.
- Desktop/mobile, light/dark, enlarged text, keyboard focus and reduced-motion checks were batched. Initial findings were fixed together: mobile builder height, compact header overflow, theme-icon alignment and inherited fixed text line heights.
- Final compact-layout suite passed **14/14 in 16.8 seconds** after the review fixes. The first attempted final run could not launch Chromium inside the macOS sandbox; the permitted browser launch passed outside it. No failing application case was bypassed.
- The Impeccable detector ran once on the changed UI targets and returned `[]`.
- Final browser measurements found no document overflow at 320, 390 or 1440px; the mobile theme control is 44×44px. Forced 200% text retained usable controls/status copy. Browser errors/warnings and idle running animations were both zero; keyboard focus remained visible.
- Actual safety-copy contrast in light/dark respectively: adverse-report disclaimer **12.70/13.43**, row safety text **6.01/8.49**, Brief safety note **5.65/7.88**. These checks exceed the 4.5:1 text threshold. Detailed measured evidence is in `design-dashboard-browser-results-2026-10-23.json`.

Screenshots and transient browser artifacts are local under `output/playwright/design-compact-*`; they use frozen evidence/test responses and are not new live research findings. The approved concept contained illustrative facts; those facts were not copied into the app.

## Finish review and verdict

The first fresh read-only design review passed the Registry direction. After the user requested closer comp fidelity and smoother selection, the independent reviewer found two P2 issues: Brief/Reliability hashes did not restore the visible view, and enlarged workspace labels overlapped. Both were repaired in one batch. Final verification exposed cramped table text at 200%; scalable table width, line heights and action heights repaired that too.

The review agents then reached their usage limit. The final verdict and document reconciliation were completed in-thread using the skill's fallback roles; this final confirmation is not represented as an independent review.

| Material finding | Verdict | Evidence |
| --- | --- | --- |
| Brief/Reliability URL and view disagree | Resolved | Complete shared five-view mapping; all five selection/hash/reload cases pass |
| Enlarged recent-workspace labels overlap | Resolved | 24px text uses 36px line height, with a measured 3px title/intervention gap; recaptured desktop 200% image |
| Enlarged table text/actions cramped | Resolved | Table scales to 1624px within its scroll container; document remains 1440px; review/action controls grow to 43–46px and remain readable |

Remaining material findings: **clear**. Final disposition: **ship** for this design scope. This does not approve model-answer quality or deployment.

The compact builder originally suggested as optional by the reviewer is now implemented following the user's explicit request. `DESIGN.md`, its sidecar and both surface briefs describe the final build. The latest measured evidence is `design-compact-browser-results-2026-10-23.json`; the earlier dashboard report remains as iteration history.

## Remaining release issues

- The semantic answer-quality failures documented in `iteration-status-2026-10-23.md` remain unresolved. This design work does not promote an experimental prompt or weaken citation/copying guards.
- The free inference ledger and provider limits remain intact. No paid fallback or local GPU inference was introduced.
- `npm audit` reports three moderate entries from the existing Tailwind 3/PostCSS selector-parser dependency chain (one underlying selector-parsing CPU exhaustion advisory). No high/critical entries were reported. The suggested automatic fix is a major Tailwind migration; this was not bundled into the design change. The application does not accept user-supplied CSS for its build.
- Existing deployment scope still needs a host decision, account/workspace ownership and backup/restore review. No deployment occurred.
