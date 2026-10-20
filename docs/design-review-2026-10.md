# TrialLens design review — October 2026

## Summary

Overall: **Good** for a private research pilot, subject to the separate answer-quality and deployment checks. This is a responsive Next.js web app for people exploring biomedical evidence. Its job is to connect a research question to inspectable sources, then preserve useful answers in a brief. The mineral surfaces, condensed display type and teal evidence ribbon give it a recognizable identity; keep them.

This review applies Apple’s foundations and interaction principles to the web. Native macOS menu-bar and iOS tab-bar conventions are not requirements for this website. Reviewed references: accessibility, layout, typography, color, designing-for-macos, generative-ai, loading, writing, and cross-platform translation. Real browser checks used the expect tools at localhost port 3001.

## Improvements implemented

- **High — visible error recovery.** Ask, save and review errors formerly appeared only in the launcher above the workspace. Workspace errors now appear next to the work area, receive keyboard focus and scroll into view. JSON errors show their useful detail; HTML proxy errors become a recovery message. `writing.md › Best practices`: “display it as close to the problem as possible”.
- **High — keyboard navigation matches layout.** The Tabs wrapper omitted the actual Base UI orientation prop. It now passes that prop; the workspace chooses vertical above 900 px and horizontal below. Verified desktop ArrowDown moves focus Ask → Sources and mobile ArrowRight moves Evidence → Ask. Enter selects the focused tab. `accessibility.md › Speech`: “Let people use the keyboard alone”.
- **Medium — touch controls.** Small filter and row buttons were 24–28 px tall. At compact widths button controls now have at least 44 px height, with wrapping labels. At 390 px, measured visible filters were 44 px and the build button 48 px. `accessibility.md › Mobility`: “Offer sufficiently sized controls.”
- **Medium — loading is understandable.** Generation now has a visible spinner, factual status, elapsed seconds, and permission to browse other workspace views. It does not invent completion percentages or pretend to advance through timed processing phases. The composer is disabled while its question is pending so completion cannot erase newly typed text. `generative-ai.md › Outputs`: “Factor processing time into your design.”
- **Medium — context and provenance.** The current condition, intervention, source count and evidence-row count stay above the workspace. Persisted ingestion warnings are shown separately from an empty search. Historical records whose external ID contains DEMO are visibly marked in Sources and Inspect/table views.
- **Medium — motion and transparency preferences.** Framer Motion now receives the user’s reduced-motion setting in addition to the existing CSS overrides. Reduced-transparency users get an opaque header. A keyboard-visible skip link reaches the workspace.
- **Low — navigation and typography.** Header links prevent duplicate browser anchor scrolling, and source/review filter labels are semantic headings at 12 px rather than 10 px tracked uppercase labels.

## Token plan retained

| Role | Light | Contrast on light paper | Dark | Contrast on dark paper |
| --- | --- | --- | --- | --- |
| Paper | #FAFCFB | — | #151C1B | — |
| Content | #111817 | 17.47:1 | #EBF2F0 | 15.23:1 |
| Muted content | #4F5E5B | 6.61:1 | #A9B8B5 | 8.41:1 |
| Teal action/citation | #007973 | 5.12:1 | #3CC9BE | 8.48:1 |

These ratios were calculated from actual CSS token values, not estimated from screenshots. Translucent blends and every possible hovered/disabled state are not represented by this token table. `accessibility.md › Vision` requires checking minimum contrast in both appearances.

Geist remains body/control type; League Gothic is reserved for display headings. Data stays in readable body type with tabular numerals for elapsed time. The main view uses a quiet sidebar at regular widths and a scrollable tab strip at compact widths. The source ribbon is the signature; no additional decorative animation is needed.

```text
Regular: [research focus / counts]  Compact: [research focus / counts]
         [rail | active view]               [scrollable views]
                                            [active view]
```

The plan is specific to evidence navigation rather than a generic dashboard. One accessory deliberately avoided: adding another animated component library for the loading message. The Website Toolkit cache exists and its Planes ThinkingLoader source was reviewed. Its timer-driven phase changes and extra motion helper dependencies do not improve the truthfulness of this workflow. Existing Base UI, Framer Motion and Lucide components serve it without copying toolkit source or adding packages.

## Browser evidence and limits

- A real existing metformin workspace reopened with 14 sources and 14 evidence rows through the same-origin API proxy.
- At 390 × 844 the document width equals the 390 px viewport, with no page-level horizontal overflow. The table remains deliberately scrollable within its own region.
- Desktop and compact tab focus behavior was exercised with real keyboard events; focus had a visible 3 px outline.
- The Literature evidence filter selected correctly and showed five PubMed rows. Ask’s source selector changed the visible search context to “Searching PubMed”, then returned to all sources for the live chat checks.
- An initial automated accessibility pass found no axe violations. IBM’s output included manual “Verify/Confirm” prompts about focus, color and text resizing, plus the browser testing tool’s own injected overlay. Those prompts are not evidence of 31 confirmed product failures. Full screen-reader certification remains outside this pass.
- Production compilation and TypeScript checking passed during this iteration. Recheck after the root agent’s deployment-route changes.

