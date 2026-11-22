# video-factory

Local, zero-API video and Shorts production. Write a `script.json` (or let Kiro write it), run one command, and get a captioned, music-ducked, -14 LUFS H.264/AAC MP4 at 9:16, 16:9 or 1:1, ready to upload unlisted to YouTube, Instagram or TikTok on a schedule.

No paid APIs and no Pexels key. Voices come from Edge-TTS (free) or Kokoro (local), captions from faster-whisper (local), music from a bundled royalty-free library, footage from Wikimedia Commons, Archive.org and NASA (keyless), rendering from Remotion, Manim, handanim or explainroo (local), and uploads from browser cookies via social-auto-upload.

## Quickstart

```powershell
python scripts\bootstrap.py                       # fresh clone only: venv, npm, engines, music, skills
.venv\Scripts\python scripts\doctor.py            # health check
.venv\Scripts\python scripts\smoke_test.py        # 5 s end-to-end render with checks
.venv\Scripts\python make_video.py projects\concept-001
```

Output: `output\concept-001.mp4` and `output\concept-001.meta.json`. Full walkthrough: [docs/FIRST_VIDEO_GUIDE.md](docs/FIRST_VIDEO_GUIDE.md).

## What is in here

| Module | Entry point | Does |
| --- | --- | --- |
| Orchestrator | `make_video.py` | voice -> music -> route -> QA stills -> render -> metadata |
| Analyzer | `analyzer/analyze_reference.py` | Reference video -> contact sheets, transcript, shot pacing -> `style_blueprint.json` + 5-idea approval gate |
| Voice + captions | `audio_pipeline/make_voice_and_subs.py` | Edge-TTS / Kokoro -> `narration.wav`, faster-whisper -> word-level `captions.json` |
| Music | `audio_pipeline/mix_music_and_sfx.py` | Mood pick from `manifest.json`, `sidechaincompress` ducking, -14 LUFS |
| Media | `media_pipeline/fetch_free_media.py` | Keyless Wikimedia / Archive.org / NASA + `attribution.json`, hash cache |
| Studio | `studio/` | Remotion: `ConceptExplainer`, `VoxEditorial`, `WhiteboardDraw`, `UniversalCustom` |
| Engines | `engines/` | Manim, handanim, explainroo, long-to-short clipper, OpenMontage |
| Scheduler | `scheduler/run_scheduler.py` | `schedule.yaml` + APScheduler + `state.sqlite`, retries, daily caps |
| Publisher | `publisher/publish.py` | social-auto-upload wrapper, YouTube unlisted by default |

## Docs

- [FIRST_VIDEO_GUIDE.md](docs/FIRST_VIDEO_GUIDE.md): first render, preview, cookie login, test upload
- [ARCHITECTURE.md](docs/ARCHITECTURE.md): data flow, folder map, every JSON/YAML schema
- [DEBUGGING.md](docs/DEBUGGING.md): FFmpeg, TTS, Whisper CPU/GPU, Remotion, ducking, cookies
- [SCHEDULER.md](docs/SCHEDULER.md): batches, caps, running at startup, inspecting state
- [ADDING_STYLES.md](docs/ADDING_STYLES.md): blueprints from reference videos, new scene types, engines, skills

## Development

```powershell
.venv\Scripts\ruff check . ; .venv\Scripts\ruff format --check .
.venv\Scripts\python -m pytest
cd studio; npx tsc --noEmit
```

## Licenses

Our code: MIT. Brand profile from [claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit) (MIT, see `studio/LICENSE-claude-code-video-toolkit`). Remotion is free for individuals and teams of up to 3 people; larger companies need a [company license](https://www.remotion.dev/license). Music tracks come from the YouTube Audio Library via [short-video-maker](https://github.com/gyoridavid/short-video-maker) and are free to use, including in monetized videos. Archive media keeps each item's own license, recorded in `attribution.json` and appended to upload descriptions.
