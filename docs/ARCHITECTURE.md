# Architecture

video-factory turns a prompt, a `script.json`, a scheduled job, or reference videos into a finished MP4 plus thumbnail and upload metadata. Rendering, voice, captions, music and media are local or keyless. The only network services are Edge-TTS, the open archives, and the language model you choose (Gemini free tier by default, Ollama for fully offline).

## Data flow

```text
                     ┌──────────── ui/server.py (127.0.0.1, token) ───────────┐
                     │ Create · Ideas · Library · Schedule · Settings · logs  │
                     └──────────────┬─────────────────────────────────────────┘
                                    │ runs each action as a logged subprocess (ui/jobs.py)
 reference URLs ──► analyzer/analyze_reference.py ──► contact sheets, transcript, scenes.csv
                     (yt-dlp, ffmpeg, faster-whisper, PySceneDetect)
                                    │ llm.tasks.read_reference_frames (vision)
                                    ▼
                    analyzer/blueprints/<style>.json ──► llm.tasks.generate_ideas ──► ideas.json (5)
                                    │                                  user approval (Ideas tab)
 prompt ──► llm.tasks.write_script ─┴──────────────► projects/<slug>/script.json ◄── schedule.yaml
                                    │
                           make_video.py (orchestrator)
   1 audio_pipeline/make_voice_and_subs.py  Edge-TTS | Kokoro (GPU) ─► narration.wav 48 kHz
                                            faster-whisper (GPU)     ─► captions.json, timing.json
   2 audio_pipeline/mix_music_and_sfx.py    mood track + sfx.auto_cues ─► mixed_master.wav (-14 LUFS)
   3 pipeline/router.py                     style ─► engine, composition, transition, look
   4 pipeline/render.py + pipeline/qa.py    cover + 4 stills, pixel checks ─► qa/report.json
   5 Remotion (studio/) or engines/*        ─► output/<slug>.mp4 (H.264 yuv420p + AAC, faststart)
   6 pipeline/thumbnail.py + llm.tasks      ─► output/<slug>.thumb.jpg, output/<slug>.meta.json
                                    │
   publisher/publish.py ── cookie (social-auto-upload) | api (official_apis.py) ──► YouTube / Instagram / TikTok
                       └── publisher/post_log.py: daily caps + post history (scheduler/state.sqlite)
```

Audio is the master clock: scene start/end times in `timing.json` come from the synthesized narration, and every engine sizes its video to `mixed_master.wav`.

## Folder map

| Path | Role |
| --- | --- |
| `make_video.py` | One-command orchestrator for a project folder |
| `common/` | Paths, hashing, JSON IO, subprocess/ffprobe helpers, CUDA DLL registration; `settings.py` for `.env` + `config/settings.json` |
| `llm/` | `providers.py` (Gemini, Ollama, OpenAI-compatible), `tasks.py` (ideas, scripts, metadata, frame reading), `cli.py` |
| `ui/` | `server.py` (FastAPI), `jobs.py` (subprocess jobs + logs), `static/` (HTML/CSS/JS, no build step) |
| `analyzer/` | Reference analysis, blueprints, idea generation, approval |
| `audio_pipeline/` | TTS, word captions, music library + fallbacks, ducking + loudness, `sfx.py` |
| `media_pipeline/` | Keyless archive fetcher, URL-hash cache, offline textures |
| `pipeline/` | Router, render/QA/validation, `qa.py` pixel checks, `thumbnail.py` |
| `studio/` | Remotion: 4 video compositions + `Thumbnail`, shared components, `scripts/stills.mjs` |
| `engines/` | Manim, handanim, explainroo, clipper (speaker tracking), OpenMontage; shared caption burn-in |
| `scheduler/` | `schedule.yaml` + APScheduler daemon + `state.sqlite` |
| `publisher/` | `publish.py`, `official_apis.py`, `post_log.py`; vendored `social-auto-upload` |
| `scripts/` | `doctor.py`, `smoke_test.py`, `bootstrap.py`, `setup_repos.ps1/.sh`, `seed_music.py`, `install_skills.py`, `fetch_geo.py` |
| `.agent/skills/` | 69 SKILL.md files from 12 zero-API packs |
| `.kiro/steering/` | Rules Kiro follows; `.kiro/settings/mcp.json` (local) wires the handanim MCP server |
| `projects/<slug>/` | `script.json` (committed); `assets/`, `qa/`, `props.json` (ignored) |
| `output/` | MP4, thumbnail, `.meta.json` (ignored) |
| `config/` | `settings.json` preferences, `secrets/` OAuth files (ignored) |

Gitignored and recreated by `python scripts/bootstrap.py`: `.venv`, `node_modules`, vendored repos (`engines/openmontage`, `engines/explainroo`, `engines/clipper`, `publisher/social-auto-upload`), music MP3s, textures, the SFX library, caches, logs, `.env`, `config/`, cookies.

## Studio (Remotion)

