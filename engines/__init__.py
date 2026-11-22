"""Non-Remotion engines. Each module exposes `render(script, run_dir, out_mp4, aspect) -> Path`.

The audio pipeline has already produced `run_dir/mixed_master.wav`, `captions.json` and
`timing.json` (the master clock). Engines that render silent video get that audio muxed on
with `mux_audio`, which also burns the word captions, so every engine ends with the same
captioned H.264 yuv420p + AAC output.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from common import read_json, run, which

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


def _ass_time(t: float) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_ass(words: list[dict], path: Path, w: int, h: int, aspect: str = "9:16") -> Path:
    """Phrase captions (3 words) with a thick outline, kept inside the safe zone for the aspect."""
    portrait = aspect == "9:16"
    margin_v = int(h * (0.24 if portrait else 0.08))
    margin_l = int(w * 0.06)
    margin_r = int(w * (0.15 if portrait else 0.06))
    size = 78 if portrait else 64
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Bold",
        f"Style: Default,Arial,{size},&H00FFFFFF,&H00000000,1,5,0,2,{margin_l},{margin_r},{margin_v},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Text",
    ]  # fmt: skip
    for i in range(0, len(words), 3):
        chunk = words[i : i + 3]
        text = " ".join(x["word"] for x in chunk).replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 0,{_ass_time(chunk[0]['start'])},{_ass_time(chunk[-1]['end'])},Default,{text}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def subtitles_filter(ass: Path) -> str:
    """FFmpeg `subtitles=` argument with Windows drive colons escaped."""
    arg = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    return f"subtitles='{arg}'"


def mux_audio(
    video: Path,
    audio: Path,
    out_mp4: Path,
    duration: float | None = None,
    captions: Path | None = None,
    aspect: str = "9:16",
) -> Path:
    """Loop/trim `video` to the audio length, burn captions, encode H.264 yuv420p + AAC (faststart)."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [which("ffmpeg"), "-y", "-stream_loop", "-1", "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"]
    vf = []
    if captions and captions.exists():
        w, h = DIMENSIONS[aspect]
        ass = write_ass(read_json(captions), out_mp4.with_suffix(".ass"), w, h, aspect)
        vf.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,{subtitles_filter(ass)}")
    # Engines that render from JPEG/PNG frames emit full-range yuvj420p; force standard tv-range yuv420p.
    vf.append("scale=out_range=tv,format=yuv420p")
    cmd += ["-vf", ",".join(vf), "-color_range", "tv", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]  # fmt: skip
    cmd += ["-t", f"{duration:.3f}"] if duration else ["-shortest"]
    run([*cmd, str(out_mp4)])
    out_mp4.with_suffix(".ass").unlink(missing_ok=True)
    return out_mp4


def fit_filter(aspect: str) -> str:
    """Scale + pad any input to the target canvas."""
    w, h = DIMENSIONS[aspect]
    return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1"
