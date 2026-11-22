"""Non-Remotion engines. Each module exposes `render(script, run_dir, out_mp4, aspect) -> Path`.

The audio pipeline has already produced `run_dir/mixed_master.wav` and `timing.json`
(the master clock). Engines that render silent video get that audio muxed on with
`mux_audio`, so every engine ends with the same H.264 yuv420p + AAC output.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from common import run, which

DIMENSIONS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}

_MODULES = {
    "explainroo": "engines.explainroo_engine",
    "handanim": "engines.handanim_engine",
    "manim": "engines.manim_engine",
    "clipper": "engines.clipper_engine",
    "openmontage": "engines.openmontage_engine",
}


def dispatch(engine: str, *, script: dict[str, Any], run_dir: Path, out_mp4: Path, aspect: str) -> Path:
    if engine not in _MODULES:
        raise ValueError(f"Unknown engine '{engine}'. Known: {', '.join(_MODULES)}")
    module = importlib.import_module(_MODULES[engine])
    return module.render(script, run_dir, out_mp4, aspect)


def mux_audio(video: Path, audio: Path, out_mp4: Path, duration: float | None = None) -> Path:
    """Loop/trim `video` to the audio length and encode final H.264 yuv420p + AAC (faststart)."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [which("ffmpeg"), "-y", "-stream_loop", "-1", "-i", str(video), "-i", str(audio),
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]  # fmt: skip
    cmd += ["-t", f"{duration:.3f}"] if duration else ["-shortest"]
    run([*cmd, str(out_mp4)])
    return out_mp4


def fit_filter(aspect: str) -> str:
    """Scale + pad any input to the target canvas."""
    w, h = DIMENSIONS[aspect]
    return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1"
