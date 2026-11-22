# video-factory

Local video and Shorts production with a web UI. Type a topic (or paste reference videos to learn a style from), approve the ideas you like, and get a captioned, music-ducked, -14 LUFS H.264/AAC MP4 at 9:16, 16:9 or 1:1, with a code-rendered thumbnail and AI titles/hashtags, ready to upload (unlisted by default) to YouTube, Instagram or TikTok, now or on a schedule.

No Pexels and no paid APIs required. Voices come from Edge-TTS (free) or Kokoro (local, GPU), captions from faster-whisper (local, GPU), music from a bundled royalty-free library with Archive.org/Wikimedia fallbacks, sound effects are synthesized locally, footage comes from Wikimedia Commons, Archive.org and NASA (keyless), rendering from Remotion, Manim, handanim or explainroo (local). Writing (ideas, scripts, metadata) uses the Gemini free tier by default, Ollama for fully offline, or any OpenAI-compatible endpoint. Uploads use browser cookies via social-auto-upload, or the official APIs once your apps are approved.

## Quickstart

```powershell
python scripts\bootstrap.py                    # fresh clone only: venv, GPU libs, npm, engines, music, skills, assets
.venv\Scripts\python scripts\doctor.py         # health check
.venv\Scripts\python scripts\smoke_test.py     # 5 s end-to-end render with checks
.venv\Scripts\python ui\server.py              # web UI at http://127.0.0.1:8765
```

Then add your Gemini key in **Settings** and render `projects/concept-001` from the **Create** tab. Full walkthrough: [docs/FIRST_VIDEO_GUIDE.md](docs/FIRST_VIDEO_GUIDE.md).

## What is in here

| Module | Entry point | Does |
| --- | --- | --- |
| Web UI | `ui/server.py` | Create · Ideas · Batch · Library (player, QA, metadata, publish) · Schedule (pre-flight, builder) · Settings (keys, platform logins, alerts, spend limit) |
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
- [SCHEDULER.md](docs/SCHEDULER.md): pre-flight, builder, gate, caps, running at startup, inspecting state
- [BATCH_SHEETS.md](docs/BATCH_SHEETS.md): Excel / CSV / Google Sheets batches
- [ADDING_STYLES.md](docs/ADDING_STYLES.md): blueprints from reference videos, scene types, transitions, engines, skills

## Development

```powershell
.venv\Scripts\ruff check . ; .venv\Scripts\ruff format --check .
.venv\Scripts\python -m pytest
cd studio; npx tsc --noEmit
```

## Licenses

Our code: MIT. Brand profile from [claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit) (MIT, see `studio/LICENSE-claude-code-video-toolkit`). Remotion is free for individuals and teams of up to 3 people; larger companies need a [company license](https://www.remotion.dev/license). Music tracks come from the YouTube Audio Library via [short-video-maker](https://github.com/gyoridavid/short-video-maker) and are free to use, including in monetized videos; fallback tracks keep their own CC0 / public-domain / CC BY licenses, credited in the upload description. Map outlines: [Natural Earth](https://www.naturalearthdata.com/) (public domain). Archive media keeps each item's own license, recorded in `attribution.json` and appended to upload descriptions.
