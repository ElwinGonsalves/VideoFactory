# Upgrade plan v2 (handoff for a fresh agent session)

Status: **implemented** (sections 1-9, one commit per section; see `git log`). Remaining notes are at the end of this file. The current code is on `main` at https://github.com/ElwinGonsalves/VideoFactory.
Read `docs/ARCHITECTURE.md` first, then this file. Work through the sections in order and commit
atomically per section (`feat(ui): ...`, `feat(batch): ...`, ...).

## Requested upgrade (from the owner, verbatim intent)

1. **Global UI/UX & errors**
   - Never show a generic "Failed to fetch". Add CORS (allow only `http://127.0.0.1:<port>` / `http://localhost:<port>`), request timeouts in the frontend (AbortController), and a global FastAPI exception handler that returns structured JSON `{detail, hint}`. Map network errors to an actionable message ("server not reachable; is `python ui/server.py` running?").
   - Slugs: clean 3-5 word kebab-case **from the video Title only** (never from prompt/script text); de-duplicate with `-2`, `-3`.
   - Nav: `Create | Ideas | Batch | Library | Schedule | Settings`.
2. **Create page**
   - Segmented toggle: *From Idea (AI writes script)* vs *From Script (keep exact text)*. Script mode keeps the user's words verbatim for TTS and only splits them into scenes (LLM may pick visuals, never rewrite narration).
   - `prompts/script_templates.py` → `ScriptTemplateRegistry` with native beats + visual fields per style:
     - `concept_explainer` / `case_study`: Hook → Mechanism → Case Study (data/timeline) → Takeaway Loop
     - `vox_documentary`: Cold Open → Archival/Map Context → Turning Point → Editorial Synthesis
     - `whiteboard` / `hand_drawn`: Problem Sketch → Step-by-Step Draw Cues (Rough.js/icons) → Recap
     - `stickman`: Character Setup → Escalation & Reaction Beats → Punchline (needs a new stick-figure renderer)
     - `long_form` (16:9): Hook → Intro → 3-5 Chapters → Summary & CTA
     - `reference_blueprint`: beats inherited from `analyzer/blueprints/<style>.json`
   - Gemini Google Search grounding for case studies / stats / history; store cited sources + verification flags in `script.json`.
   - Scene editor: auto-resizing textareas, scene-type dropdown, `+ Add Scene`, `Delete`, `Move Up/Down`.
3. **No text-only frames + micro-SFX**
   - Validator + every Remotion/whiteboard template: each scene renders a concrete visual filling the center 55% (animated SVG diagram/flow, bar/counter chart, Rough.js sketch/icon, Vox paper-cutout card, or Wikimedia/Archive image with Ken Burns). Never plain text on an empty gradient.
   - `audio_pipeline/sfx_library/manifest.json` mapping `whoosh`, `pop`, `paper_flip`, `chalk_draw`, `riser` to local CC0 clips.
   - SFX at -12 dB relative to the voice on scene cuts, stat pop-ins, Vox/whiteboard reveals.
4. **Ideas page**
   - Two modes: *Brainstorm from Topic/Niche* and *Learn from Reference Video(s)*. Plain labels (`Analysis depth: Fast / Detailed`), list saved Style Blueprints.
   - Pitch cards: editable Title, Opening Hook (spoken + visual), Core Concept & Case Study (2 lines), Style/Aspect/Duration/Mood badges, 1-line Why It Works; buttons `Approve & Generate`, `Edit Script`, `Add to Schedule`, `Dismiss`.
   - Query `data/projects.db` before generating so topics/case studies never repeat.
   - `Sync Analytics` (+ optional weekly task): `yt-dlp --dump-json` on published URLs → views/likes in SQLite → top 3 hooks/styles fed into future idea prompts.