| Composition | Theme | Look | Default transition |
| --- | --- | --- | --- |
| `ConceptExplainer` | concept | dark gradient with drifting glow, glass cards, animated bars | fade (whip_pan for case_study, hard_cut for kinetic_type) |
| `VoxEditorial` | vox | paper-grain texture, white-bordered print photos, yellow highlighter, serif heads | paper_slide |
| `WhiteboardDraw` | whiteboard | grid board, sketch borders, stroke-dashoffset pen reveals | pen_draw |
| `UniversalCustom` | `props.theme` | any of the above or `minimal` | fade |
| `Thumbnail` | any | blurred video frame or sharp archive photo, scrim, accent edge, hook text | (still) |

Shared components (`studio/src/components/`): `SafeZone`, `Captions` (word_highlight / phrase_box / minimal_editorial), `SceneView` (headline, stat, bullets, chart, image, quote, flow, map), `MapView` (d3-geo Natural Earth projection over `public/geo/countries.geojson`, highlighted countries fill in one by one, auto-zoom for up to 4 countries), `Cover` (frame-0 hook card), `Transition`, `Background`, `primitives`.

**Frame 0 cover.** When `coverText` is set (from `cover_text`, else the first heading, max 5 words), frames 0–15 show a full-contrast hook card inside the safe zone, then dissolve over 0.25 s. Scene 0 never fades in, so the cover sits on a finished frame. Feeds and auto-thumbnails pick up this image.

**Safe zones** (`studio/src/format.ts`): 9:16 keeps 22% bottom, 15% right, 6% top/left free; other ratios 5%. Scene content stays above a 230 px caption band.

**Stills** are rendered by `studio/scripts/stills.mjs`: one bundle and one browser for all QA frames and the thumbnail.

## Visual QA (`pipeline/qa.py`)

Each QA frame is rendered twice: normally and with `qaHideContent` (background only). The pixel difference is exactly the content. Checks: content inside the 9:16 unsafe bands (>0.2% of the band), content touching the frame edge, an almost-empty frame, and cover contrast (luma std-dev ≥ 45). Results go to `projects/<slug>/qa/report.json`, with `<frame>.overlay.png` painting problems magenta. `--strict-qa` stops before the final render if anything fails.

## LLM layer (`llm/`)

`get_provider()` reads Settings. All three providers support JSON-schema output, retries with backoff on 429/5xx, and clear errors naming the setting to fix. Gemini tries the newer `interactions` endpoint, then `generateContent`, then each fallback model (`gemini_fallback_models`), and remembers the one that worked. Vision (`vision_json`) works with Gemini, OpenAI-compatible vision models, and Ollama vision models.

