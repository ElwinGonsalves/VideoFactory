# video-factory

Local video and Shorts production with a web UI. Type a topic (or paste reference videos to learn a style from), approve the ideas you like, and get a captioned, music-ducked, -14 LUFS H.264/AAC MP4 at 9:16, 16:9 or 1:1, with a code-rendered thumbnail and AI titles/hashtags, ready to upload (unlisted by default) to YouTube, Instagram or TikTok, now or on a schedule.

No Pexels and no paid APIs required. Voices come from Edge-TTS (free) or Kokoro (local, GPU), captions from faster-whisper (local, GPU), music from a bundled royalty-free library with Archive.org/Wikimedia fallbacks, sound effects are synthesized locally, footage comes from Wikimedia Commons, Archive.org and NASA (keyless), rendering from Remotion, Manim, handanim or explainroo (local). Writing (ideas, scripts, metadata) uses the Gemini free tier by default, Groq or OpenRouter free models, Ollama for fully offline, or any OpenAI-compatible endpoint; if one fails (bad key, used-up quota) the next one with a key takes over. Uploads use browser cookies via social-auto-upload, or the official APIs once your apps are approved.

## Start in under 5 minutes

Needs Python 3.10+, Node 20+ and FFmpeg on PATH.

```powershell
git clone https://github.com/ElwinGonsalves/VideoFactory video-factory
cd video-factory
.\start.ps1            # macOS/Linux: ./start.sh
```

The first run creates `.venv`, installs Remotion and builds the studio UI (the minimum, a few minutes), then opens http://127.0.0.1:8765. Later runs start straight away. `.\start.ps1 -Full` also installs the optional extras (CUDA libraries for Kokoro and Whisper, the Explainroo/OpenMontage/clipper engines, the uploader, the music library, agent skills); `.\start.ps1 -Port 8766 -NoBrowser` picks another port.

The first-run guide offers **Judge Demo Mode**, which needs no API key: a sample Short, a sample Style Blueprint and a sample Batch preview. To write your own scripts, paste a free Gemini key in step 2 (or later in **Settings**), or point it at Ollama. Full walkthrough: [docs/FIRST_VIDEO_GUIDE.md](docs/FIRST_VIDEO_GUIDE.md).

Checks:

```powershell
.\.venv\Scripts\python.exe scripts\doctor.py       # health check
.\.venv\Scripts\python.exe scripts\smoke_test.py   # 5 s end-to-end render with checks
```

## The studio

- **Create**: from an idea or your exact script, pick a look from Style Picker cards (real frames from each engine), then render.
- **Ideas**: brainstorm from a topic, or learn a style's "DNA" from reference videos and approve the pitches you like.
- **Batch**: drop an Excel/CSV sheet or paste a Google Sheets link; rows are checked before anything renders.
- **Library**: the video in a 9:16 phone frame, QA frames, fact-check notes, download, publish, metadata.
- **Schedule**: pre-flight checks, then a staggered builder for an overnight queue.
- **Studio Status Pill → Activity Drawer**: what is rendering now (a 5-node stepper: Script → Voice → Music+SFX → Render → QA), what is scheduled next, and recent results with Open in Library / Retry.
- **Stitched Engines**: live health of every engine in the pipeline.

The previous UI is still at `/classic`.

## Frankenstein architecture

video-factory is a creature stitched from independent open-source organs. Each does one job and is swapped or skipped without touching the others:

| Organ | Engine | Job |
| --- | --- | --- |
| Brain | Gemini free tier / Ollama / OpenAI-compatible | Ideas, scripts, titles, reading reference frames |
| Voice box | Edge-TTS or Kokoro | Narration |
| Ears | faster-whisper | Word-level captions (audio is the master clock) |
| Heart | FFmpeg | Music ducking, SFX, -14 LUFS, H.264 encode |
| Skeleton | Remotion | Concept, Vox, whiteboard and long-form compositions |
| Left hand | Explainroo | Rough.js whiteboard engine |
| Right hand | Manim | Math and algorithm animation |
| Eyes | WatchVideo + PySceneDetect | Reading reference videos into a Style Blueprint |
| Hands | Playwright (social-auto-upload) | Cookie-based uploads |

`pipeline/router.py` picks the organs for a style, `make_video.py` runs them in order, and `pipeline/qa.py` checks the stills for clipping and Shorts safe zones before the final render. The studio parses each job's log into the 5-node stepper (`ui/studio.py`).

## How Kiro built it