Live answer, Brief export, fault recovery, dark appearance and text enlargement results are appended below as checks finish. This report does not claim clinical validation of generated answers.

## Live chat check — issue found before deployment

The first broad, open-ended request completed as a conversational local-model answer with three citations and eight retrieved passages. It explained the indicated glucose-control use and missing effect-size data, but incorrectly generalized the ZITUVIMET combination label’s “not studied in people with a history of pancreatitis” caveat to metformin as a whole. Citation validation did not catch that semantic error. This is a **High deployment blocker for claiming accurate answers**, reported to the chat-quality agent for a targeted fix and rerun. The answer also introduced an irrelevant baseline-trend caveat. The generated badge and a passing schema are insufficient quality evidence.

During the follow-up generation, switching to Sources worked. Dark appearance at 390 px retained the 390 px document width with readable mineral surfaces and distinct teal controls. No model calls used paid API credits. Production build including `/api/[...path]` passed.

A further functional issue was found in recent workspaces: server items were sliced in identifier order, and older cached duplicates overwrote newly created/server records. The merge now prefers the primary record and sorts server workspaces by creation time before deduplicating research topics. A regression test covers a newer server record against a stale cached duplicate. Responsive tab direction and failed Ask recovery also have browser regression tests.

At 200% root text size and a 390 px viewport, the page retained its viewport width. Source-family labels now wrap instead of ellipsizing so their identity survives enlarged text. This is a focused enlargement check, not a comprehensive zoom/accessibility certification.

## Iteration after the live semantic failure

The backend agent separated combination-product labels from the single-ingredient summary when standalone metformin labels exist. A fresh browser conversation showed the explicit scope note and removed the incorrectly generalized pancreatitis statement. Its reported diarrhea (53% versus 12%), nausea/vomiting (26% versus 8%) and vitamin B12 findings (approximately 7% after 29 weeks) match the standalone label excerpts. This is a targeted correction rather than proof of universal answer accuracy. Two precision concerns were sent back for review: the summary omitted the pediatric age floor and could imply a known frequency for postmarketing liver injury.

A real API restart during a save attempt exercised error recovery: the workspace showed a clear service-unavailable alert, kept the current answer and allowed a retry. No brief flag changed in that failed request. Follow-up and Brief lifecycle checks continue below.

The fresh follow-up used everyday language but omitted the preceding safety summary. That incompleteness was reported to the chat-quality agent; it must not be counted as a full semantic pass. The frontend now uses a plain source-scope note when a conversational answer supplies no uncertainty text, instead of presenting an unrelated raw safety extraction as its main “Evidence boundary”.

Brief lifecycle verification: saving the fresh answer populated one saved answer and enabled Export. A real browser download produced `triallens-research-brief.md`; its contents included the exact answer, scope note, citations with URLs, evidence gaps and next steps. Removal was interrupted when the development server stopped during the root agent’s dependency upgrade. The single QA-created saved flag was restored through the API (HTTP 200), and all four answers created by this browser evaluation are unsaved. Final browser removal/empty-state verification should run after the frontend restarts.

The main evidence table now shows actual review status rather than an unlabeled heuristic percentage. The deeper Inspect view labels that percentage “Automated extraction estimate”. This avoids presenting an extraction heuristic as measured answer accuracy (design judgment).

## Final production browser verification

After the dependency upgrade and a clean production build, the preview at `http://127.0.0.1:3001` passed **8 of 8 browser regression tests in 10.4 seconds**:

1. Light/dark preference persists.
2. A real workspace opens and all five evidence views remain reachable.
3. Ask results retain citations and progressive evidence disclosures.
4. Compact layout and contained table scrolling remain usable.
5. Responsive keyboard tab direction follows the visible layout.
6. Failed Ask requests focus a readable error, preserve the question, and allow retry.
7. Newer server workspaces supersede stale cached duplicates.
8. Conversational answers with no uncertainty list show a coherent source-scope boundary.

These UI tests mock generated Ask output; semantic quality was separately assessed through the real local-model turns above. Manual expect-tool verification of the final production build also reopened the real metformin workspace, opened Inspect and its original-source link, closed Inspect with Escape, and confirmed an empty Brief with Export disabled. All QA-created brief flags are restored to false. The full eight-test command was `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3001 npm run test:e2e` from `apps/web`.

No blocking browser failure remains in this review. Chat semantic findings and deployment readiness must still be interpreted using the final backend evaluation report; successful UI tests do not certify biomedical accuracy.
