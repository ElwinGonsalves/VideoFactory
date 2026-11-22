# Universal Video Factory — Kiro Steering Rules

## Core Constraints
- NEVER require paid APIs or Pexels API.
- Audio duration is the master clock: always run `audio_pipeline/make_voice_and_subs.py` and `audio_pipeline/mix_music_and_sfx.py` BEFORE generating or rendering video scenes. (`make_video.py` does this in order.)
- Support requested aspect ratio: default `9:16` (1080x1920 @ 30fps) for Shorts/Reels/TikTok, or `16:9` (1920x1080) / `1:1` (1080x1080) when requested.
- Enforce Shorts/Reels UI safe zones on `9:16` videos: keep all captions and key visuals above the bottom 22% and left of the right 15%.
- Before final render, export 4 key still frames (hook, early, mid, outro), visually inspect them for text clipping, overlap, or safe-zone violations, fix issues, then render H.264 (`yuv420p`, `faststart`).
- Keep code modular, type-checked (`ruff` + `tsc --noEmit`), and never commit cookies, `.env` secrets, or rendered `.mp4` binaries to Git.

## Mode 1: Prompt / Script -> Any Video
1. Classify the request into the best engine via the Universal Style Router (`pipeline/router.py`):
   - `concept_explainer` / `case_study` / `kinetic_type` / `ui_demo` -> Remotion (`studio/`) + `iart-ai/explainer-video-skills`
   - `vox_documentary` / `editorial_map` / `news_breakdown` -> Remotion + `codepawl/creator-generalist` + `charlie947/motion-graphics-skills` + keyless Wikimedia/Archive.org media
   - `whiteboard` / `hand_drawn` / `sketch` -> `engines/explainroo/` (Rough.js) or `handanim` (Python/MCP) or Remotion SVG draw-on
   - `math_science` / `algorithm` -> `ManimCommunity/manim`
   - `clip_repurpose` -> `engines/clipper/` (Clipsmith / PySceneDetect)
   - `hybrid_or_custom` -> `OpenMontage` production plan + Remotion custom composition
2. Default narrative structure for Concept + Case Study Shorts (45–58s):
   - Beat 1 (0–3s): Visual + verbal pattern-interrupt hook.
   - Beat 2 (3–20s): Core concept visual/diagram.
   - Beat 3 (20–45s): Concrete case study with real figures or timeline.
   - Beat 4 (45–55s): 1-sentence takeaway + seamless loop back to Beat 1.
   (For any other requested video type, adapt structure to the user's prompt or `style_blueprint.json`.)
3. Write `projects/<slug>/script.json` (schema in `docs/ARCHITECTURE.md`), then run `python make_video.py projects/<slug>`.
4. Read the 4 PNGs in `projects/<slug>/qa/`. If anything clips or crosses the red safe zone (`--safe-zones`), fix the script or component and re-render.

## Mode 2: Reference Video(s) -> Feature Extraction -> Idea Approval -> Generation
1. Run `analyzer/analyze_reference.py analyze <url-or-file> --style <name>` (`watchvideo` + `PySceneDetect`).
2. Inspect the generated 30-frame contact sheets, Whisper transcript, and scene-cut CSV to produce `analyzer/blueprints/<style_name>.json` (fill every `TODO`).
3. Present 5 tailored video ideas mapped to that blueprint (each with Title, Hook, Core Concept/Angle, Case Study/Example, Engine Selection, and Music Mood) in `analyzer/work/<run>/IDEAS.md`.
4. STOP and wait for explicit user approval of which idea(s) to generate before running audio, music, or rendering scripts. Record it with `analyze_reference.py approve --work <run> --ideas <n,...>`.

## Debugging
- Health check: `python scripts/doctor.py`. End-to-end check: `python scripts/smoke_test.py`.
- Known fixes live in `docs/DEBUGGING.md`; add new ones there when you solve something.