- **Spec**: `.kiro/specs/studio-ui-v3/` holds the requirements (EARS), design and task list for the UI rebuild; each task traces to a requirement.
- **Steering**: `.kiro/steering/video-factory.md` (always on) encodes the pipeline rules: audio first, safe zones, the QA-stills loop, approval before rendering ideas. `.kiro/steering/studio-ui.md` loads for `frontend/**` and points at `DESIGN.md`, the UI primitives and the test port.
- **Hooks**: `.kiro/hooks/` rebuilds and runs the 4-viewport Playwright audit after frontend edits, and lints and tests Python on save.
- **MCP**: the handanim whiteboard server (`.kiro/settings/mcp.example.json`; `bootstrap.py --mcp` writes your local copy).
- **Design process**: the audit, critique and design-system work are in [docs/UX_AUDIT.md](docs/UX_AUDIT.md), the visual system in [DESIGN.md](DESIGN.md), product context in [PRODUCT.md](PRODUCT.md).

## What is in here

| Module | Entry point | Does |
| --- | --- | --- |
| Web UI | `start.ps1` → `ui/server.py`, React app in `frontend/` | Status Pill + Activity Drawer · Create · Ideas · Batch · Library (player, QA, metadata, publish) · Schedule (pre-flight, builder) · Settings (keys, platform logins, alerts, spend limit) |
| Orchestrator | `make_video.py` | voice → music + SFX → route → visual QA → render → thumbnail + metadata |
| Language model | `llm/` | Gemini / Ollama / OpenAI-compatible: ideas, scripts, titles, hashtags, reading reference frames |
| Analyzer | `analyzer/analyze_reference.py` | Reference links → contact sheets, transcript, shot pacing, vision → `style_blueprint.json` → 5 ideas → approval |
| Voice + captions | `audio_pipeline/make_voice_and_subs.py` | Edge-TTS / Kokoro → `narration.wav`, faster-whisper → word-level `captions.json` |
| Music + SFX | `audio_pipeline/mix_music_and_sfx.py`, `sfx.py` | Mood pick from `manifest.json`, `sidechaincompress` ducking, scene-change SFX, -14 LUFS |
| Media | `media_pipeline/fetch_free_media.py` | Keyless Wikimedia / Archive.org / NASA + `attribution.json`, hash cache, textures |
| Studio | `studio/` | Remotion: `ConceptExplainer`, `VoxEditorial`, `WhiteboardDraw`, `UniversalCustom`, `Thumbnail`; frame-0 cover, maps, transitions |
| Visual QA | `pipeline/qa.py` | Pixel checks for Shorts safe zones, clipping, empty frames, cover contrast |
| Engines | `engines/` | Manim, handanim (+ MCP), explainroo, long-to-short clipper (optional speaker tracking), OpenMontage |
| Scheduler | `scheduler/run_scheduler.py` | `schedule.yaml` + APScheduler + `state.sqlite`, retries, shared daily caps |
| Publisher | `publisher/publish.py` | Cookie (social-auto-upload) or official API per platform, YouTube unlisted by default |

## Docs

- [FIRST_VIDEO_GUIDE.md](docs/FIRST_VIDEO_GUIDE.md): first render, the UI, keys, cookie login, test upload
- [ARCHITECTURE.md](docs/ARCHITECTURE.md): data flow, folder map, every JSON/YAML schema, UI security
- [DEBUGGING.md](docs/DEBUGGING.md): FFmpeg, TTS, GPU, Remotion, LLM, yt-dlp, engines, ducking, cookies
- [CONNECT_ACCOUNTS.md](docs/CONNECT_ACCOUNTS.md): YouTube and Instagram official APIs step by step, plus Telegram and Discord alerts
- [SCHEDULER.md](docs/SCHEDULER.md): pre-flight, builder, gate, caps, running at startup, inspecting state
- [BATCH_SHEETS.md](docs/BATCH_SHEETS.md): Excel / CSV / Google Sheets batches
- [ADDING_STYLES.md](docs/ADDING_STYLES.md): blueprints from reference videos, scene types, transitions, engines, skills
- [UX_AUDIT.md](docs/UX_AUDIT.md) and [DESIGN.md](DESIGN.md): the UI audit, the rebuild's verification, and the visual system

## Development

```powershell
.\.venv\Scripts\ruff.exe check . ; .\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe -m pytest
cd studio; npx tsc --noEmit; cd ..\frontend; npm run build   # tsc + vite build
```

## Licenses

Our code: MIT. Brand profile from [claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit) (MIT, see `studio/LICENSE-claude-code-video-toolkit`). Remotion is free for individuals and teams of up to 3 people; larger companies need a [company license](https://www.remotion.dev/license). Music tracks come from the YouTube Audio Library via [short-video-maker](https://github.com/gyoridavid/short-video-maker) and are free to use, including in monetized videos; fallback tracks keep their own CC0 / public-domain / CC BY licenses, credited in the upload description. Map outlines: [Natural Earth](https://www.naturalearthdata.com/) (public domain). Archive media keeps each item's own license, recorded in `attribution.json` and appended to upload descriptions.
