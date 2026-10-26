---
name: TrialLens
description: A minimal evidence registry for biomedical research.
colors:
  primary: "rgb(48 85 78)"
  primary-foreground: "#fff"
  background: "rgb(236 237 232)"
  foreground: "rgb(45 49 45)"
  card: "rgb(253 253 250)"
  secondary: "rgb(244 245 240)"
  accent: "rgb(229 237 231)"
  muted-foreground: "#62695f"
  destructive: "rgb(173 52 63)"
  border: "#dce0d7"
  input: "#858e80"
  dark-primary: "rgb(158 197 181)"
  dark-primary-foreground: "#162b24"
  dark-background: "rgb(19 24 21)"
  dark-foreground: "rgb(235 239 231)"
  dark-card: "rgb(28 35 30)"
  dark-secondary: "rgb(23 30 25)"
  dark-accent: "rgb(42 58 48)"
  dark-muted-foreground: "#b4bfb0"
  dark-destructive: "rgb(250 149 158)"
  dark-border: "#3d493f"
  dark-input: "#81937f"
typography:
  headline:
    fontFamily: 'var(--font-sans), ui-sans-serif, system-ui, sans-serif'
    fontSize: "25px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-0.03em"
  title:
    fontFamily: 'var(--font-sans), sans-serif'
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.025em"
  body:
    fontFamily: 'var(--font-sans), ui-sans-serif, system-ui, sans-serif'
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.85
  label:
    fontFamily: 'var(--font-sans), ui-sans-serif, system-ui, sans-serif'
    fontSize: "12px"
    fontWeight: 550
rounded:
  badge: "5px"
  filter: "999px"
  control: "10px"
  navigation: "12px"
  quiet: "8px"
  container: "16px"
  composer: "10px"
  shell: "22px"
  pill: "999px"
spacing:
  compact: "8px"
  control: "12px"
  content: "16px"
  composer: "18px"
  section: "24px"
  wide: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "42px"
  input-workspace:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
    minHeight: "42px"
    height: "auto"
  navigation-active:
    backgroundColor: "{colors.card}"
    textColor: "{colors.primary}"
    rounded: "{rounded.navigation}"
    padding: "10px 14px"
  answer-composer:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.composer}"
    padding: "18px"
---

# Design System: TrialLens

## Overview

**Creative North Star: "The Evidence Registry"**

TrialLens is a minimal, clean, intuitive research dashboard. The chosen visual direction combines quiet desktop panels, a warm cream canvas and ink, and rounded selection. A persistent research index, compact creation controls, soft paper panels, and readable source rows give evidence the largest share of the canvas. Registry remains the organizing structure.

The voice is sober and source-aware. Hierarchy comes from type, spacing, thin separators, and muted deep teal. Supporting details remain inspectable through disclosures rather than occupying equal visual weight with the current research task.

**Key Characteristics:**

- A persistent index anchors five research views.
- Soft paper panels and thin rules organize evidence within an inset desktop window.
- Geist carries headings, controls, and reading text.
- Muted deep teal identifies actions, citations, and focus; paper-white surfaces mark selection.
- Informative motion acknowledges new answers and changed inventory.

## Colors

Muted deep teal sits against a warm cream canvas, paper white, soft gray-green secondary surfaces, and dark ink. The dark theme preserves semantic roles with deep green-gray surfaces and pale sage teal. The frontmatter records the actual light and dark values from `apps/web/app/globals.css`, without a synthesized color ramp. Measured contrast ratios are 12.97:1 for light body text, 5.56:1 on paper and 5.17:1 on sidebar for secondary text, and 8.28:1 for the primary button. Dark theme ratios are 13.78:1 for body text, 8.42:1 for secondary text, and 7.9:1 for the primary button.

### Primary

- **Registry Teal** (`primary`): Primary actions, selected navigation, citations, and inventory feedback.
- **On Teal** (`primary-foreground`): Text and icons on the solid primary action.

### Neutral