| Task | Input | Output (validated) |
| --- | --- | --- |
| `read_reference_frames` | contact sheets + what the first 3 s say | blueprint hook visuals, on-screen text, style notes, caption/transition picks |
| `generate_ideas` | blueprint + transcript/pacing notes + niche | 5 × {title, hook, angle, case_study, style, music_mood, why_it_works} |
| `write_script` | brief, style, aspect, duration, language | script.json (6–9 scenes, cover_text, facts_to_verify) |
| `write_metadata` | script narration | 3 titles, 3 hooks, thumbnail_text, description, ≤8 hashtags (#shorts first for YouTube), tags ≤480 chars, pinned comment |

Normalizers clip every string, coerce chart values to numbers, drop invalid visuals to headlines, and keep only ISO-A3 country codes, so model output can never break a render.

## JSON / YAML contracts

### `projects/<slug>/script.json`

```jsonc
{
  "title": "string (<=100 chars)",
  "cover_text": "2-5 word frame-0 hook ('' disables the cover)",
  "description": "string", "tags": ["..."],
  "style": "concept_explainer | case_study | kinetic_type | ui_demo | vox_documentary | editorial_map | news_breakdown | whiteboard | hand_drawn | sketch | explainroo | handanim | math_science | algorithm | clip_repurpose | hybrid_or_custom | openmontage",
  "aspect_ratio": "9:16 | 16:9 | 1:1",
  "music_mood": "chill | documentary | upbeat | dramatic",
  "caption_style": "word_highlight | phrase_box | minimal_editorial | none",
  "transition": "hard_cut | fade | whip_pan | paper_slide | pen_draw",          // optional; route/blueprint default
  "sfx": "auto | none | [{ \"file\": \"x.wav\", \"at\": 1.2, \"volume\": 0.6 }]", // default auto
  "platforms": ["youtube", "instagram", "tiktok"],
  "visibility": "unlisted | private | public",
  "voice": { "engine": "edge-tts | kokoro", "voice": "en-US-AndrewNeural | af_heart | ef_dora", "rate": "+5%" },
  "facts_to_verify": ["claims with numbers, shown in the Library"],
  "metadata": { "title": "...", "description": "...", "hashtags": [], "tags": [] },  // Library edits, kept on re-render
  "blueprint": "analyzer/blueprints/x.json", "approval": "approved", "idea": { },     // from approve_ideas
  "scenes": [
    {
      "beat": "hook | concept | case_study | takeaway | other",
      "narration": "spoken text for this scene",
      "visual": {
        "type": "headline | stat | bullets | chart | image | quote | flow | map",
        "heading": "...", "text": "...", "value": "7M+", "label": "...",
        "items": ["..."], "data": [{ "label": "2007", "value": 7 }],
        "countries": ["USA", "IND"],
        "src": "assets/<slug>/media/file.jpg", "credit": "author / license"
      },
      "media_query": "apollo 11 launch"   // openmontage engine fetches a keyless archive image
    }
  ],
  "manim": { "file": "engines/manim_scenes/example_scene.py", "scene": "ConceptGraph" },
  "handanim": { "file": "engines/handanim_scenes/whiteboard_scene.py" },
  "explainroo": { "project": "projects/<slug>/explainroo", "workers": 2, "quality": "fast", "watermark": false },
  "clip": { "source": "url-or-file", "min_sec": 15, "max_sec": 45, "speaker_tracking": false },
  "openmontage": { "pipeline": "documentary-montage", "theme": "vox" }
}
```

### `assets/timing.json`, `assets/captions.json`

```json
{ "total_duration_sec": 4.978, "engine": "edge-tts", "voice": "en-US-AndrewNeural", "rate": "+0%",
  "scenes": [{ "index": 0, "start": 0.0, "end": 2.122, "text": "..." }], "narration": "narration.wav" }
```

```json
[{ "word": "Why", "start": 0.0, "end": 0.22 }]
```

### `audio_pipeline/music_library/manifest.json` and `assets/attribution.json`

```json
{ "tracks": [{ "file": "documentary/Hopeless - Jimena Contreras.mp3", "mood": "documentary", "upstream_mood": "sad",
  "bpm": null, "license": "...", "source": "...", "title": "...", "artist": "..." }] }
```

```json
{ "music": { "...manifest track..." }, "sfx": ["subtle_whoosh", "pop"],
  "media": [{ "source": "wikimedia", "title": "...", "author": "...", "license": "...", "url": "...", "page_url": "...", "file": "..." }] }
```

Music source order: local library → Archive.org public-domain search → Wikimedia Commons (CC0 / public domain / CC BY, never NC/ND) → any local mood. Downloads are added to the manifest.

### `output/<slug>.meta.json`

```json
{ "slug": "concept-001", "file": "output/concept-001.mp4", "aspect_ratio": "9:16",
  "title": "...", "title_variants": ["...", "...", "..."], "hook_variants": ["..."],
  "description": "...", "hashtags": ["#shorts", "#business"], "tags": ["..."], "pinned_comment": "...",
  "thumbnail_text": "...", "thumbnail": "output/concept-001.thumb.jpg",
  "platform_targets": ["youtube"], "visibility": "unlisted", "music_attribution": "Music: ...",
  "facts_to_verify": ["..."], "qa_ok": true, "metadata_source": "llm | user | script" }
```

Upload description = description + hashtags + music credit (`publisher.publish.full_description`).

### `analyzer/blueprints/<style>.json`

BUILD_SPEC Module A's `style_blueprint.json`, plus measured `median_shot_sec`, `words_per_minute`, `sources`, `created`, and after the vision step `on_screen_text` and `visual_style_notes`. Work folder `analyzer/work/<date>-<style>/` holds `ref<N>/{media,frames,audio,transcript.json,scenes.csv}`, `analysis.json`, `ideas.json`, `IDEAS.md`, `approval.json`.

### `scheduler/schedule.yaml` and `scheduler/state.sqlite`

See `docs/SCHEDULER.md`. Tables: `jobs`, `uploads`, `events`, and `posts` (shared with `publisher/post_log.py`: every successful post from any path, used for daily caps).

### Settings

| File | Holds | In git |
| --- | --- | --- |
| `.env` | `GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OLLAMA_HOST`, `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`, `TIKTOK_ACCESS_TOKEN` | no (`.env.example` is) |
| `config/settings.json` | `llm`, `defaults` (voice, style, aspect, mood, niche, language, length), `publish` (method/account per platform), `clipper` | no |
| `config/secrets/` | `youtube_client_secret.json`, `youtube_token.json` | no |

## Caching

| What | Key | Location |
| --- | --- | --- |
| TTS per scene | sha256(engine, voice, rate, text) | `audio_pipeline/cache/*.wav` |
| Music loudness | sha256(file bytes) | `audio_pipeline/cache/music_lufs.json` |
| Archive media | sha256(url) | `media_pipeline/cache/` |
| Remotion bundle | webpack cache | `studio/node_modules/.cache` |

## UI security

Binds to `127.0.0.1`. A random token per launch is embedded in the page and required on every `/api` call and media file; other websites cannot read it (same-origin policy), and a Host-header check blocks DNS rebinding. With `--host 0.0.0.0`, the page itself also requires the token (printed link). Secrets are write-only from the browser (masked on read), keys are allow-listed and single-line, file serving is restricted to `output/`, `projects/`, `analyzer/work/` and `studio/public/assets/`, and all job inputs are validated before they reach a subprocess argument list (never a shell).
