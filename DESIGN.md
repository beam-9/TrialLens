---
name: TrialLens
description: A cool-mineral evidence workspace where source provenance stays visible before synthesis.
colors:
  primary: "var(--primary)"
  primary-foreground: "var(--primary-foreground)"
  background: "var(--background)"
  foreground: "var(--foreground)"
  card: "var(--card)"
  secondary: "var(--secondary)"
  muted-foreground: "var(--muted-foreground)"
  accent: "var(--accent)"
  destructive: "var(--destructive)"
  border: "var(--border)"
  input: "var(--input)"
  ring: "var(--ring)"
typography:
  display:
    fontFamily: 'var(--font-display), "Arial Narrow", sans-serif'
    fontSize: "clamp(4.3rem, 8vw, 6rem)"
    fontWeight: 500
    lineHeight: 0.87
    letterSpacing: "-0.025em"
  headline:
    fontFamily: 'var(--font-display), "Arial Narrow", sans-serif'
    fontSize: "3rem"
    fontWeight: 500
    lineHeight: 0.98
    letterSpacing: "-0.04em"
  title:
    fontFamily: 'var(--font-sans), "Helvetica Neue", ui-sans-serif, system-ui, sans-serif'
    fontSize: "clamp(1.4rem, 2.6vw, 2rem)"
    fontWeight: 690
    lineHeight: 1.08
    letterSpacing: "-0.028em"
  body:
    fontFamily: 'var(--font-sans), "Helvetica Neue", ui-sans-serif, system-ui, sans-serif'
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  label:
    fontFamily: 'var(--font-sans), "Helvetica Neue", ui-sans-serif, system-ui, sans-serif'
    fontSize: "0.75rem"
    fontWeight: 640
    lineHeight: 1.2
    letterSpacing: "normal"
rounded:
  sm: "10px"
  rail: "11px"
  md: "12px"
  lg: "14px"
  xl: "16px"
  panel: "18px"
  flow: "20px 68px 24px 56px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  3xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "48px"
  button-outline:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "36px"
  input-workspace:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "48px"
  card-surface:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.panel}"
    padding: "24px"
  tab-active:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.primary}"
    typography: "{typography.label}"
    rounded: "{rounded.rail}"
    padding: "10px 12px"
    height: "42px"
---

# Design System: TrialLens

## Overview

**Creative North Star: "The Evidence Ribbon"**

The Evidence Ribbon makes evidence provenance the composition. Cool mineral surfaces, graphite type, and one teal signal create a trustworthy, exact workspace that feels softly irregular rather than rigid; the visual world stays sober enough for biomedical review without becoming sterile.

Four source families visibly converge into inspectable extraction rows before synthesis. Large flowing fields carry the path through the product, while the controls inside them remain compact, precise, and immediately legible. Atmospheric or cinematic research dashboards and generic equal-weight card grids are explicit anti-references.

**Key Characteristics:**

- Provenance remains visible from source families to extraction.
- One mineral teal signal organizes action, focus, and evidence flow.
- Cool paper and fog layers support graphite data typography in both themes.
- Softly irregular fields frame the entry sequence; controls remain exact and compact.
- Tonal layering carries hierarchy; shadows are reserved for floating or focal surfaces.

## Colors

The palette uses one mineral teal signal against graphite ink, cool paper, mineral fog, and a semantic safety red; the same semantic roles invert deliberately in dark mode.

### Primary

- **Mineral Teal** (`primary`): Primary action, active navigation, focus, evidence streams, source convergence, and compact positive status.
- **Primary Foreground** (`primary-foreground`): High-contrast text and icons placed on the mineral teal signal.

### Secondary

- **Mineral Slide** (`secondary`): Quiet rail backgrounds, grouped controls, and low-emphasis structured surfaces.
- **Mineral Fog** (`accent`): Hover feedback, selected-area tint, and softly layered evidence fields.

### Neutral

- **Cool Canvas** (`background`): The page ground and input fill; it becomes deep graphite in dark mode.
- **Graphite Ink** (`foreground`): Primary text, icons, rules through alpha, and the occasional ink-led synthesis action.
- **Cool Paper** (`card`): Cards, launcher, provenance band, workspace frame, and inspection surfaces.
- **Muted Ink** (`muted-foreground`): Secondary copy and metadata that must remain readable but visually subordinate.
- **Mineral Border** (`border`): Default 1px rules and component outlines.
- **Mineral Input** (`input`): Stronger field and disabled-control outlines.

