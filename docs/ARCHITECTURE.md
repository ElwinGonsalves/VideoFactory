# Architecture

video-factory turns a `script.json` (or a scheduled job, or a reference video) into a finished MP4 plus upload metadata, using only local tools and keyless public archives.

## Data flow

```text
 reference URL/file ──► analyzer/analyze_reference.py ──► analyzer/blueprints/<style>.json
                                   │                         + work/<run>/IDEAS.md (5 ideas)
                                   ▼
                         human approval (approve --ideas)
                                   │
 prompt ──(agent writes)──► projects/<slug>/script.json ◄── scheduler/schedule.yaml
                                   │
                         make_video.py (orchestrator)
                                   │
   1 audio_pipeline/make_voice_and_subs.py   Edge-TTS | Kokoro  ─► narration.wav (48 kHz)
                                             faster-whisper     ─► captions.json, timing.json
   2 audio_pipeline/mix_music_and_sfx.py     manifest.json mood ─► mixed_master.wav (-14 LUFS)
                                             sidechaincompress ducking, attribution.json
   (media_pipeline/fetch_free_media.py       Wikimedia/Archive.org/NASA ─► assets/media + attribution.json)
   3 pipeline/router.py                      style ─► engine + composition
   4 pipeline/render.py                      4 QA stills ─► projects/<slug>/qa/*.png
   5 Remotion (studio/) or engines/*         ─► output/<slug>.mp4 (H.264 yuv420p + AAC, faststart)
   6 make_video.py                           ─► output/<slug>.meta.json
                                   │
                    publisher/publish.py (social-auto-upload, cookies) ─► YouTube / Instagram / TikTok
```

Audio is the master clock. Scene start/end times in `timing.json` come from the synthesized narration, and every engine sizes its video to `mixed_master.wav`.

## Folder map

| Path | Role |
| --- | --- |
| `make_video.py` | One-command orchestrator for a project folder |
| `common/` | Shared paths, hashing, JSON IO, subprocess and ffprobe helpers |
| `analyzer/` | Reference analysis, blueprints, idea approval gate |
| `audio_pipeline/` | TTS, word captions, music library, ducking + loudness |
| `media_pipeline/` | Keyless archive fetcher, URL-hash cache, offline textures |
| `pipeline/` | Style router and Remotion render/QA/validation helpers |
| `studio/` | Remotion project: 4 compositions sharing one component set |
| `engines/` | Wrappers for explainroo, handanim, Manim, the clipper and OpenMontage |
| `scheduler/` | `schedule.yaml` + APScheduler daemon + `state.sqlite` |
| `publisher/` | `publish.py` wrapper around vendored `social-auto-upload` |
| `scripts/` | `doctor.py`, `smoke_test.py`, `bootstrap.py`, `seed_music.py`, `install_skills.py` |
| `.agent/skills/` | Installed SKILL.md packs (Remotion, iart-ai, Vox, media getter, watchvideo) |
| `.kiro/steering/` | Rules Kiro follows when it drives the pipeline |
| `projects/<slug>/` | `script.json` (committed); `assets/`, `qa/`, `props.json` (ignored) |
| `output/` | Rendered MP4 + `.meta.json` (ignored) |

Vendored third-party code (`engines/openmontage`, `engines/explainroo`, `engines/clipper`, `publisher/social-auto-upload`) and downloaded music are gitignored and recreated with `python scripts/bootstrap.py`.

## Studio (Remotion)

All four compositions render through `ThemedVideo`; they differ only in theme:

| Composition | Theme | Look |
| --- | --- | --- |
| `ConceptExplainer` | concept | dark gradient, glass cards, animated bars, word-highlight captions |
| `VoxEditorial` | vox | paper grain, white-bordered print cards, yellow highlighter sweep, serif heads |
| `WhiteboardDraw` | whiteboard | grid board, sketch borders, stroke-dashoffset pen reveals |
| `UniversalCustom` | `props.theme` | any of the above or `minimal` |

Shared components in `studio/src/components/`: `SafeZone` (insets + red debug overlay), `Captions` (word_highlight / phrase_box / minimal_editorial), `SceneView` (headline, stat, bullets, chart, image, quote, flow), `primitives` (Card, Highlight, DrawPath), `Background`.

Width, height and duration come from props in `calculateMetadata`: `aspectRatio` picks 1080x1920, 1920x1080 or 1080x1080, and `durationSec` sets the frame count at 30 fps.

Safe zones (`studio/src/format.ts`): for 9:16, 22% bottom, 15% right, 6% top/left. Other ratios use a 5% margin. Scene content sits in the safe area above a 230 px caption band, so captions never overlap visuals.

## JSON / YAML contracts

### `projects/<slug>/script.json`

