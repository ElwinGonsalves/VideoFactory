# Requirements: Studio UI v3 (Kiroween "Frankenstein" rebuild)

Source: the owner's 5-phase redesign brief, the Phase 1 audit (`docs/UX_AUDIT.md`), and owner answers 1.c (playful Halloween register), 2.b (keep the old UI at `/classic`), 3 (the demo video is submitted separately).

## R1 Studio status without a jobs bar
- **R1.1** The system SHALL NOT show a persistent bottom Jobs bar.
- **R1.2** The header SHALL show a Studio Status Pill on every page, e.g. `● Ready · 3 Scheduled · Next upload in 45m`.
- **R1.3** WHEN the user activates the pill, the system SHALL open a right Studio Activity Drawer.
- **R1.4** WHILE a job runs, the drawer's **Now Generating** section SHALL show the title, a style badge, an animated 5-node stepper `Script → Voice → Music+SFX → Render → QA`, elapsed time, Cancel (with confirmation) and expandable logs.
- **R1.5** The **Up Next (Scheduled)** section SHALL list upcoming render/upload slots with countdowns, platforms and a `Manage Schedule` link.
- **R1.6** The **Recent Activity** section SHALL offer `Open in Library` for finished renders and `Retry` for failed ones.

## R2 Navigation
- **R2.1** At ≥768px the system SHALL show a 240px sidebar that collapses to a 64px icon rail; the choice SHALL persist.
- **R2.2** Below 768px the system SHALL show a bottom nav (Create, Ideas, Library, Schedule, More), with the remaining destinations in a More sheet.

## R3 Journeys
- **R3.1** Create SHALL offer From Idea / From Script and a visual Style Picker whose cards show real rendered frames.
- **R3.2** Library SHALL preview 9:16 videos inside a phone bezel, with download, publish, schedule and QA frames.
- **R3.3** Batch SHALL accept drag-and-drop Excel/CSV and Google Sheets links, with a row preview before anything renders.
- **R3.4** Schedule SHALL offer a staggered Schedule Builder (first slot, spacing, render-just-before or render-all-now) with a live slot preview.
- **R3.5** Ideas SHALL support Brainstorm from Topic and Learn from References (Style DNA), with approve/dismiss on idea cards.

## R4 First run and judging
- **R4.1** WHEN no `vf-onboarded` flag exists, the system SHALL show a 3-step onboarding modal (welcome, brain/API key, first video).
- **R4.2** Onboarding SHALL offer a 1-click Judge Demo Mode that needs no API key and shows a sample Short, a sample Style Blueprint and a sample Batch preview, all labelled as samples and built from real files on disk.
- **R4.3** The sidebar SHALL show a **Stitched Engines** badge; activating it SHALL open a modal with live health for Remotion, FFmpeg, Whisper, Edge-TTS/Kokoro, Explainroo, Manim, WatchVideo and Playwright.
- **R4.4** `start.ps1` / `start.sh` SHALL take a fresh clone to a running studio, doing only the minimum setup on first run.

## R5 Quality
- **R5.1** Every page, the onboarding modal, the drawer (idle and mid-render), the engines modal and the More sheet SHALL have no horizontal scroll, clipped text, failing contrast, unnamed controls, console errors or failed requests at 375×812, 768×1024, 1280×800 and 1440×900 (`scripts/ui_audit.py`).
- **R5.2** All motion SHALL stop under `prefers-reduced-motion`.
- **R5.3** The old UI SHALL remain reachable at `/classic`.