### Semantic

- **Safety Red** (`destructive`): Errors, safety limitations, and evidence states that require review; never general decoration.
- **Focus Teal** (`ring`): The visible keyboard-focus system, kept semantically aligned with the primary signal.

### Named Rules

**The One Signal Rule.** Mineral teal is the only non-semantic accent; reserve safety red for risk, error, and uncertainty that needs attention.

**The Theme Parity Rule.** Light and dark modes preserve role, hierarchy, and contrast; dark mode is a semantic remap, not a decorative alternate palette.

## Typography

**Display Font:** League Gothic (with Arial Narrow and sans-serif fallback)  
**Body Font:** Geist (with Helvetica Neue, ui-sans-serif, system-ui, and sans-serif fallback)  
**Label/Mono Font:** Geist; no separate mono face is used.

**Character:** League Gothic gives the evidence path a compressed, declarative silhouette. Geist keeps controls, extraction rows, citations, and medical-scope language neutral and densely legible.

### Hierarchy

- **Display** (500, fluid 4.3–6rem, 0.87 line-height): Hero statements only; cap the line length near 7–9 characters to preserve the vertical silhouette.
- **Headline** (500, fluid 2.2–3rem, 0.98 line-height): Major workspace view titles and large evidence landmarks.
- **Title** (690, fluid 1.4–2rem, 1.08 line-height): Launcher, provenance, and section titles in the body family.
- **Body** (400, 1rem, 1.55 line-height): Explanatory copy and primary reading text, generally constrained to 58ch or less near controls.
- **Label** (640, 0.75rem, compact line-height): Field labels, rail labels, status readouts, and evidence metadata; uppercase with wide tracking only for very small category labels.

### Named Rules

**The Compression Rule.** Use League Gothic for large navigational or section landmarks only; keep evidence content in Geist so dense rows remain legible.

## Layout

The system uses a full-width canvas with centered working regions capped at 1480px. A sticky utility header is 72px tall on larger screens and 64px on small screens. The first viewport places the compressed headline to the left and the workspace launcher inside the central evidence flow; the provenance summary rises across the seam before the application shell.

The desktop application shell pairs a 184px vertical tab rail with one broad content field. At 1180px, launcher controls wrap to two columns with the action spanning the row. At 900px, the hero becomes one column and the rail becomes a sticky, horizontally scrollable strip. At 680px, launcher fields stack, the primary action fills the width, the header simplifies, provenance counts become a two-column grid, and data tables retain horizontal scroll rather than collapsing evidence fields.

Spacing follows a compact 8–16px control rhythm and a broader 24–40px structural rhythm. Thin 1px rules organize dense evidence; open gaps separate workflow stages. Responsive changes preserve the provenance sequence instead of merely shrinking the desktop arrangement.

### Named Rules

**The Visible Path Rule.** Keep the launcher, four source families, extraction shell, and cited inspection context in one continuous spatial story.

## Elevation & Depth

Depth is primarily tonal. Cool canvas, paper, slide, and fog surfaces separate layers without constant shadow; flat research cards and data rows use 1px rules. Two restrained ambient shadows are reserved for overlap and focus: soft framing (`0 24px 70px rgb(28 55 50 / 0.1)` light; `0 26px 76px rgb(0 0 0 / 0.28)` dark) and floating focus (`0 16px 42px rgb(25 51 47 / 0.13)` light; `0 18px 48px rgb(0 0 0 / 0.34)` dark). Neither uses glow.

### Shadow Vocabulary

- **Ambient Soft** (`--shadow-soft`): Provenance and workspace frames that overlap or rise from the canvas.
- **Ambient Float** (`--shadow-float`): The focal workspace launcher and similarly important floating surfaces.

### Named Rules

**The Ambient Lift Rule.** Resting panels rely on tone and 1px rules; apply ambient shadow only to floating, overlapping, or focal surfaces.

## Shapes

The form language pairs flowing asymmetry with precise controls. Large evidence fields use softly irregular percentage radii, and the launcher uses an asymmetric `20px 68px 24px 56px` silhouette that tightens on mobile. Ordinary surfaces step through 14px source cards, 16px library cards, and 18px structural panels. Controls use 10–12px corners, the theme switch uses 14px, and true pills are reserved for compact statuses or the evidence spine. Borders remain 1px and low contrast.

