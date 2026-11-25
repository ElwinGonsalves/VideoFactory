---
name: Video Factory Studio
description: Frankenstein's studio, a local video lab whose stitched engines come alive on screen.
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
  button-ghost:
    textColor: "{colors.moss}"
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
    padding: "24px"
  specimen-tag:
    backgroundColor: "{colors.lab-800}"
    textColor: "{colors.moss}"
    typography: "{typography.mono}"
    rounded: "{rounded.sm}"
    height: "24px"
  lever:
    backgroundColor: "{colors.lab-850}"
    textColor: "{colors.pumpkin}"
    rounded: "{rounded.md}"
    height: "56px"
  nav-item-active:
    backgroundColor: "{colors.lab-800}"
    textColor: "{colors.bone}"
    rounded: "{rounded.md}"
    height: "44px"
---

# Design System: Video Factory Studio

Source of truth: `frontend/src/index.css` (`@theme` tokens and the effect keyframes) and `frontend/src/components/ui.tsx` (primitives). This file describes them and never overrides them.

## Overview

**Creative North Star: "Frankenstein's Studio"**

The app is one creature stitched together from open-source engines, and every room of the studio is part of its laboratory. You write a script in the Laboratory, lay it on the Operating Table, and pull a lever to bring it to life. The finished creature rests in Dracula's Vault until the Witching Hour carries it out into the world. The pipeline is shown as organs on one body, joined by seams that carry current only while that organ works.

The register is playful Halloween, built from classic monster movies (Frankenstein, Dracula, The Wolf Man, Night of the Living Dead, Hocus Pocus). Everyday work stays calm and legible. Theatre is saved for the moments that earn it: finishing setup, a render coming alive, switching rooms, opening the vault, banishing ghosts. Each room has a themed name, and its plain name always sits underneath, so nobody hunts for "Library".

Surfaces are dark green-black Laboratory Glass. The loudest colour is the single Jack-o'-Lantern action per view, and the other signal colours each mean exactly one thing.

**Key Characteristics:**
- Green-black ground, never neutral grey or blue-black.
- One Jack-o'-Lantern primary action per view; the render lever is that action on the Operating Table.
- Status colour is semantic and fixed: Galvanic Current = live/healthy/done, Ectoplasm = scheduled (and ghosts), Candlelight = needs attention, Dracula's Kiss = failure.
- Stitch seams (dashed vector lines) are the signature, and they animate only while work runs.
- Theatrical effects are moments, not wallpaper. All of them are decorative (`aria-hidden`), stop under reduced motion, and switch off with Haunted effects.
- Real artifacts over illustration: style cards are real Remotion frames, and the Vault plays the real MP4 in a phone frame.

## Colors

A dark, slightly green lab palette with four signal colours, each with one meaning.

### Primary
- **Jack-o'-Lantern** (pumpkin): the one primary action per view (Write Script, Download MP4, the lever's label). Text on it is Pumpkin Ink. Also the focus ring, the text caret, and the "selected" border on style cards and shelf rows. Hover lightens to pumpkin-hi.

### Secondary
- **Galvanic Current** (volt): current through the creature. Live jobs, healthy organs, finished stepper nodes, QA pass, click sparks, the lightning core. Volt-deep is its filled background.
- **Ectoplasm** (ghost): scheduled things and on-time countdowns, plus everything spectral: the ghosts' glow, the wand button, the ghost-voice preview, the bats' rim light.

### Tertiary
- **Candlelight** (candle): needs attention (late slot, unverified facts, Safe-Publish hold, dormant organs, length warnings) and the warm light inside the opened coffin.
- **Dracula's Kiss** (blood): failure only (failed jobs, missing required organs, QA issues and the CURSED stamp). Never decoration.

### Neutral
- **Laboratory Glass** (lab-950 to lab-700): page ground, sidebar, panels and raised rows, in that order.
- **Lab Edge** (lab-400): every control border, at least 3:1 against every surface.
- **Bone** (bone): primary text and the ghosts' bodies. **Moss** (moss): secondary text. **Fog** (fog): hints, plain room names and pending states.

### Named Rules
**The One Lantern Rule.** One Jack-o'-Lantern button per view. A second action is secondary or ghost.

**The Signal Means One Thing Rule.** Galvanic Current, Ectoplasm, Candlelight and Dracula's Kiss are status. The single exception is the haunting itself: a ghost glows Ectoplasm and a spark glows Current because those colours are what they are made of.

## Typography

**Display Font:** Big Shoulders Bold (with Arial Narrow)
**Body Font:** Work Sans (with system-ui)
**Label/Mono Font:** JetBrains Mono

**Character:** A condensed monster-poster face for room names, panel moments and big numbers, against a plain humanist sans for everything you read or type. Mono appears only where the content is machine text.

