"""explainroo engine: Rough.js hand-drawn explainers with 1,800 Lucide icons.

explainroo owns its own narration timing (it voices `script.md` with Kokoro and draws
`scenes.js` on cue words). We render with its music turned off, then lay our mood
music under its narration with the same sidechain ducking + -14 LUFS normalization.

script.json:
    "style": "explainroo",
    "explainroo": {"project": "projects/<slug>/explainroo"}   # holds video.json, script.md, scenes.js

If the folder has no video.json, it is created with `explainroo init`. Write script.md and
scenes.js by following `node engines/explainroo/bin/explainroo.js docs`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from audio_pipeline.mix_music_and_sfx import MUSIC_LIBRARY, mix
from common import ROOT, media_duration, read_json, run, which
from engines import mux_audio

SIZES = {"9:16": "shorts", "16:9": "youtube", "1:1": "square"}
CLI = ROOT / "engines" / "explainroo" / "bin" / "explainroo.js"


def _cli(*args: str, cwd: Path) -> None:
    if not CLI.exists():
        raise FileNotFoundError("engines/explainroo missing. Run `python scripts/bootstrap.py`.")
    run([which("node"), str(CLI), *args], cwd=cwd)


def render(script: dict[str, Any], run_dir: Path, out_mp4: Path, aspect: str) -> Path:
    cfg = script.get("explainroo") or {}
    project = ROOT / cfg.get("project", str(run_dir.parent / "explainroo"))
    project.mkdir(parents=True, exist_ok=True)
    video_json = project / "video.json"
    if not video_json.exists():
        _cli("init", str(project), cwd=ROOT)
    conf = read_json(video_json)
    conf.update({"size": SIZES[aspect], "music": None, "title": script.get("title", conf.get("title", ""))})
    video_json.write_text(json.dumps({k: v for k, v in conf.items() if v is not None}, indent=2), encoding="utf-8")

    # 8 parallel workers (explainroo's default) each pipe frames into FFmpeg; on a 16 GB laptop
    # under load those FFmpeg processes die ("write EOF"). Two workers is reliable and still fast.
    args = ["render", str(project), "--workers", str(cfg.get("workers", 2)), "--quality", cfg.get("quality", "fast")]
    if not cfg.get("watermark", False):
        args.append("--no-watermark")
    _cli(*args, cwd=ROOT)
    rendered = max((project / "out").glob("*.mp4"), key=lambda p: p.stat().st_mtime)  # never build/ segments

    narration = run_dir / "explainroo_narration.wav"
    run([which("ffmpeg"), "-y", "-i", str(rendered), "-vn", "-ac", "1", "-ar", "48000", str(narration)])
    track = read_json(run_dir / "attribution.json")["music"]
    master = run_dir / "mixed_master.wav"
    mix(narration, MUSIC_LIBRARY / track["file"], master)
    return mux_audio(rendered, master, out_mp4, media_duration(master))
