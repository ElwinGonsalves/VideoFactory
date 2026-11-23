---
name: Video Factory Studio
description: A local video lab where a stitched pipeline of engines comes alive on screen.
colors:
  lab-950: "#0a0f0c"
  lab-900: "#0f1612"
  lab-850: "#131c17"
  lab-800: "#18231c"
  lab-700: "#213027"
  lab-600: "#2d4034"
  lab-500: "#3e5647"
  lab-400: "#618471"
  bone: "#ecf2e8"
  moss: "#aebdaf"
  fog: "#8fa192"
  volt: "#8ef0a6"
  volt-deep: "#1f5a33"
  pumpkin: "#ffa64d"
  pumpkin-hi: "#ffbd78"
  pumpkin-ink: "#1c0f02"
  ghost: "#c2adff"
  ghost-deep: "#2c2447"
  blood: "#ff8b8b"
  blood-deep: "#3d1616"
  candle: "#ffd88a"
  candle-deep: "#3a2d0f"
typography:
  display:
    fontFamily: "Big Shoulders, Arial Narrow, sans-serif"
    fontWeight: 700
    lineHeight: 1
  body:
    fontFamily: "Work Sans, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Work Sans, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
rounded:
  sm: "6px"
  md: "10px"
  lg: "16px"
components:
  button-primary:
    backgroundColor: "{colors.pumpkin}"
    textColor: "{colors.pumpkin-ink}"
    rounded: "{rounded.md}"
    height: "40px"
    padding: "0 16px"
  button-primary-hover:
    backgroundColor: "{colors.pumpkin-hi}"
  button-secondary:
    backgroundColor: "{colors.lab-800}"
    textColor: "{colors.bone}"
    rounded: "{rounded.md}"
    height: "40px"
  input:
    backgroundColor: "{colors.lab-950}"
    textColor: "{colors.bone}"
    rounded: "{rounded.md}"
    height: "40px"
  panel:
    backgroundColor: "{colors.lab-900}"
    rounded: "{rounded.lg}"
  specimen-tag:
    backgroundColor: "{colors.lab-800}"
    textColor: "{colors.moss}"
    typography: "{typography.mono}"
    rounded: "{rounded.sm}"
    height: "24px"
---

# Design System: Video Factory Studio

Source of truth: `frontend/src/index.css` (`@theme`) and `frontend/src/components/ui.tsx`. This file describes them; it never overrides them.

## Overview

**Creative North Star: "Film lab after midnight"**

The studio is a stitched creature you can watch come alive. Each long job is a row of organs (the engines: script model, TTS, FFmpeg, Remotion, QA) joined by seams, and a seam carries current only while its organ works. The rest of the interface stays quiet so that current is the thing you notice.

The register is playful Halloween (owner choice), carried by copy ("Scripts on the slab", "The lab is quiet") and by a few world devices, never by costume: no cobwebs, no dripping fonts, no faked textures. Surfaces are dark green-black lab glass. The single loud color is the pumpkin primary action.

**Key Characteristics:**
- Green-black ground, never neutral grey or blue-black.
- One pumpkin primary action per view; everything else is secondary or ghost.
- Status color is semantic and fixed: volt = live/healthy/done, ghost violet = scheduled, candle = needs attention, blood = failure.
- Stitch seams (dashed vector lines) are the signature; they animate only while work runs.
- Real artifacts over illustrations: style cards are real Remotion frames, the Library preview is the real MP4 inside a phone bezel.

## Colors

A dark, slightly green lab palette with four signal colors that each mean exactly one thing.

### Primary
- **Pumpkin Lantern** (pumpkin): the primary action only (Write Script, Download MP4, Next). Text on it is Pumpkin Ink (9.67:1). Also the focus ring and the text caret.

### Secondary
- **Galvanic Volt** (volt): current. Live jobs, healthy engines, finished stepper nodes, QA pass. Volt Deep is its filled background.
- **Ghost Violet** (ghost): scheduled things and countdowns that are still on time.

### Tertiary
- **Candle** (candle): needs attention (late slot, unverified facts, held by the Safe-Publish Gate).
- **Blood** (blood): failure only. Never decoration.

### Neutral
- **Lab Glass** (lab-950 to lab-700): page ground, sidebar, panels, raised rows, in that order.
- **Lab Edge** (lab-400): every control border; at least 3:1 against every surface.
- **Bone** (bone): primary text. **Moss** (moss): secondary text. **Fog** (fog): hints and pending states.

### Named Rules
**The One Lantern Rule.** One pumpkin button per view. A second action is secondary or ghost.

**The Signal Means One Thing Rule.** Volt, violet, candle and blood are status, never decoration. If something is not live, scheduled, at risk or failed, it is neutral.

## Typography

**Display Font:** Big Shoulders Bold (with Arial Narrow)
**Body Font:** Work Sans (with system-ui)
**Label/Mono Font:** JetBrains Mono

**Character:** A condensed poster face for titles and the status pill, against a plain humanist sans for everything you read or type. Mono appears only where the content is machine text.

