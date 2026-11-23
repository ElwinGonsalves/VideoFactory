# UX and navigation audit (Phases 1-5)

Status: **Phases 1-5 done.** Sections 1-6 are the Phase 1 audit of the old UI (kept at `/classic`). Sections 7-9 record the rebuild, its verification and the judging self-evaluation.
Target: the v2 vanilla UI in `ui/static/` (`index.html`, `app.js`, `style.css`), served by `ui/server.py`.
Date: 2026-11-23.

## How this audit was made

| Skill (from `../.agents/skills/`) | What it contributed |
| --- | --- |
| `impeccable` `critique` | Two isolated assessments run as separate sub-agents. **Method: dual-agent** (A: design review against `critique-rubric.md`; B: `impeccable detect` CLI + URL scans). Neither saw the other's output before synthesis. |
| `impeccable` `shape` | Journey map, brief and open decisions below. Shape stops before code and asks for confirmation. |
| `ui-ux-audit` | `scripts/uicheck.py` measured the render at 375/768/1280/1440, plus a per-tab Playwright sweep (every tab, log panel open and closed). Severity scale and pre-flight checklist adopted for the rebuild. |
| `ui-ux-pro-max` | `--design-system` query, and `ux` domain searches for navigation, progress, drawer focus and drag-and-drop. |
| `web-design-guidelines` | Vercel rule list (`references/command.md`), adopted as the code-review checklist for Phase 3. |

Not available: `design-review` (not in `.agents/skills`). Its role is covered by `ui-ux-audit/scripts/uicheck.py` and the Playwright sweep. The Impeccable live overlay was not injected because no headed browser is available to a human in this session.

Raw evidence: `ui/logs/baseline/`, `ui/logs/critique_a/`, `ui/logs/critique_b/` (`checks.json`, `measure.json`, `detect_*.json`, 48 screenshots). These folders are gitignored.

## 1. User journeys today

Each journey lists the clicks a user makes now, where it breaks, and what the rebuild must change.

| # | Journey | Today | Breaks at | Rebuild must |
| --- | --- | --- | --- | --- |
| J1 | **First-time setup (target under 5 min)** | `python scripts\bootstrap.py` → `doctor.py` → `ui\server.py` → find Settings → paste Gemini key → Save → Test connection. | Nothing says a key is needed. Create fails with "see log". No first-run guide. Masked placeholder `••••tmtg` looks like a value. | 3-step onboarding modal (Engines check → Gemini key or Demo Mode → first video), one-command `start.ps1` / `start.sh`. |
| J2 | **Create from Idea / Script** | Create → mode toggle → prompt or script → title, length, style, aspect, mood, platforms, two checkboxes → Write script → watch the log → Open → edit scenes → Render → wait ~3 min → Library. | About 10 controls before the primary button. Style options are raw ids (`concept_explainer`). Progress is raw log text. The editor is hidden until Open. Unsaved edits are lost on tab switch. | Visual Style Picker cards. Advanced options collapsed. Live 5-stage stepper in the Studio pill and drawer. Editor opens automatically after writing. Unsaved-changes guard. |
| J3 | **Reference DNA and approve ideas** | Ideas → mode → links/topic → Analyze → wait → pitch cards (6 fields, 4 buttons each) → Approve. | "No idea runs yet" is a dead end. "Add to Schedule" runs the full approve job first, so the label misleads. Sync Analytics lives here but its inputs live in Settings. | Blueprint ("Style DNA") cards with visible measured fields. Lighter cards with edit-in-place. Every empty state has one primary action. Analytics moves to Library and Settings. |
| J4 | **Batch from Excel / Sheets** | Batch → file or link → preview table → interval → Start. | The table cuts at 60 chars with `nowrap` and scrolls sideways. Start is disabled with no reason given. "Relative upload interval" is jargon. | Drag-and-drop zone with a keyboard and click fallback. Row cards on mobile, table on desktop. Inline row errors. The disabled reason is shown next to the button. |
| J5 | **Inspect and download in Library** | Library → list → inspector (video, QA strip, warnings, 4 fields, ~10 actions). | "5 to verify" overlaps "QA issues". The style filter has no label and renders blank. `<a><button>` nesting is invalid. Two ambiguous hashtag fields. About 10 equal-weight actions. | Phone-bezel 9:16 player, one primary action (Download), Publish and Re-render in a secondary menu, labelled filters, stacked status badges. |
| J6 | **Staggered overnight schedule** | Schedule → Pre-Flight switches → Builder (videos, first time, spacing, mode) → Preview → Add → Queue. | "Add to schedule" stays enabled while the daemon is OFF and logins are "?". "Tonight 11:00 PM" is a fixed label. Past-due jobs ("Yesterday 11:54 PM") show no late state. A paused card looks queued. Caps are edited in a different place from where they are read. | Readiness checklist gating Add (daemon, awake, logins, caps). Relative label computed from the clock. Overdue and paused states. Countdown in the Studio pill. |
| J7 | **Configure Settings** | One long two-column page: LLM (Gemini, Ollama, OpenAI all visible), defaults, 3 platform cards, alerts, spend, analytics, system. | Wall of about 25 fields. Ollama/OpenAI fields shown while Gemini is selected. "System health" is the most prominent button. | Sectioned settings with in-page nav. Provider fields shown only for the selected provider. Status summary at the top (key set, spend this month, logins). |
| J8 | **Watch a long job (all journeys)** | Bottom Jobs bar: unlabeled select, Cancel always enabled, ▲ glyph, plus a "0 running" header pill. | 48 px permanently taken (324 px when open, 40% of a phone). Two controls open the same panel. No stage or percent. Toasts are not announced. | **Delete the bar.** Studio Status Pill in the header + right-hand Studio Activity Drawer (Now Generating, Up Next, Recent). |