- **Cool Canvas** (`background`): The working canvas.
- **Graphite Ink** (`foreground`): Primary text and iconography.
- **Paper** (`card`): Header, fields, tables, composer, and inspection surfaces.
- **Cool Gray** (`secondary`): Sidebar, table headings, and quiet explanatory blocks.
- **Teal Wash** (`accent`): Selected navigation and filters, plus citation hover.
- **Muted Ink** (`muted-foreground`): Supporting copy, metadata, and labels.
- **Separator** (`border`): Thin surface boundaries and row divisions.
- **Field Stroke** (`input`): Stronger input boundaries.
- **Review Red** (`destructive`): Error and review attention; pair with explicit text.

**The Semantic Theme Rule.** Use the CSS semantic variables in components so light and dark roles change together. The focus token `--ring` aliases `--primary` in both themes.

## Typography

Geist is loaded through `next/font/google` into `--font-sans`. Display and heading variables alias the same family; the implemented Registry has no separate display face. Use the frontmatter headline for the compact page introduction and title for view headings. At small widths the introduction becomes 23px and view headings 19px.

The main answer uses the body role, constrained to 74ch. Answer questions use 20px/1.5 at weight 600, becoming 18px on small screens. Table cells use 13px/1.55, explanatory copy commonly uses 13px/1.65–1.8, and secondary metadata uses 11–12px. Source counts use tabular numerals. Preserve this reading hierarchy when adding research content.

## Layout

The desktop shell sits within an 18px inset and is capped at 1560px. Its research window has a 22px radius and a soft secondary-surface frame. A sticky 72px header contains the compact creation form, wordmark and theme switch. A 224px persistent left index contains the five research views, stable workspace entries and medical-scope note. The quiet sidebar shares the warm secondary surface; the 12px rounded selection rests on paper white. Loaded workspaces begin with their topic and evidence; the introduction becomes screen-reader-only. On Evidence, source inventory sits in a 200px right column with an 18px gap. Other views keep inventory in the index. There is no marketing hero or duplicate header navigation. A ResizeObserver tracks the actual header height so sticky navigation follows enlarged text.

Below 1360px, Evidence inventory stacks below the table. At 1150px the index narrows to 200px and main horizontal padding becomes 24px. At 900px the header becomes 64px and creation moves into the main area; the shell becomes one column and the index becomes a sticky horizontal tab strip below the header. Recent workspaces move into the main creation area. After a workspace loads, mobile creation collapses into the New workspace disclosure, leaving the current research view prominent. At 600px, main padding becomes 20px 14px 32px; builder fields stack, actions and key touch targets reach 44px, and split brief/reliability content becomes one column. At 1500px main right padding becomes 32px.

The evidence table keeps a 58em minimum width, scaling with enlarged table text, inside its own horizontally scrollable container, with a mobile scroll hint. Long titles, questions, citations, and source metadata wrap. Keep min-width: 0 on grid content so text enlargement and narrow screens retain access to content.

## Elevation & Depth

The desktop research window has a gentle frame, while working surfaces use paper-white fills, 16px corners, and no shadows. Table rows and content sections use thin separators; quiet explanations use tonal fills. The selected view and recent workspace use a rounded paper-white shared-layout highlight; the workspace highlight has a faint inset 1px border. Selection moves between entries; reopening does not reorder them. The source inspection sheet is the elevated exception, with `-12px 0 44px rgb(0 20 26 / .12)` shadow and a `rgb(8 20 24 / .25)` overlay without blur.

**The Flat Workspace Rule.** Use open space, rules, and tonal grouping for normal research content; reserve floating depth for inspection overlays.

## Shapes

Soft, regular corners define the Registry. The research window uses 22px; paper panels and evidence inventory use 16px. Navigation and selection use 12px; ordinary controls, launcher fields, and the composer use 10px. Source filters and the primary build action are pill-shaped (999px). Quiet blocks use 8px and badges use 5px. Separators and tonal grouping keep rounded surfaces calm rather than card-heavy.

## Components

### Buttons

Creation uses a solid teal action, a compact label, and the primary button dimensions in frontmatter. Hover mixes 10% black into the primary color. Other shared variants include outline, secondary, ghost, destructive tint, and text link; choose the emphasis required by the action. Shared buttons transition background, text, and border color over 150ms. Disabled controls reduce opacity and prevent interaction. Shared button focus adds a 3px ring; the global keyboard outline is 2px with a 3px offset.