### Hierarchy
- **Display** (700, 1.5rem on phones to 1.875rem, line-height 1): the room name in the header (the short name on phones), drawer and modal titles, "It's alive!", the length readout, and the lever label.
- **Title** (Work Sans 700, 1.125rem): panel titles ("Stitch a new video", "The slab").
- **Body** (400, 1rem, or 0.9375rem in controls, 1.5): descriptions and field text, kept to about 65ch.
- **Label** (600, 0.875rem): field labels, buttons, nav items. Sentence case with no tracking. The plain room name under each nav item is 0.6875rem Fog.
- **Mono** (400, 0.75rem): logs, file names, specimen tags, the R.I.P. plate.

Devanagari (Hindi) relies on the system fallback (Nirmala UI on Windows) in both the app and the rendered video.

### Named Rules
**The No Kicker Rule.** No small uppercase tracked labels above headings. Section headings are real headings.

**The Two Names Rule.** A themed name never stands alone in navigation: the plain name ("Render", "Library") sits under it, and screen readers hear both.

## Layout

- **App shell:** a 240px sidebar (each item shows the themed name over the plain name), collapsible to a 64px rail. Below 768px it becomes a bottom nav (Lab, Table, Vault, Séance, More), with the rest in a More sheet.
- **Header:** 64px and sticky, holding the room emblem, the room name, the wand button and the Studio Status Pill. The pill shows its long form only from 1280px.
- **The rooms, in pipeline order:**
  1. Laboratory (write)
  2. Operating Table (render)
  3. Dracula's Vault (library)
  4. Séance (ideas)
  5. Horde (batch)
  6. Witching Hour (schedule)
  7. Apothecary (settings)
- **The shelf:** "Your creatures" groups projects as On the slab (opens the Operating Table), Alive and Released (both open the Vault).
- **Responsive panels:** panels are CSS containers, so inner grids respond to the panel's width. The Style Picker goes from 2 columns to 3 at `@lg` and 6 at `@5xl`.
- **Spacing:** a 4px base, 12–16px inside rows, 24px panel padding, and 24–32px between panels.
- **Verification:** `scripts/ui_audit.py` checks 375×812, 768×1024, 1280×800 and 1440×900, and `scripts/nav_check.py` checks switching between every pair of rooms.

## Elevation & Depth

Flat by default, with depth from tonal layering: each layer is one Laboratory Glass step lighter. Shadows appear only for things that float (overlays, the More sheet, tags pinned over images) or glow because they are alive.

### Shadow Vocabulary
- **Lift** (`0 10px 30px -12px rgb(0 0 0 / .7), 0 2px 6px -2px rgb(0 0 0 / .5)`): drawers, modals, the More sheet, specimen tags over images.
- **Glow** (`0 0 0 1px rgb(142 240 166 / .35), 0 8px 28px -8px rgb(142 240 166 / .35)`): a live organ, a healthy engine, the lever while it renders, a valid drop target.
- **Lantern** (`0 6px 20px -8px rgb(255 166 77 / .6)`): under the Jack-o'-Lantern button only.

### Named Rules
**The Flat-At-Rest Rule.** No cast shadow on cards or rows. If something is not floating, alive or primary, its depth comes from its surface step.

## Shapes

Softly rounded rectangles: 6px for chips and tags, 10px for controls, rows and the lever, 16px for panels and dialogs. Circles are used only for stepper nodes, organs, status dots and the wand button. Specimen tags are the one irregular shape: a dashed border, mono text, tilted -2° when pinned to an image. Swappable organs have a dashed ring. The coffin lids are the one silhouette that is not a rectangle: tapered at the head and foot.

## Components

Character: lab instruments that spark when used. Plain and precise at rest, with a jolt of current on use.

### Buttons
- **Shape:** 10px radius, 40px tall (44px on touch screens), and 32px for the small size.
- **Primary:** Jack-o'-Lantern fill, Pumpkin Ink text and the Lantern shadow. Hover lightens it to pumpkin-hi; pressing scales it to 0.98. A click throws forked Galvanic sparks.
- **Secondary:** lab-800 fill and a lab-500 border that brightens to lab-400 on hover. A click draws a quick Current ring. **Ghost:** Moss text that fills with lab-800 on hover. **Danger:** Dracula's Kiss text and border, with blood-deep on hover.
- **Focus:** a 2px Jack-o'-Lantern outline at 2px offset on every interactive element.

### The Lever (signature)
The render control on the Operating Table, a real `<button>` that a click, Enter or Space all pull. On a pointer you can also drag the handle down. At rest it has a Jack-o'-Lantern border, a recessed slot and a brass handle. When pulled, the handle drops on a spring, an arc flickers between the two contacts, and the frame turns Galvanic with the Glow shadow while the render runs ("Alive and rendering…").