## 2. Critique synthesis

**Method: dual-agent** (A: design review sub-agent · B: detector sub-agent). Snapshot written with `impeccable critique-storage`.

### Design health score

| # | Heuristic | Score | Key issue |
| --- | --- | --- | --- |
| 1 | Visibility of system status | 2 | Jobs bar collapsed on load with "0 running" / "no jobs yet". A 3 min render shows only a log tail. Auth badges read "?" until clicked. |
| 2 | Match system / real world | 3 | Mostly plain creator language. Leaks: "Pre-Flight", "cookie login", "grounding", `needs_review`, `script.json`, `doctor.py`. |
| 3 | User control and freedom | 2 | Cancel and confirms exist. No undo for Dismiss or Overwrite. Re-render replaces the file. Scene edits lost on tab switch. |
| 4 | Consistency and standards | 2 | Two "Save defaults" in different tabs. Segmented controls double as tabs. Two near-identical hashtag fields. |
| 5 | Error prevention | 3 | Good: publish confirm, fact double-confirm, empty-scene check, Safe-Publish Gate. Weak: Publish Now never restates platform, account and visibility. |
| 6 | Recognition rather than recall | 2 | Hidden defaults (daemon OFF), unlabeled selects, slugs shown instead of titles. |
| 7 | Flexibility and efficiency | 2 | Batch and multi-select scheduling are good. No shortcuts, no bulk actions, no "reuse last settings". |
| 8 | Aesthetic and minimalist design | 2 | Clean but flat: every card has the same weight. Settings is a wall. |
| 9 | Error recovery | 3 | `explainFetchError` gives a next step. Toasts vanish in 4.5 to 9 s and are not announced. |
| 10 | Help and documentation | 2 | Good inline explainers. No first-run guide, no empty-state next steps, QA "issues" never says what to do. |
| | **Total** | **23/40** | **Fair**: functional and careful, visually generic. |

### Design specificity verdict

**Category-interchangeable.** A dark admin panel (slate cards, one orange accent, system-ui, pill tabs). Without the wordmark it could be a router console. The product's own character (frames, scenes, beats grammar, fact-check pipeline, hand-drawn styles, stitched engines) appears only in content, never in the chrome.

For the Frankenstein category the UI hides the idea: the engines appear only as raw strings in Settings (`edge-tts`, `kokoro`, `doctor.py`). There is no pipeline view and no "which organ is working now".

**Deterministic scan (Assessment B), agrees with A:**

- `impeccable detect` on `ui/static/index.html`: 3 low-contrast warnings.
  - White on `#ea580c` is 3.6:1, and `#fbdece` on `#ea580c` is 2.8:1.
  - Hover white on `#fb923c` is 2.3:1.
- URL scan at 1280×800 and 390×844: 6 findings, the same at both widths.
  - The same contrast warnings, plus 2 advisory placeholder warnings at 4.2:1.
  - `undersized-ui-text`: 10 px "(becomes the folder name)".
  - `nested-cards`: ×4.
- `uicheck.py`, Create tab at 4 widths:
  - Overflow is 0, focus visibility passed, and alignment, radius and ratio checks are clean.
  - The 3 contrast failures from the scan are confirmed.
  - 7 unnamed controls.
  - 13×13 checkboxes.
  - 11 px badges.
  - Both mode buttons wrap at 375.
