"""Manim engine: render a scene class, then mux the ducked narration master.

script.json:
    "style": "math_science",
    "manim": {"file": "engines/manim_scenes/example_scene.py", "scene": "ConceptGraph"}

Scenes may read `VF_DURATION` (seconds) from the environment to match narration length.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import ROOT, media_duration, read_json
from engines import DIMENSIONS, mux_audio


def render(script: dict[str, Any], run_dir: Path, out_mp4: Path, aspect: str) -> Path:
    cfg = script.get("manim") or {}
    scene_file = ROOT / cfg.get("file", "engines/manim_scenes/example_scene.py")
    scene = cfg.get("scene", "ConceptGraph")
    w, h = DIMENSIONS[aspect]
    timing = read_json(run_dir / "timing.json")
    media = run_dir / "manim"
    env = {**os.environ, "VF_DURATION": str(timing["total_duration_sec"]), "VF_TITLE": script.get("title", "")}
    subprocess.run(
        [sys.executable, "-m", "manim", "render", "-r", f"{w},{h}", "--fps", "30", "--format", "mp4",
         "--media_dir", str(media), "-o", "scene.mp4", str(scene_file), scene],
        check=True, env=env, cwd=ROOT,
    )  # fmt: skip
    video = next(media.rglob("scene.mp4"))
    audio = run_dir / "mixed_master.wav"
    return mux_audio(video, audio, out_mp4, media_duration(audio))