### Inputs / Fields

Workspace fields use paper fill, field stroke and written labels. The desktop header variant uses 13px text, a 34px minimum height, automatic height and 6px block padding; mobile uses stacked controls with a 44px minimum height and unitless line spacing. The frontmatter records the base field geometry. Shared field focus uses the primary border and translucent 3px ring. The answer composer is a paper container around a vertically resizable textarea, with a minimum 80px text area and 15px/1.65 type. Its focus outline is 1px with a 5px offset. Preserve written labels, invalid states, and disabled feedback.

### Navigation

The persistent index uses icons and 13px labels, a 44px minimum row, and a paper-white active state with stronger weight. Hover uses a faint ink fill. At 900px it becomes horizontally scrollable with 42px minimum rows. Each view has a matching hash used by selection and hydration: #workspace, #ask, #sources, #brief and #reliability. Workspace labels use unitless 1.5 line spacing. Existing workspace switches retain list order and desktop scroll position; an opening indicator marks the pending entry.

### Chips

Evidence filters pair visible pressed state with teal text, wash, and border. Additional review filters are behind a disclosure. Badges use 11px type, a 21px minimum height, and wrapping text; communicate review state in words as well as color.

### Cards / Containers

View panels are open sections. The evidence table uses paper, a thin border, the container radius, shaded column headings, and row separators. Source titles, citations, review labels and row actions use scalable line heights; action heights grow with text. Horizontal overflow stays inside the table container. The answer composer is the principal bounded input region. Source lists and saved answers use separated rows rather than a grid of floating cards.

### Answers and Brief

Ask presents one readable answer with inline citation links, source links, generation notes, and a visible boundary or caveat when provided. Supporting evidence, method, and retrieved passages use disclosures. Conversation history uses compact expandable turns. Brief foregrounds explicitly saved research answers, with export and remove actions; workspace context is disclosed separately. Do not turn these affordances into claims about answer quality.

Framer Motion shared-layout highlights use a spring with stiffness 440 and damping 38. Workspace hover moves 2px horizontally over 180ms. Incoming workspace/view content transitions opacity 0.94 to 1 and y 3 to 0 over 240ms; reduced motion removes travel. Workspace records, evidence and saved conversation commit together after loading. Framer Motion reveals a new answer from opacity 0.88 to 1 over 180ms with easeOut. Reduced motion removes the initial animation and sets duration to zero. GSAP acknowledges source inventory changes with y: 3 to 0, opacity 0.65 to 1, duration 220ms, 25ms stagger, and power2.out easing. Its scoped useGSAP context reverts on updates, matchMedia is reverted on cleanup, and transform/opacity are cleared after completion. The effect runs only for no-preference motion settings. Global reduced-motion CSS disables smooth scrolling and reduces animation/transition durations to 0.01ms.

### Theme Toggle and Inspection

The keyboard-accessible theme toggle is 36px square on desktop and 44px on small screens. It uses a quiet corner, paper fill, border, and sun/moon state. The chosen theme persists in localStorage and a one-year same-site cookie; the server reads the cookie for the initial root class. With no saved preference, the client uses the system preference. Source inspection uses the existing Base UI sheet with its focus and close behavior.

## Do's and Don'ts

### Do:

- **Do** keep the current research view dominant beneath compact creation controls.
- **Do** use Geist, thin separators, warm cream surfaces, ink, and quiet rounded panels.
- **Do** preserve inspectable citations, source limits, and written review states.
- **Do** use disclosures for supporting detail while keeping primary answers readable.
- **Do** retain semantic themes, keyboard focus, mobile access, and reduced motion.

### Don't:

- **Don't** reintroduce a marketing hero, evidence ribbon, or separate condensed display face.
- **Don't** fill the dashboard with equal-weight floating cards or decorative motion.
- **Don't** use color alone to communicate review, error, or selected state.
- **Don't** imply medical advice, validated answer quality, or completed deployment through visual copy.