- Per-tab sweep:
  - Schedule overflows by **6 px at 375** (`.grid2 > .card`).
  - 62 controls lack a programmatic label across tabs (27 in Settings).
  - There is no `h1` on any tab, and Ideas starts at `h3`.
  - Primary orange buttons sit at 3.56:1 everywhere.
  - Console showed 0 errors.
- False positives the detector or sweep raised:
  - The 1.88:1 Start/Add buttons are disabled controls, which WCAG exempts.
  - The `/stream` `ERR_ABORTED` is the video request aborted when the page closed.
  - Inline links under 24 px are exempt.
  - The `gemini-4-hydrogen` "placeholder" that A flagged is the real configured model (see `docs/UPGRADE_PLAN.md`), not a defect.

### What's working

1. **QA frame strip and fact-check badges.** These are product-specific trust features. The rebuild keeps and enlarges them.
2. **Queue step bar** (Queued → Rendering → Uploading → Published) plus a plain-language Safe-Publish hold message. It becomes the pattern for the 5-node stitch stepper.
3. **Error copy.** Specific next steps (`explainFetchError`, inline explainers like "keep my exact words").

### Priority issues

| ID | Severity | What | Fix | Command |
| --- | --- | --- | --- | --- |
| PI-1 | **P1** | Mobile header is **259 px** (nav stacks into 6 rows) and the Jobs bar adds 48 px, so a third of an 812 px phone is chrome. | Bottom nav on mobile, 64 px rail at tablet, 240 px sidebar on desktop. Delete the Jobs bar. | `adapt` |
| PI-2 | **P1** | No pipeline identity. Long jobs show raw logs. The Frankenstein idea is invisible. | Studio Status Pill + Activity Drawer with the 5-node stitch stepper (Script → Voice → Music+SFX → Render → QA), engine named per node. Stitched Engines health modal. | `onboard` |
| PI-3 | **P1** | Schedule and publish have no readiness gate. Add is enabled while the daemon is OFF. Publish uses two native `confirm()` dialogs that never restate platform, visibility or account. | Readiness checklist beside Add. Summary modal for publish with platform, account, visibility, unverified facts. Success state with the post link. | `harden` |
| PI-4 | **P1** | Primary buttons fail contrast (white on `#ea580c` = 3.56:1) across every tab. | New token pair at or above 4.5:1 (dark text on a lighter accent, or a deeper accent). | `colorize` |
| PI-5 | **P2** | Library list badges overlap, the style filter is blank and unlabeled, and empty states are dead ends. | Stacked badges, labelled filters ("All styles"), one primary action per empty state. | `clarify` |
| PI-6 | **P2** | Settings is a 25-field wall that shows every provider at once. A judge without a key gets stuck. | Sectioned settings. Provider-conditional fields. First-run Demo Mode that needs no key. | `distill` |

### Persona red flags

- **First-timer (Jordan):**
  - Create looks ready but fails without a key.
  - "Pre-Flight", "Safe-Publish Gate" and "Scheduler Daemon" are unexplained.
  - "QA issues" never says what to do.
- **Accessibility-dependent (Sam):**
  - Nav buttons lack `role=tablist` / `aria-current`.
  - Toasts and job status are not `aria-live`.
  - "?" / "✓" / "✗" badges and QA borders carry state by color alone.
  - 13 px checkboxes; 62 inputs without labels.
- **Power user (Alex):**
  - About 6 clicks and 2 confirms per video.
  - No shortcuts, no bulk select in Library or Queue, no reuse of last settings.
- **Solo creator queuing a week at 11 PM:**
  - The daemon is OFF by default next to an enabled "Add to schedule".
  - "Tonight 11:00 PM" is wrong after 11 PM.
  - Overdue jobs look normal.
  - No end-of-night summary in the UI.
- **Hackathon judge, 2 minutes, no API key:**
  - The default screen is an empty prompt that cannot run.
  - About 90 seconds go before anything is visible.
  - The best view (rendered video plus QA frames) is buried in Library.

## 3. Defect register (every item gets fixed or replaced in Phase 3)

