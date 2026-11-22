"""handanim engine: hand-drawn whiteboard scenes in Python.

script.json:
    "style": "handanim",
    "handanim": {"file": "engines/handanim_scenes/whiteboard_scene.py"}   # optional

The scene module must define `build(script, timing, width, height) -> handanim.Scene`.
The default module draws each scene's heading/text on cue with the narration timing.
handanim also ships an MCP server (`aianim` / `voiceanim`) for direct agent use; see docs/ADDING_STYLES.md.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from common import ROOT, media_duration, read_json
from engines import DIMENSIONS, mux_audio


def _load(path: Path):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render(script: dict[str, Any], run_dir: Path, out_mp4: Path, aspect: str) -> Path:
    cfg = script.get("handanim") or {}
    module = _load(ROOT / cfg.get("file", "engines/handanim_scenes/whiteboard_scene.py"))
    w, h = DIMENSIONS[aspect]
    timing = read_json(run_dir / "timing.json")
    scene = module.build(script, timing, w, h)
    silent = run_dir / "handanim_silent.mp4"
    scene.render(str(silent), max_length=timing["total_duration_sec"] + 0.5)
    audio = run_dir / "mixed_master.wav"
    return mux_audio(silent, audio, out_mp4, media_duration(audio), captions=run_dir / "captions.json", aspect=aspect)