### Stitch Stepper (signature)
Five organs (Script, Voice, Music+SFX, Render, QA) joined by seams:
- **Done:** a Current ring on volt-deep with a check.
- **Active:** a Jack-o'-Lantern ring with a Current glow. The seam into it runs `.seam-live`, and a spark travels along it.
- **Finishing:** a node flashes once when its step completes.
- **Pending:** a lab-500 ring with a Fog label. **Failed:** Dracula's Kiss.

### The Creature (signature)
In the Stitched Engines modal: a stitched body with nine organ buttons placed on it (Brain, Eyes, Ears, Voice box, Heart, Skeleton, the two Hands, Legs). Each organ is coloured by health (Current alive, Candlelight dormant, Dracula's Kiss missing), and the heart beats while FFmpeg is alive. Clicking an organ opens its card. The brain and the voice box take transplants: drag a donor onto the organ, or click it. A transplant writes the real setting, and the organ flashes Current.

### Cards / Containers
- **Panels:** lab-900, a 1px lab-700 border, 16px radius, 24px padding, and a title with a one-line description. Rows inside panels are lab-850 with a 10px radius.
- **The shelf:** a three-tab segmented control (name plus count) above rows. A selected row has a Jack-o'-Lantern border.

### Inputs / Fields
- **Fields:** lab-950 fill, a lab-400 border at 70%, 10px radius and 40px tall. Focus gives a Jack-o'-Lantern border with a 2px ring at 35%. Labels sit above and hints below, in Moss.
- **Length picker:** a fieldset with a large Display readout, preset chips (a 44px target, each a value plus a hint) and a 44px-tall dial with a Jack-o'-Lantern fill and a Bone thumb. A Candlelight note appears when a Short runs past 60 seconds.
- **Narrator:** a language segmented control (English, Hinglish, हिन्दी), a voice select with optgroups, and the "Hear it" ghost-voice pill.

### Navigation
- **Sidebar:** items are 44px rows: icon, themed name, plain name. The active item gets a lab-800 fill, a lab-500 border and a Jack-o'-Lantern icon. The rail shows icons, with tooltips carrying both names.
- **Bottom nav:** short names, with the active item in Jack-o'-Lantern.
- **Emblem:** each room shows its emblem in a dashed circle beside the title.

### Studio Status Pill and Activity Drawer
The pill (`● Ready · 3 Scheduled · Next upload in 45m`) is the only global status surface; it opens the right-hand drawer with Now Generating, Up Next (Scheduled) and Recent Activity.

### The Haunting (moments)
- **Bat burst:** about 28 flapping bats and a rising moon when setup is finished. It plays once, about 3 seconds.
- **"It's alive!":** a Current lightning strike and a Display headline when a render finishes.
- **Page bolt:** a top-down lightning reveal into the page on every room switch, about 0.5 seconds.
- **Click sparks:** described under Buttons above.
- **Scroll ghosts:** a lead ghost drifts diagonally with scroll progress, two companions orbit, and all of them vanish 0.65 seconds after scrolling stops.
- **Exorcism:** the wand button in the header turns the cursor into a wand. Clicking a ghost bursts it into Ectoplasm with "Begone!", and the ghosts stay gone until they are summoned back.
- **Dracula's Vault:** each video you pick opens under a coffin. Tapered wood-grain lids with brass nails, a gold cross and an R.I.P. plate hold for a beat, creak open on their hinges over about 1.5 seconds, and reveal crimson velvet that fades. Videos that failed QA get a CURSED stamp.
- **Ghost voice:** a ghost rises with a waveform over the card while the narrator reads that style's line.
- **Atmosphere:** candlelight follows the pointer, and two fog layers drift along the floor.

## Do's and Don'ts

### Do:
- **Do** use real rendered frames for any image of a style, and regenerate them with `scripts/render_style_cards.py`.
- **Do** keep signal colours semantic (The Signal Means One Thing Rule).
- **Do** keep theatrical effects to moments that matter: finishing setup, a render coming alive, switching rooms, opening a video, banishing ghosts. Mark them `aria-hidden`, use `pointer-events: none` unless they are the interaction (the wand), and keep them under about 3 seconds.
- **Do** give every effect a reduced-motion path, and respect Apothecary > System > Haunted effects (`vf-calm`).
- **Do** keep real materials (wood grain, brass, velvet) inside those moments only.
- **Do** show the plain name under every themed room name (The Two Names Rule).
- **Do** run `scripts/ui_audit.py` and `scripts/nav_check.py` on port 8766 after any layout change.

### Don't:
- **Don't** add a second Jack-o'-Lantern button to a view.
- **Don't** put materials, textures or bevels on everyday controls (buttons, fields, cards, rows).
- **Don't** let an effect block, delay or cover a task, or play sound without a click.
- **Don't** use dripping or "spooky" display fonts; Big Shoulders carries the poster voice.
- **Don't** use small uppercase eyebrow labels above headings.
- **Don't** bring back a persistent bottom jobs bar; job status belongs to the pill and the drawer.