| ID | Tab / viewport | Element | Defect | Kind |
| --- | --- | --- | --- | --- |
| D1 | All / 375 | `header`, `nav#tabs` | Header is 259 px; nav stacks vertically. | Layout |
| D2 | All | `#log-panel` | Permanent 48 px bar, 324 px open; unlabeled `#log-job`; Cancel enabled with no job; ▲ has no accessible name; pill and ▲ duplicate one action. | Redundant / a11y |
| D3 | All | primary buttons, active segments | White on `#ea580c` = 3.56:1; hover 2.3:1; `#fbdece` sublabel 2.78:1. | Contrast |
| D4 | All | 62 inputs/selects | No programmatic label (placeholders only, or adjacent text not linked). | a11y |
| D5 | All | checkboxes/radios | 13×13 controls. | Touch |
| D6 | All | headings | No `h1`; Ideas starts at `h3`. | Structure |
| D7 | All | `#toast` | Not `aria-live`; disappears in 4.5 s. | a11y |
| D8 | Schedule / 375 | `.grid2 > .card` | 6 px horizontal overflow. | Overflow |
| D9 | Schedule / 375 | `#b-projects .badge` | "rendered" wraps to 2 lines and overflows the list. | Wrapping |
| D10 | Create, Ideas / 375 | mode segments | Two-line buttons with 11.67 px sub-labels. | Cramped wrapping |
| D11 | Create / 375 | `#c-title`, `#c-style` | Placeholder truncated; select clips "concept_explaine". | Truncation |
| D12 | Create | `#c-style` | Raw ids instead of names. | Label |
| D13 | Create | `#projects` rows | Slugs shown beside titles; meta line breaks mid-phrase ("7 / scenes"). | Wrapping / noise |
| D14 | Create | `#c-overwrite` | Destructive option next to the primary button. | Error prevention |
| D15 | Create | editor | Hidden until Open; edits lost on tab switch. | Dead end / data loss |
| D16 | Ideas | `#runs` empty, blueprints "none yet" | No action. | Dead end |
| D17 | Ideas | pitch card | "Add to Schedule" approves first; 6 fields and 4 buttons per card. | Misleading label |
| D18 | Ideas | `#i-sync` | Sync Analytics here, its inputs in Settings. | IA |
| D19 | Batch | `#b-table` | 60-char cut + `nowrap` forces sideways scroll. | Truncation |
| D20 | Batch | `#b-run` | Disabled with no visible reason. | Dead end |
| D21 | Library / 1280 | `.lib-item` badges | "5 to verify" overlaps "QA issues". | Overlap |
| D22 | Library | `#l-style` | Blank, unlabeled select. | Label |
| D23 | Library | Download | `<a><button>` nesting. | Invalid HTML |
| D24 | Library | metadata | "Hashtags" vs "Hashtags / tags (comma)". | Confusing label |
| D25 | Library | actions | About 10 equal-weight actions; Publish Now beside Add to Schedule. | Hierarchy |
| D26 | Library | publish | Two native `confirm()` dialogs with no summary. | High-stakes UX |
| D27 | Schedule | Pre-Flight | 9 controls in one wrapping row; "?" badges by color. | Grouping / a11y |
| D28 | Schedule | Rendering radios | Label wraps over 5 lines, radio far from text. | Cramped wrapping |
| D29 | Schedule | `#sb-create` | Enabled while the daemon is OFF / logins unknown. | Error prevention |
| D30 | Schedule | `sb-first` | "Tonight 11:00 PM" fixed label. | Copy / logic |
| D31 | Schedule | queue | Past-due jobs show no late state; paused looks queued; Retry/Run Now on every card. | State |
| D32 | Schedule | defaults | Caps read in Pre-Flight, edited in Defaults. | IA |
| D33 | Settings | LLM | All providers' fields visible at once. | Progressive disclosure |
| D34 | Settings | secrets | Masked placeholder looks like a value. | Recognition |
| D35 | Settings | accounts | Per-card Save plus a separate "Save login methods". | Redundant |
| D36 | Settings | System | Diagnostics button styled primary. | Hierarchy |
| D37 | CSS | `style.css` | Minified patches appended; one type size family; `transition` not scoped. | System |

## 4. Navigation plan

Six destinations, unchanged in purpose, in task order:

| Slot | Destination | Icon (lucide) | Holds |
| --- | --- | --- | --- |
| 1 | Create | `Sparkles` | Idea / Script modes, Style Picker cards, scene editor |
| 2 | Ideas | `FlaskConical` | Brainstorm, Reference DNA (blueprints), pitch cards |
| 3 | Batch | `Sheet` | Drop zone, Sheets link, validated preview, spacing |
| 4 | Library | `Film` | List + phone-bezel inspector, QA strip, fact check, actions |
| 5 | Schedule | `CalendarClock` | Readiness checklist, Builder, queue |
| 6 | Settings | `SlidersHorizontal` | Sectioned: Model and spend, Defaults, Accounts, Alerts, System |

