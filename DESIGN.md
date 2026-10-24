---
name: TrialLens
description: A minimal evidence registry for biomedical research.
colors:
  primary: "rgb(0 111 105)"
  primary-foreground: "#fff"
  background: "rgb(248 250 251)"
  foreground: "rgb(26 38 43)"
  card: "rgb(255 255 255)"
  secondary: "rgb(240 244 245)"
  accent: "rgb(229 242 239)"
  muted-foreground: "#52636b"
  destructive: "rgb(173 52 63)"
  border: "#dbe3e6"
  input: "#788e97"
  dark-primary: "rgb(86 207 193)"
  dark-primary-foreground: "#092b28"
  dark-background: "rgb(16 23 27)"
  dark-foreground: "rgb(234 241 244)"
  dark-card: "rgb(21 31 36)"
  dark-secondary: "rgb(27 39 45)"
  dark-accent: "rgb(28 58 57)"
  dark-muted-foreground: "#acbdc5"
  dark-destructive: "rgb(250 149 158)"
  dark-border: "#35464e"
  dark-input: "#768d98"
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
  filter: "6px"
  control: "7px"
  quiet: "8px"
  container: "9px"
  composer: "10px"
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
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "42px"
  input-workspace:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "42px"
  navigation-active:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.primary}"
    rounded: "{rounded.control}"
    padding: "9px 12px"
  answer-composer:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.composer}"
    padding: "18px"
---

# Design System: TrialLens

## Overview

**Creative North Star: "The Evidence Registry"**

TrialLens is a minimal, clean, intuitive research dashboard. A persistent research index, compact creation controls, flat working panels, and readable source rows give the evidence the largest share of the canvas. The user chose Registry, composition A, as the replacement visual world.

The voice is sober and source-aware. Hierarchy comes from type, spacing, thin separators, and a restrained teal signal. Supporting details remain inspectable through disclosures rather than occupying equal visual weight with the current research task.

**Key Characteristics:**

- A persistent index anchors five research views.
- Flat panels and thin rules organize evidence.
- Geist carries headings, controls, and reading text.
- Teal identifies actions, selection, citations, and focus.
- Informative motion acknowledges new answers and changed inventory.

## Colors

One restrained teal accent sits against cool near-white surfaces and graphite text; the dark theme preserves the same semantic roles. The frontmatter records the actual light and dark values from `apps/web/app/globals.css`, without a synthesized color ramp.

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

The desktop shell is capped at 1600px. A sticky 72px header contains the compact creation form, wordmark and theme switch. A 216px persistent left index contains the five research views, stable workspace entries and medical-scope note. Main padding is 28px 32px 48px. Loaded workspaces begin with their topic and evidence; the introduction becomes screen-reader-only. On Evidence, source inventory sits in a 180px right column with a 24px gap. Other views keep inventory in the index. There is no marketing hero or duplicate header navigation. A ResizeObserver tracks the actual header height so sticky navigation follows enlarged text.

Below 1250px, Evidence inventory stacks below the table. At 1150px the index narrows to 200px and main horizontal padding becomes 24px. At 900px the header becomes 64px and creation moves into the main area; the shell becomes one column and the index becomes a sticky horizontal tab strip below the header. Recent workspaces move into the main creation area. After a workspace loads, mobile creation collapses into the New workspace disclosure, leaving the current research view prominent. At 600px, main padding becomes 20px 16px 36px; builder fields stack, actions and key touch targets reach 44px, and split brief/reliability content becomes one column. At 1500px main horizontal padding becomes 40px.

The evidence table keeps a 58em minimum width, scaling with enlarged table text, inside its own horizontally scrollable container, with a mobile scroll hint. Long titles, questions, citations, and source metadata wrap. Keep min-width: 0 on grid content so text enlargement and narrow screens retain access to content.

## Elevation & Depth

Working panels are flat: the active view has transparent background, no border, no radius, and no shadow. Table rows and content sections use thin separators; quiet explanations use tonal fills. The selected recent workspace uses a teal-wash shared-layout highlight with a faint inset 1px border. Selection moves between entries; reopening does not reorder them. The source inspection sheet is the elevated exception, with `-12px 0 44px rgb(0 20 26 / .12)` shadow and a `rgb(8 20 24 / .25)` overlay without blur.

**The Flat Workspace Rule.** Use open space, rules, and tonal grouping for normal research content; reserve floating depth for inspection overlays.

## Shapes

Small, regular corners define the Registry. Filters use the filter radius, navigation and creation controls use the control radius, quiet blocks and the theme switch use the quiet radius, table/alert containers use the container radius, and the composer uses the composer radius. Badges are compact labels with the badge radius rather than oversized pills. Structural research panels remain square and open.

## Components

### Buttons

Creation uses a solid teal action, a compact label, and the primary button dimensions in frontmatter. Hover mixes 10% black into the primary color. Other shared variants include outline, secondary, ghost, destructive tint, and text link; choose the emphasis required by the action. Shared buttons transition background, text, and border color over 150ms. Disabled controls reduce opacity and prevent interaction. Shared button focus adds a 3px ring; the global keyboard outline is 2px with a 3px offset.

### Inputs / Fields

Workspace fields use paper fill, field stroke and written labels. The desktop header variant uses 13px text, a 34px minimum height, automatic height and 6px block padding; mobile uses stacked 44px controls. The frontmatter records the base field geometry. Shared field focus uses the primary border and translucent 3px ring. The answer composer is a paper container around a vertically resizable textarea, with a minimum 80px text area and 15px/1.65 type. Its focus outline is 1px with a 5px offset. Preserve written labels, invalid states, and disabled feedback.

### Navigation

The persistent index uses icons and 13px labels, a 40px minimum row, and a teal-wash active state with stronger weight. Hover uses a faint ink fill. At 900px it becomes horizontally scrollable with 42px minimum rows. Each view has a matching hash used by selection and hydration: #workspace, #ask, #sources, #brief and #reliability. Workspace labels use unitless 1.5 line spacing. Existing workspace switches retain list order and desktop scroll position; an opening indicator marks the pending entry.

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
- **Do** use Geist, thin separators, and regular compact corners.
- **Do** preserve inspectable citations, source limits, and written review states.
- **Do** use disclosures for supporting detail while keeping primary answers readable.
- **Do** retain semantic themes, keyboard focus, mobile access, and reduced motion.

### Don't:

- **Don't** reintroduce a marketing hero, evidence ribbon, or separate condensed display face.
- **Don't** fill the dashboard with equal-weight floating cards or decorative motion.
- **Don't** use color alone to communicate review, error, or selected state.
- **Don't** imply medical advice, validated answer quality, or completed deployment through visual copy.