5. **Batch page**: `.xlsx`/`.csv` upload + public Google Sheets URL (→ `/export?format=csv`). `Download Sample Excel` with columns `input_mode, title, content, style, aspect_ratio, music_mood, voice, auto_publish, platforms, schedule_at`. Validated preview table, Relative Upload Interval (`30m, 45m, 1h, 2h, 4h, Custom`), renders strictly 1 at a time (6 GB VRAM).
6. **Library**: files in `output/<project_id>/`, index in `data/projects.db`. `GET /api/projects/{id}/stream` with HTTP 206 Range. Encode `-c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart`. Master-detail: searchable/filterable paginated list (recent first) left; Inspector right with ONE `<video>` (no duplicate thumbnail), QA strip, fact-check banner, editable Title/Description/Hashtags, `Download MP4` (Content-Disposition: attachment), `Re-render 16:9 / 9:16`, `Add to Schedule`, `Publish Now`.
7. **Schedule**
   - Pre-Flight bar: Scheduler Daemon ON/OFF; Keep PC Awake (Windows `ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)` while jobs pending/running, release with `0x80000000`); Safe-Publish Gate (unverified facts → render but hold as `needs_review`); auth badges YouTube/Instagram/TikTok ✓/✗.
   - 5-10 min before an upload, check the cookie session / API token; if expired, pause that platform's queue (no retry storms).
   - Schedule Builder: pick projects by Title (multi-select), first upload time (`Now`, `Tonight 11:00 PM`, picker) + relative spacing (`30 min, 45 min, 1 hr, 2 hr, 4 hr, custom`), live preview of times, and "auto-generate X min before upload" vs "generate all now, upload staggered".
   - Queue cards: human times ("Today 11:45 PM"), steps Queued → Rendering → Uploading → Published (+ link), Pause/Resume, Run Now, Retry, Remove.
8. **Settings**
   - Remove the `Clipper speaker tracking` checkbox from Settings.
   - Per-platform cards: Account label, Cookie Login / Official API toggle, `Connect / Refresh Login`, `Check Session`; when API: masked Client ID, Client Secret, `client_secret.json` upload, Access Token, Save, Test Connection. Secrets only in gitignored `.env` / `config/secrets.json`.
   - Optional Telegram bot + Discord webhook (in `.env`) → message when an overnight batch finishes or a job fails (with links).
   - Log Gemini input/output tokens per call in `data/projects.db`, show estimated ₹ spend, enforce an editable stop-limit (default ₹100) that pauses batches cleanly.
9. **Docs + verification**: update `FIRST_VIDEO_GUIDE.md`, `ARCHITECTURE.md`, `SCHEDULER.md`, new `BATCH_SHEETS.md`, `DEBUGGING.md` (add: keep the project **outside OneDrive** for render/SQLite stability). Pass `scripts/doctor.py`, `scripts/smoke_test.py`, `ruff check --fix && ruff format`, `npx tsc --noEmit` (in `studio/`). Push to `origin main`.

## Facts the next session must know

**Constraints found in this session**
- **Gemini free tier has no Google Search grounding** (pricing page, Nov 2026: "Grounding with Google Search: Not available" on Free; paid: 5,000 free requests/month then $14/1,000). Implement grounding with a clean fallback: on a tier/permission error, generate ungrounded and mark every numeric claim `verified: false`. The Safe-Publish Gate then holds those videos.
- Gemini paid prices for `gemini-4-hydrogen`: $1.50 / 1M input, $7.50 / 1M output (thinking tokens count as output). Free tier costs ₹0; the spend guard needs per-model prices and an editable USD→INR rate.
- The Gemini adapter (`llm/providers.py`) reads text from whichever response field holds it, so usage metadata should be parsed defensively (`usageMetadata` for `generateContent`; field names on `interactions` are unverified).
- Probable cause of "Failed to fetch": the old Library tab mounts one `<video preload=metadata>` per item plus thumbnails, served without Range support. That exhausts the browser's ~6 connections per host and stalls or resets API calls. The master-detail Library with a single player and a 206 stream endpoint should fix it; verify after.
- The cookie uploader (social-auto-upload) does not return the published URL. For Sync Analytics, let the user paste URLs per project and/or set a channel URL (`https://www.youtube.com/@handle/shorts`, `yt-dlp --flat-playlist -J`) and match by title.
- `kaomei/stickman-video-director` has an empty default branch: build the stickman renderer in Remotion (SVG figure, poses, speech bubbles).
- Lucide icons are available for "icon" visuals: `lucide-react` (npm) or the 1,800 icons inside `engines/explainroo`.