- **Desktop (1024 px and up):** 240 px left sidebar with labels, the Stitched Engines badge at its foot, and a collapse control. Header: page title (`h1`) left, **Studio Status Pill** right.
- **Minimized and tablet (768 to 1023 px, or user-collapsed):** 64 px icon rail. Each icon has a tooltip and an `aria-label`.
- **Mobile (under 768 px):** bottom nav with 5 slots (Create, Ideas, Library, Schedule, More). "More" opens a sheet holding Batch and Settings, keeping the bottom bar at the ui-ux-pro-max limit of 5. The header keeps the pill, compact.
- **URL reflects state** (`web-design-guidelines`): `#/create`, `#/library?item=<id>`, `#/settings/accounts`, so back, forward and deep links work.
- **Studio Activity Drawer:** a right-hand sheet, full width on mobile. It is a modal dialog: focus moves in, Tab is trapped, Escape closes it, and focus returns to the pill (ui-ux-pro-max *Modal Dialog Focus*). `overscroll-behavior: contain`.
  - **Now Generating:** title, style badge, 5-node stepper, elapsed time, Cancel, expandable log.
  - **Up Next:** slots with countdowns and platforms, plus a Manage Schedule link.
  - **Recent:** done and failed jobs, with Open in Library and Retry.

## 5. Design-system plan (for confirmation, not yet built)

`ui-ux-pro-max --design-system` returned "Soft UI Evolution" with indigo primary, green CTA and Fira Code/Sans. That is a generic SaaS default and conflicts with the brief, which pins a Halloween / Frankenstein Film Lab world. Per Impeccable ("the brief wins"), the pinned world is used and the search output contributes only its rules: status colors, contrast targets, 150 to 300 ms motion, and visible focus. The React stack search returned **no database match** after one retry, so stack guidance falls back to the `ui-ux-audit` pre-flight checklist and `web-design-guidelines`.

Proposed world, "Film Lab after midnight":

- **Surfaces:** near-black with a green cast (lab glass), not slate. 3 elevation steps, 2 shadow levels at most.
- **Signal colors:** one "galvanic" green for live/healthy (electricity through the stitches), one pumpkin-amber for primary actions (dark text on amber to pass 4.5:1), red for failure, cool violet for scheduled. Status is never shown by color alone: an icon and a word go with every color.
- **Signature element:** the **stitch line**. A dashed seam joins pipeline nodes and engine organs, and it carries current (an animated dash) only while a node is working. It is the Frankenstein idea made functional. It stays static under `prefers-reduced-motion`.
- **Type:** a condensed display face for page titles and the pill, and a readable sans for body (16 px base, 12 px floor). Tabular numbers for countdowns and percentages.
- **Shape:** radii in 3 steps (6/10/16) plus pills. Inner radius = outer minus inset.
- **Motion:** `framer-motion`, transform and opacity only, 150 to 300 ms, reduced-motion variants everywhere.
- **Restraint:** Halloween lives in icons, empty-state illustrations, the stepper and hover glows. Forms, tables and copy stay plain (Operate mode).

## 6. Rebuild guardrails (Phase 3 and 4)

- Every state per screen: loading, empty (with one action), error (with a next step), disabled (with a reason), long content.
- `min-w-0` on flex text children, `minmax(0, 1fr)` grid tracks, `overflow-wrap:anywhere` on user content, `text-wrap: balance` on headings.
- Labels on every control; `aria-live="polite"` for the pill, toasts and drawer status; 44 px targets on touch layouts, 24 px minimum anywhere; skip link; `color-scheme: dark`; explicit colors on native `<select>`.
- Phase 4 pass condition, measured with `uicheck.py` and a Playwright sweep at 375/768/1280/1440 on all 6 pages plus the Onboarding modal and Activity drawer:
  - zero horizontal overflow
  - zero clipped text
  - zero unnamed controls
  - zero contrast failures (enabled controls)
  - zero console errors
  - zero failed requests (excluding aborted media)
  - plus a visual check of every screenshot.

## 7. Owner decisions (resolved)

1. **1.c, playful.** Copy carries the Halloween register ("Scripts on the slab", "The lab is quiet"). Visuals stay disciplined: no costume ornament, no faked textures.
2. **2.b, keep the old UI.** `ui/static` is served at `/classic` and linked from Settings → System and the mobile More sheet.
3. **3, demo video submitted separately.** No rendered video is committed. Judge Demo Mode plays an MP4 already on the machine if one exists, otherwise it offers a no-key render of `projects/concept-001`. `.kiro/settings/mcp.json` stays gitignored (absolute path); `mcp.example.json` is committed.