### Named Rules

**The Flow-and-Precision Rule.** Soft irregularity belongs to large flow fields; controls and evidence containers use exact, modest radii.

## Components

Components feel like precise research controls set against flowing asymmetric surfaces. Default states are quiet; hover, focus, active, review, and risk states become explicit without adding visual noise.

### Buttons

- **Shape:** Compact library buttons use a 16px default radius, while task-specific research actions tighten to 10–12px. The primary launcher action is 48px tall with 16px horizontal padding.
- **Primary:** Mineral teal background with primary-foreground text and a weight near 680; no resting shadow.
- **Hover / Focus:** Hover darkens through `brightness(0.94)`; active presses by 1px. Keyboard focus uses a 3px mineral teal outline or ring with visible offset.
- **Outline / Ghost / Destructive:** Outline controls use cool canvas or paper with a 1px mineral rule and fog hover. Ghost controls add tone only on hover. Destructive actions use a safety-red tint and matching focus treatment rather than a solid warning block by default.

### Chips

- **Style:** Compact source and review labels use slide or paper fills, short horizontal padding, small type, and pill or small control radii.
- **State:** Selected or checked chips pair a teal fill or tint with explicit text. Needs-review states pair safety red with a written label; state never depends on color alone.

### Cards / Containers

- **Corner Style:** Source cards use 14px corners, library cards 16px, and major frames 18px.
- **Background:** Paper carries primary content; canvas, slide, and fog alpha layers distinguish nested evidence without creating a grid of floating cards.
- **Shadow Strategy:** Cards stay flat; only focal or overlapping frames use the ambient shadow vocabulary.
- **Border:** A 1px low-contrast graphite or mineral rule is preferred for data-bearing containers.
- **Internal Padding:** Compact cards use 12–16px; focal panels use 20–32px responsive padding.

### Inputs / Fields

- **Style:** Library fields are 32px high with a 16px radius; the primary workspace fields are 48px high with a 12px radius, 14px horizontal padding, a cool-canvas fill, and a 1px input border.
- **Focus:** Border shifts to mineral teal with a 3px translucent teal halo.
- **Error / Disabled:** Invalid fields use safety-red border and ring treatments. Disabled fields retain their structure, reduce opacity, and remove pointer interaction.

### Navigation

The utility header is a single line with the wordmark left, restrained 14px links centered, a workspace readout near the right edge, and a 44px theme switch at the far right. Header links reveal a 1px teal underline on hover. The workspace rail uses 42px items with 11px corners; hover adds mineral fog, and the active view uses a teal tint plus teal text. Below 900px, the rail becomes a sticky horizontal scroller.

### Evidence Ribbon

Four thin source streams converge into a single teal spine before the extraction workspace. The source lines reveal from left to right over 760ms with 90ms stagger; the spine follows over 900ms after a 380ms delay, using the same `cubic-bezier(0.16, 1, 0.3, 1)` easing. Reduced-motion mode resolves the streams immediately with no transform.

### Theme Toggle

The theme toggle is a 44px square with a 14px radius, paper fill, 1px rule, and sun/moon icon transition. Hover introduces a fog fill and teal-tinted border; active scales to 0.97. The control remains keyboard accessible and persists the selected theme.

### Named Rules

**The Inspectable State Rule.** Every active, reviewed, risky, or selected state must pair color with visible text, structure, or iconography.

## Do's and Don'ts

### Do:

- **Do** keep provenance visible before any synthesis surface.
- **Do** use mineral teal sparingly for action, focus, active state, and evidence flow.
- **Do** use 14–18px radii for data surfaces and 10–12px radii for precise controls.
- **Do** preserve semantic role and readable contrast across both light and dark themes.
- **Do** retain the 3px visible focus treatment and reduced-motion fallback.

### Don't:

- **Don't** turn the interface into an atmospheric or cinematic research dashboard.
- **Don't** arrange the workflow as a generic equal-weight card grid.
- **Don't** use safety red as a general accent or encode risk through color alone.
- **Don't** stack a border and a heavy shadow on every surface.
- **Don't** introduce serif display type or additional decorative font families.
