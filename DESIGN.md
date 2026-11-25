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

<!-- impeccable:design-map -->
Name: Video Factory Studio
Colors: primary: pumpkin #ffa64d; secondary: volt #8ef0a6; tertiary: candle #ffd88a; neutral: lab-950 #0a0f0c; primary: pumpkin-ink #1c0f02; secondary: ghost #c2adff; tertiary: blood #ff8b8b (+4 more in the sidecar)
Fonts: Big Shoulders (display); Work Sans (body, label); JetBrains Mono (mono)
Radius: sm 6px, md 10px, lg 16px
North Star: "Frankenstein's Studio"
Rules:
- The One Lantern Rule. One Jack-o'-Lantern button per view.
- The Signal Means One Thing Rule. Galvanic Current, Ectoplasm, Candlelight and Dracula's Kiss are status.
- The No Kicker Rule. No small uppercase tracked labels above headings.
- The Two Names Rule. A themed name never stands alone in navigation: the plain name ("Render", "Library") sits under it, and screen readers hear both.
- The Flat-At-Rest Rule. No cast shadow on cards or rows.
Elevation:
- Lift: 0 10px 30px -12px rgb(0 0 0 / .7), 0 2px 6px -2px rgb(0 0 0 / .5)
- Glow: 0 0 0 1px rgb(142 240 166 / .35), 0 8px 28px -8px rgb(142 240 166 / .35)
- Lantern: 0 6px 20px -8px rgb(255 166 77 / .6)
Don't:
- Don't add a second Jack-o'-Lantern button to a view.
- Don't put materials, textures or bevels on everyday controls (buttons, fields, cards, rows).
- Don't let an effect block, delay or cover a task, or play sound without a click.
- Don't use dripping or "spooky" display fonts; Big Shoulders carries the poster voice.
- Don't use small uppercase eyebrow labels above headings.
- Don't bring back a persistent bottom jobs bar; job status belongs to the pill and the drawer.
Do:
- Do use real rendered frames for any image of a style, and regenerate them with `scripts/render_style_cards.py`.
- Do keep signal colours semantic (The Signal Means One Thing Rule).
- Do keep theatrical effects to moments that matter: finishing setup, a render coming alive, switching rooms, opening a video, banishing ghosts.
- Do give every effect a reduced-motion path, and respect Apothecary > System > Haunted effects (`vf-calm`).
- Do keep real materials (wood grain, brass, velvet) inside those moments only.
- Do show the plain name under every themed room name (The Two Names Rule).
- (+1 more)
Map: frontend/src/index.css
Map: frontend/src/components/ui.tsx
Map: scripts/ui_audit.py
Map: scripts/nav_check.py
Map: scripts/render_style_cards.py
Full: .impeccable/design-full.md (read a section when you need its detail)
