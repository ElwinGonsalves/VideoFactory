# Adding styles

There are four ways to get a new look, from least to most work.

## 1. Re-skin with props (no code)

Pick another composition with `style`, change `caption_style`, or switch brand.

| Want | Set in `script.json` |
| --- | --- |
| Vox paper look | `"style": "vox_documentary"` |
| Whiteboard look | `"style": "whiteboard"` |
| Clean light look | `"style": "ui_demo"` (UniversalCustom + minimal theme) |
| Boxed captions | `"caption_style": "phrase_box"` |
| Landscape YouTube | `"aspect_ratio": "16:9"` or `--aspect 16:9` |

New brand: copy `studio/brands/default/` to `studio/brands/<name>/`, edit colors and fonts, and pass `brand_name` in `pipeline/render.build_props` (or add a `"brand"` field to the script and wire it through).

Transitions (`"transition"` in the script, or the blueprint's `pacing.transition_style`): `hard_cut`, `fade`, `whip_pan` (motion blur), `paper_slide`, `pen_draw` (left-to-right wipe). Sound effects follow the look automatically (`"sfx": "auto"`): concept → subtle whoosh + pop, vox → paper flip + click, whiteboard → pen scratch + pop; a blueprint's `audio_profile.sfx_cues` overrides them. Available sounds: `whoosh`, `subtle_whoosh`, `pop`, `click`, `paper_flip`, `pen_scratch`, `riser`, `ding` (synthesized locally by `audio_pipeline/sfx.py`).

Editorial maps: `{"type": "map", "heading": "...", "countries": ["USA", "IND"], "label": "..."}`. Up to 4 countries zoom in; more show the world with each country filling in turn.

## 2. Learn a style from a reference video

The UI **Ideas** tab does all of this: paste links, **Analyze + propose ideas**, tick ideas, **Approve selected**. With a Gemini key, the model also reads the contact sheets to fill the blueprint's visual fields (what the first 3 seconds show, on-screen text, style notes) and writes the 5 ideas and, on approval, full scripts. Terminal version:

```powershell
.venv\Scripts\python analyzer\analyze_reference.py analyze "https://www.youtube.com/shorts/XXXX" --style my_style --mode condensed
```

This writes:

- `analyzer/work/<date>-my_style/ref1/frames/*.jpg`: 30-frame contact sheets plus `first-3s.jpg`
- `.../transcript.json`: Whisper segments with word times
- `.../scenes.csv`: PySceneDetect shot list
- `analyzer/blueprints/my_style.json`: measured pacing, aspect, words per minute; `TODO` fields for judgement calls
- `.../IDEAS.md`: the 5-idea approval sheet

With an LLM configured, `analyze` continues automatically (`--no-ideas` to skip):

1. Vision pass over the contact sheets fills the blueprint's `TODO` fields.
2. Five ideas are written to `ideas.json` and `IDEAS.md`: Title, Hook, Core Concept/Angle, Case Study/Example, Engine Selection, Music Mood.
3. It stops and waits for you to choose.
4. `analyze_reference.py approve --work analyzer/work/<run> --ideas 2,4` writes a complete `projects/my_style-idea2/script.json` per idea (or a scaffold with `--scaffold-only` / without an LLM), marked `"approval": "approved"`.

Without an LLM, Kiro can do steps 1-2 by reading the sheets and filling `IDEAS.md`.

`make_video.py` refuses any script that names a blueprint without that approval.

Modes: `hook` (first 20 s, 1 sheet, good for many competitors), `condensed` (default), `forensic` (1 fps). Runs over 15 sheets stop and ask first; `--yes` overrides.

## 3. Add a scene type or composition (TypeScript)

New visual type, e.g. a timeline:

1. Add `'timeline'` to `Visual['type']` in `studio/src/types.ts`.
2. Add a component in `studio/src/components/SceneView.tsx` and a `case 'timeline'` in `SceneView`. Reuse `Card`, `Highlight`, `DrawPath` and `useSpring` from `primitives.tsx` so it works in every theme.
3. `cd studio; npx tsc --noEmit`, then render a project that uses it and check the QA stills with `--safe-zones`.

New theme or composition:

1. Add a theme id to `ThemeId` and a branch in `studio/src/theme.ts`.
2. Copy `studio/src/compositions/VoxEditorial.tsx`, rename it and set `themeId`.
3. Register it in the `compositions` map in `studio/src/Root.tsx`.
4. Add a route in `pipeline/router.py`: `"my_style": Route("remotion", "MyComposition", "phrase_box")`.

## 4. Plug in another engine or skill

Installed skill packs live in `.agent/skills/` (refresh with `scripts/install_skills.py`):

| Pack | Use for |
| --- | --- |
| `skills/` (remotion-dev) | Remotion guardrails: frame math, audio sync, layout |
| `explainer-video-skills`, `tiktok-video-skills` (iart-ai) | Kinetic type, diagrams, Shorts safe zones, render-screenshot-inspect QA loop |
| `creator-generalist`, `motion-graphics-skills` | Vox editorial cards, highlighters, maps |
| `web-media-getter-skill` | More keyless sources (`webmedia.py --source nokey`: Openverse, LoC) |
| `watchvideo` | The reference-analysis method `analyze_reference.py` follows |

To add a skill from [awesome-claude-video-skills](https://github.com/zhuyansen/awesome-claude-video-skills): check it needs no paid API, add its `owner/repo` to `REPOS` in `scripts/install_skills.py`, re-run the script, and read its `SKILL.md`. Do **not** add `vox-director`, `vox-explainer-skill` or `vox-ai-motion-graphics-generator`; they need paid APIs.

### Engine contract

A new engine is a module in `engines/` with:

```python
def render(script: dict, run_dir: Path, out_mp4: Path, aspect: str) -> Path: ...
```

When it runs, `run_dir` already holds `narration.wav`, `mixed_master.wav`, `captions.json` and `timing.json`. Render silent video sized to `timing["total_duration_sec"]`, then call `engines.mux_audio(video, run_dir / "mixed_master.wav", out_mp4, duration)`. Register it in `engines/__init__.py::_MODULES` and add a route in `pipeline/router.py`.

Existing engines and how to drive them:

| Engine | Style | Notes |
| --- | --- | --- |
| Manim | `math_science` | `"manim": {"file", "scene"}`. Scenes read `VF_DURATION`, `VF_TITLE` env vars. Example: `engines/manim_scenes/example_scene.py` |
| handanim | `handanim` | `"handanim": {"file"}` module with `build(script, timing, w, h) -> Scene`. Its MCP server (`aianim`, `voiceanim`) can be added to `.kiro/settings/mcp.json` |
| explainroo | `explainroo` | Folder with `video.json`, `script.md`, `scenes.js`; read `node engines/explainroo/bin/explainroo.js docs`. It voices its own narration; our ducked music goes underneath |
| Clipper | `clip_repurpose` | `"clip": {"source", "min_sec", "max_sec"}`. Densest speech window, cut-snapped, centre-cropped, captions burned in. The full Clipsmith app (Ollama moment picking): `engines/clipper/run.bat` |
| OpenMontage | `openmontage` | Scenes with `media_query` get keyless archive images, rendered through UniversalCustom. Pipeline definitions are in `engines/openmontage/pipeline_defs/` |
| Long tail | any | [lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) has 99 code-rendered styles to port as themes |

## Music moods

Add tracks to `audio_pipeline/music_library/<mood>/` and a manifest entry with `file`, `mood`, `license`, `source`. Free sources: YouTube Audio Library, Free Music Archive (CC licenses, see [mdeff/fma](https://github.com/mdeff/fma)), Mixkit, or a local [ACE-Step](https://github.com/ace-step/ACE-Step-1.5) instrumental. When a mood has no local track, the mixer tries an Archive.org public-domain search automatically. A new mood name also has to be added to `MOODS` in `audio_pipeline/mix_music_and_sfx.py`.