### Hierarchy
- **Display** (700, 1.875–2.25rem, line-height 1): page `h1` in the header, the onboarding title, drawer title and drawer section headings.
- **Title** (Work Sans 700, 1.125rem): panel titles ("Stitch a new video").
- **Body** (400, 1rem / 0.9375rem in controls, 1.5): descriptions, field text. Panels cap prose around 65ch.
- **Label** (600, 0.875rem): field labels, buttons, nav items. Sentence case, no tracking.
- **Mono** (400, 0.75rem): logs, file names, specimen tags.

### Named Rules
**The No Kicker Rule.** No small uppercase tracked labels above headings. Section headings are real headings.

## Layout

- App shell: sidebar 240px, collapsible to a 64px rail (`vf-rail`). Under 768px it becomes a bottom nav (Create, Ideas, Library, Schedule, More) with the rest in a More sheet.
- Sticky 64px header holds the page `h1` and the Studio Status Pill. There is no bottom jobs bar; activity lives in the right drawer.
- Panels are CSS containers (`@container`), so inner grids respond to the panel width, not the viewport. Style Picker: 2 columns → 3 at `@lg` → 6 at `@5xl`.
- Spacing rhythm on a 4px base: 12–16px inside rows, 24px panel padding, 24–32px between panels.
- Verified clean at 375×812, 768×1024, 1280×800 and 1440×900 by `scripts/ui_audit.py`.

## Elevation & Depth

Depth is tonal first: each layer is one lab step lighter. Shadows are reserved for things that float or glow.

### Shadow Vocabulary
- **Lift** (`0 10px 30px -12px rgb(0 0 0 / .7), 0 2px 6px -2px rgb(0 0 0 / .5)`): drawers, modals, the More sheet, specimen tags over images.
- **Glow** (`0 0 0 1px rgb(142 240 166 / .35), 0 8px 28px -8px rgb(142 240 166 / .35)`): a live organ or healthy engine.
- **Lantern** (`0 6px 20px -8px rgb(255 166 77 / .6)`): under the pumpkin button only.

## Shapes

Softly rounded rectangles: 6px for chips and tags, 10px for controls and rows, 16px for panels and dialogs. Circles only for stepper nodes and status dots. Specimen tags are the one irregular shape: dashed border, mono text, tilted -2° when pinned to an image.

## Components

### Buttons
- **Shape:** 10px radius, 40px tall (44px on coarse pointers), 32px for the small size.
- **Primary:** pumpkin fill, pumpkin-ink text, lantern shadow; hover lightens to pumpkin-hi; press scales to 0.98.
- **Secondary:** lab-800 fill, lab-500 border that brightens to lab-400 on hover.
- **Ghost:** moss text, fills lab-800 on hover. **Danger:** blood text and border, blood-deep on hover.
- **Focus:** 2px pumpkin outline, 2px offset, on every interactive element.

### Specimen Tag
Dashed lab-400 border, lab-800 fill, 12px mono moss text, truncates. Labels a style or engine (Library meta row, Activity drawer, Style Picker thumbnails).

### Cards / Containers
Panels: lab-900, 1px lab-700 border, 16px radius, 24px padding, title plus one-line description. Rows inside panels: lab-850, 10px radius.

### Inputs / Fields
lab-950 fill, lab-400 border at 70%, 10px radius, 40px tall. Focus: pumpkin border plus a 2px pumpkin ring at 35%. Labels sit above, hints below in moss.

### Navigation
Sidebar items are 40px rows with an icon and a label; the active item gets a lab-800 fill and a lab-500 border. The rail shows icons with tooltips. The bottom nav colors the active item pumpkin.

### Stitch Stepper (signature)
Five organs (Script, Voice, Music+SFX, Render, QA) joined by seams. Done: volt ring on volt-deep with a check. Active: pumpkin ring with a volt glow, and the seam into it runs `.seam-live` (dashed, animated). Pending: lab-500 ring, fog label. Failed: blood. Engine names show under each label from 400px up. Under reduced motion the seam is static.

### Studio Status Pill and Activity Drawer
The pill (`● Ready · 3 Scheduled · Next upload in 45m`) is the only global status surface. It opens a right drawer with Now Generating (stepper, elapsed, Cancel, log), Up Next (Scheduled) (countdowns, Manage Schedule) and Recent Activity (Open in Library, Retry).

## Do's and Don'ts

### Do:
- **Do** use real rendered frames for any image of a style; regenerate them with `scripts/render_style_cards.py`.
- **Do** keep signal colors semantic (see The Signal Means One Thing Rule).
- **Do** animate only work that is really happening (the live seam, the running spinner), and stop it under `prefers-reduced-motion`.
- **Do** run `scripts/ui_audit.py` on port 8766 after any layout change.

### Don't:
- **Don't** add a second pumpkin button to a view.
- **Don't** fake materials (CSS bevels, grain, embossing, dripping or "spooky" display fonts).
- **Don't** use small uppercase eyebrow labels above headings.
- **Don't** bring back a persistent bottom jobs bar; job status belongs to the pill and the drawer.