**Environment (owner's laptop)**
- Windows, PowerShell 5.1. `Set-Content -Encoding utf8` writes a BOM that breaks `package.json`/JSON; use `[IO.File]::WriteAllText(path, text, (New-Object Text.UTF8Encoding $false))` or the file-write tool. Chained PowerShell commands sometimes swallow output; rerun separately.
- Project path is inside OneDrive: new files can be briefly locked (`common.safe_replace` retries renames).
- RTX 4050 6 GB (driver 580.97), CUDA via pip (`requirements-gpu.txt`, torch 2.15.0+cu132). ~16 GB RAM, often only 2-3 GB free: Remotion can time out starting Chrome (auto-retry with `--concurrency=2` exists), explainroo needs `--workers 2`.
- C: had ~3-7 GB free. The pip cache (1.7 GB) and npm cache (7.6 GB) can be purged if needed.
- The owner may have `ui/server.py` running on port 8765. Never kill it; test on another port (`--port 8766`) via the background-process tool.
- The owner's own data is **not committed**: `projects/how-would-the-world-be-if-a-person-never-lied/`, `projects/is-your-brain-lying-to-you-0-4-sec-hook-what-if-i-/`, and their edits to `scheduler/schedule.yaml`. Migrate them carefully when changing the output layout (existing renders sit at `output/<slug>.mp4|.thumb.jpg|.meta.json`). Back up first.
- `.env` holds the owner's `GEMINI_API_KEY`. Never print or commit it.

**Where things are now**
- UI: `ui/server.py` (FastAPI, token + Host-header guard, jobs via `ui/jobs.py`, single heavy queue), `ui/static/{index.html,app.js,style.css}`.
- LLM: `llm/providers.py`, `llm/tasks.py` (schemas + normalizers), `llm/cli.py`.
- Render: `make_video.py`, `pipeline/{render,qa,thumbnail,router}.py`, `studio/src/**`, `studio/scripts/stills.mjs`.
- Audio: `audio_pipeline/{make_voice_and_subs,mix_music_and_sfx,sfx}.py` (SFX are synthesized into `audio_pipeline/sfx_library/*.wav`, which is gitignored today; v2 adds a committed `manifest.json`).
- Scheduler/publisher: `scheduler/run_scheduler.py` (`state.sqlite`: jobs/uploads/events/posts), `publisher/{publish,official_apis,post_log}.py`.
- Tests: `tests/` (158 passing). Checks: `scripts/doctor.py`, `scripts/smoke_test.py`.

## Status after implementation
- Done: all nine sections. Verified with `scripts/doctor.py`, `scripts/smoke_test.py`, `ruff check` / `ruff format --check`, `pytest` and `npx tsc --noEmit`.
- Not verified here (needs your accounts or a long unattended run): real Google Search grounding on a paid key, Instagram/TikTok official API calls, Telegram/Discord delivery, a real overnight batch, and the Windows keep-awake effect over hours.
- `ui/static` is exercised through the API and syntax checks, not a browser test run.
- Follow-ups worth considering: move the project outside OneDrive; per-aspect outputs (re-rendering 16:9 or 9:16 replaces the current file).

### Completion pass
Each section has its own commit: §1 cbf7b06, §2 5114700, §3 ebed535, §4 0d2d1db, §5 cd9cc41, §6 e5e3062, §7 72dc97c, §8 7fc8cb5, §9 38f140d. The v3 React studio (`frontend/`, 0f7994c) carries the v2 UI features over.
- §6 addition: `scripts/migrate_output.py --root <repo>` migrates another checkout's `output/`, `data/projects.db` and scheduler state; it exits 2 when `<repo>/output` is missing.
- Nav order: kept the v3 order (Create, Library, Ideas, Batch, Schedule, Settings) by owner decision. The v3 redesign supersedes §1's order.
- Done checks in the worktree: `scripts/doctor.py` all required checks passed; `scripts/smoke_test.py` PASSED (visual QA pass, 5 frames); `ruff check` all passed and `ruff format --check` 99 files formatted; `pytest` 158 passed; `npx tsc --noEmit` clean in `frontend/` and `studio/`.
