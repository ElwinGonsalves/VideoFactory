"""Local sound-effect library, synthesized with FFmpeg (no downloads, no licensing questions).

`ensure_library()` writes audio_pipeline/sfx_library/<name>.wav once. `auto_cues()` turns a
blueprint/style's `sfx_cues` into timed cues at scene boundaries, so `mix_music_and_sfx.mix`
can lay them over the ducked bed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from common import MUSIC_LIBRARY, run, which

SFX_DIR = MUSIC_LIBRARY.parent / "sfx_library"

# name -> (lavfi source, extra filters). All mono 48 kHz, peaks around -6 dBFS.
RECIPES: dict[str, tuple[str, str]] = {
    "whoosh": (
        "anoisesrc=d=0.55:c=pink:a=0.9:r=48000",
        "highpass=f=400,lowpass=f=5000,afade=t=in:d=0.3,afade=t=out:st=0.3:d=0.25",
    ),
    "subtle_whoosh": (
        "anoisesrc=d=0.4:c=pink:a=0.5:r=48000",
        "highpass=f=600,lowpass=f=4000,afade=t=in:d=0.2,afade=t=out:st=0.2:d=0.2",
    ),
    "pop": ("aevalsrc='0.8*sin(2*PI*(500+3500*exp(-45*t))*t)*exp(-28*t)':d=0.18:s=48000", ""),
    "click": ("aevalsrc='0.7*sin(2*PI*2400*t)*exp(-120*t)':d=0.05:s=48000", ""),
    "paper_flip": (
        "anoisesrc=d=0.28:c=white:a=0.6:r=48000",
        "bandpass=f=3500:w=2500,tremolo=f=22:d=0.9,afade=t=in:d=0.04,afade=t=out:st=0.12:d=0.16",
    ),
    "pen_scratch": (
        "anoisesrc=d=0.5:c=brown:a=0.7:r=48000",
        "highpass=f=1500,tremolo=f=35:d=0.8,afade=t=in:d=0.05,afade=t=out:st=0.35:d=0.15",
    ),
    "riser": ("aevalsrc='0.35*sin(2*PI*(180*t+260*t*t))':d=1.2:s=48000", "afade=t=in:d=0.9,afade=t=out:st=1.05:d=0.15"),
    "ding": ("aevalsrc='0.5*sin(2*PI*1320*t)*exp(-6*t)+0.2*sin(2*PI*2640*t)*exp(-9*t)':d=0.9:s=48000", ""),
}

# What each blueprint/style uses at scene changes and on "reveal" visuals.
STYLE_CUES: dict[str, dict[str, str]] = {
    "concept": {"transition": "subtle_whoosh", "reveal": "pop"},
    "vox": {"transition": "paper_flip", "reveal": "click"},
    "whiteboard": {"transition": "pen_scratch", "reveal": "pop"},
    "minimal": {"transition": "subtle_whoosh", "reveal": "click"},
}
REVEAL_VISUALS = {"stat", "chart", "map"}


def ensure_library() -> dict[str, Path]:
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, (src, filt) in RECIPES.items():
        dest = SFX_DIR / f"{name}.wav"
        if not dest.exists():
            cmd = [which("ffmpeg"), "-y", "-hide_banner", "-f", "lavfi", "-i", src]
            if filt:
                cmd += ["-af", filt]
            run([*cmd, "-ac", "1", "-ar", "48000", str(dest)])
        out[name] = dest
    return out


def auto_cues(
    timing: dict[str, Any],
    scenes: list[dict[str, Any]],
    theme: str = "concept",
    blueprint_cues: list[str] | None = None,
    volume: float = 0.35,
) -> list[dict[str, Any]]:
    """One transition sound per scene change, plus a reveal sound on stat/chart/map scenes."""
    lib = ensure_library()
    cues = dict(STYLE_CUES.get(theme, STYLE_CUES["concept"]))
    if blueprint_cues:  # blueprint wins: first known cue = transitions, second = reveals
        known = [c for c in blueprint_cues if c in lib]
        if known:
            cues["transition"] = known[0]
            cues["reveal"] = known[1] if len(known) > 1 else cues["reveal"]
    out: list[dict[str, Any]] = []
    for i, t in enumerate(timing["scenes"]):
        if i > 0:
            out.append({"file": str(lib[cues["transition"]]), "at": max(0.0, t["start"] - 0.12), "volume": volume})
        visual = (scenes[i] if i < len(scenes) else {}).get("visual", {})
        if visual.get("type") in REVEAL_VISUALS:
            out.append({"file": str(lib[cues["reveal"]]), "at": t["start"] + 0.35, "volume": volume * 0.8})
    return out