```jsonc
{
  "title": "string (<=100 chars for YouTube)",
  "slug": "optional; defaults to folder name",
  "description": "string", "tags": ["..."],
  "style": "concept_explainer | vox_documentary | whiteboard | math_science | clip_repurpose | hybrid_or_custom | openmontage | ...",
  "aspect_ratio": "9:16 | 16:9 | 1:1",
  "music_mood": "chill | documentary | upbeat | dramatic",
  "caption_style": "word_highlight | phrase_box | minimal_editorial | none",   // optional, router default
  "platforms": ["youtube", "instagram", "tiktok"],
  "visibility": "unlisted | private | public",                                 // default unlisted
  "voice": { "engine": "edge-tts | kokoro", "voice": "en-US-AndrewNeural | af_heart", "rate": "+0%" },
  "sfx": [{ "file": "path.wav", "at": 1.2, "volume": 0.6 }],                   // optional
  "blueprint": "analyzer/blueprints/x.json", "approval": "approved",           // set by analyzer approve
  "scenes": [
    {
      "narration": "spoken text for this scene",
      "visual": {
        "type": "headline | stat | bullets | chart | image | quote | flow",
        "heading": "...", "text": "...", "value": "7M+", "label": "...",
        "items": ["..."], "data": [{ "label": "2007", "value": 7 }],
        "src": "assets/<slug>/media/file.jpg", "credit": "author / license"
      },
      "media_query": "apollo 11 launch"   // openmontage engine only
    }
  ],
  "manim": { "file": "engines/manim_scenes/example_scene.py", "scene": "ConceptGraph" },
  "handanim": { "file": "engines/handanim_scenes/whiteboard_scene.py" },
  "explainroo": { "project": "projects/<slug>/explainroo" },
  "clip": { "source": "url-or-file", "min_sec": 15, "max_sec": 45 }
}
```

### `assets/timing.json` (audio master clock)

```json
{ "total_duration_sec": 4.978, "engine": "edge-tts", "voice": "en-US-AndrewNeural", "rate": "+0%",
  "scenes": [{ "index": 0, "start": 0.0, "end": 2.122, "text": "..." }], "narration": "narration.wav" }
```

### `assets/captions.json`

```json
[{ "word": "Why", "start": 0.0, "end": 0.22 }]
```

### `audio_pipeline/music_library/manifest.json`

```json
{ "tracks": [{ "file": "documentary/Hopeless - Jimena Contreras.mp3", "mood": "documentary",
  "upstream_mood": "sad", "bpm": null, "license": "...", "source": "...", "title": "...", "artist": "..." }] }
```

### `assets/attribution.json`

```json
{ "music": { "...manifest track..." }, "sfx": [], "media": [{ "source": "wikimedia", "title": "...",
  "author": "...", "license": "...", "url": "...", "page_url": "...", "file": "..." }] }
```

### `output/<slug>.meta.json`

```json
{ "slug": "concept-001", "file": "output/concept-001.mp4", "title": "...", "description": "...",
  "tags": [], "platform_targets": ["youtube"], "visibility": "unlisted", "music_attribution": "Music: ..." }
```

### `analyzer/blueprints/<style>.json`

The `style_blueprint.json` schema from BUILD_SPEC Module A, plus measured `median_shot_sec`, `words_per_minute`, `sources` and `created`. See `analyzer/blueprints/concept_case_study_short.json`.

### `scheduler/schedule.yaml`

```yaml
defaults:
  timezone: "Asia/Kolkata"
  youtube_visibility: "unlisted"
  instagram_daily_cap: 2
  youtube_daily_cap: 5
  tiktok_daily_cap: 3
  account: "main"
jobs:
  - id: "concept-001"
    type: "generate_and_upload"   # generate_only | upload_only | generate_and_upload
    script_or_prompt: "projects/concept-001/script.json"
    style: "concept_explainer"
    aspect_ratio: "9:16"
    music_mood: "documentary"
    generate_at: "2026-11-23T08:00:00+05:30"
    upload_at: "2026-11-23T18:00:00+05:30"
    platforms: ["youtube", "instagram"]
    # visibility: "public"        # optional per-job override
    # meta: "output/x.meta.json"  # required for upload_only
```

### `scheduler/state.sqlite`

| Table | Columns |
| --- | --- |
| `jobs` | id, type, spec (JSON), gen_status (pending/running/done/failed/skipped), gen_attempts, gen_next_at, meta_path, last_error, updated_at |
| `uploads` | job_id, platform, status, attempts, next_at, done_at, local_day, last_error |
| `events` | at, job_id, kind, detail (audit log) |

## Caching

| What | Key | Location |
| --- | --- | --- |
| TTS per scene | sha256(engine, voice, rate, text) | `audio_pipeline/cache/*.wav` |
| Music loudness | sha256(file bytes) | `audio_pipeline/cache/music_lufs.json` |
| Archive media | sha256(url) | `media_pipeline/cache/` |

Re-rendering after a visual-only change reuses every narration clip, so it does not call Edge-TTS again.