## 8. Phase 4: verification

`scripts/ui_audit.py` (Playwright, served build on port 8766) visits every page plus onboarding steps 1-2, the Activity Drawer (idle and with a mocked mid-render job), the Stitched Engines modal and the mobile More sheet, at 375×812, 768×1024, 1280×800 and 1440×900. Each view is measured for horizontal overflow, clipped text, cramped wrapping, touch targets, unnamed controls, WCAG contrast, console errors and failed requests, then screenshotted and looked at.

| Round | Result | Main fixes |
| --- | --- | --- |
| First run | 2/41 clean | Overflow, contrast and labelling findings fixed page by page, including explicit colors on native `<select>` and replacing nested `<a><button>` with a `LinkButton` |
| Middle rounds | 41/41 by measurement | Style grid by container width, Library filters stacked, onboarding focus on the primary button |
| Visual pass | 41/41 | Schedule queue steps truncated on mobile ("Que…") → 2×2 grid under 448 px |
| Finish review | 45/45 | Drawer headings were eyebrow labels → display headings; raw style id in drawer → style name; Cancel icon read as a checkbox → stop icon; "Music+SFX" collided at 375 px → wraps; long-form card frame had overlapping text → re-rendered; tilted engine specimen tags on style cards |

Other checks: `impeccable detect` on `frontend/src` returned no findings; 111 pytest tests (14 new in `tests/test_studio_ui.py`); ruff clean; `tsc --noEmit` clean in `studio/` and `frontend/`; `doctor.py` all required checks pass; `smoke_test.py` renders a 5 s MP4 through the OneDrive-safe public mirror.

The Impeccable finish reviewer (fresh context) returned **fix**. Applied: the items above. Not applied, with reasons: the sidebar "ending at 900 px" is a full-page-capture artifact (the sidebar is `sticky h-dvh`); "late" pills already use the candle attention color, not the pumpkin action color; a decorative seam between the Create panels was declined to keep the seam meaning "current is flowing". Not re-scored by the reviewer after the fixes.

Known gap found along the way: in 16:9 `ConceptExplainer` diagrams with four items, the top node's label overlaps the scene heading. The style card avoids it; the composition itself is not fixed yet.

## 9. Phase 5: Kiroween judging self-evaluation

| Criterion | Evidence | Honest gaps |
| --- | --- | --- |
| **Design** | One coherent world (`DESIGN.md`): green-black lab glass, one pumpkin action per view, four signal colors with one meaning each, Big Shoulders / Work Sans / JetBrains Mono. The signature Stitch Stepper shows the pipeline as organs joined by seams that carry current only while working. Clean at 4 viewports; reduced motion respected. | The first viewport of Create is still mostly form; the creature reads strongest in the drawer and onboarding. Project thumbnails of hand-drawn styles are near-white squares. |
| **Potential impact** | A solo creator goes from a topic to a captioned, loudness-normalized Short with QA frames, then schedules a staggered overnight queue, all locally and free (Edge-TTS, Gemini free tier or Ollama). `start.ps1` sets up the minimum on first run. | Uploads depend on cookie logins or approved API apps; first setup still needs Python, Node and FFmpeg installed. |
| **Innovation** | Frankenstein architecture made visible: 8 independent engines (Remotion, FFmpeg, faster-whisper, Edge-TTS/Kokoro, Explainroo, Manim, WatchVideo, Playwright) stitched into one pipeline, with live health in the Stitched Engines modal and per-node progress parsed from real logs. Reference videos become a "Style DNA" blueprint that new ideas copy. | Progress percent is inferred from step markers and frame counters, not reported by each engine. |
| **Technological implementation** | FastAPI + token-guarded API; React 19 / Tailwind v4 with container queries; one `/api/studio` poll drives the pill and drawer; OneDrive reparse-point fix for Remotion bundling; Playwright audit script with a mocked live job; 111 tests. | No end-to-end browser test of a real render through the UI (the audit mocks the job). |
| **Presentation** | Judge Demo Mode (no key): sample Short, sample Blueprint, sample Batch preview, each labelled "Sample" and built from real files. README covers <5 min start, the architecture and how Kiro built it (spec, steering, hooks, MCP). | Demo video is submitted separately (owner decision 3). |