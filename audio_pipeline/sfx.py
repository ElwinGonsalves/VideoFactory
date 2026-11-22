"""Local sound-effect library, synthesized with FFmpeg (no downloads, no licensing questions).

`ensure_library()` writes audio_pipeline/sfx_library/<name>.wav once. `auto_cues()` turns a
blueprint/style's `sfx_cues` into timed cues at scene boundaries, so `mix_music_and_sfx.mix`
can lay them over the ducked bed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common import MUSIC_LIBRARY, read_json, run, which, write_json

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
    "chalk_draw": (
        "anoisesrc=d=0.6:c=brown:a=0.8:r=48000",
        "highpass=f=900,lowpass=f=7000,tremolo=f=28:d=0.7,afade=t=in:d=0.06,afade=t=out:st=0.4:d=0.2",
    ),
    "riser": ("aevalsrc='0.35*sin(2*PI*(180*t+260*t*t))':d=1.2:s=48000", "afade=t=in:d=0.9,afade=t=out:st=1.05:d=0.15"),
    "ding": ("aevalsrc='0.5*sin(2*PI*1320*t)*exp(-6*t)+0.2*sin(2*PI*2640*t)*exp(-9*t)':d=0.9:s=48000", ""),
}

# What each blueprint/style uses at scene changes and on "reveal" visuals.
STYLE_CUES: dict[str, dict[str, str]] = {
    "concept": {"transition": "subtle_whoosh", "reveal": "pop"},
    "vox": {"transition": "paper_flip", "reveal": "pop"},
    "whiteboard": {"transition": "chalk_draw", "reveal": "pop"},
    "minimal": {"transition": "subtle_whoosh", "reveal": "click"},
}
REVEAL_VISUALS = {"stat", "counter", "chart", "map", "timeline", "cutout", "sketch", "diagram"}
RISER_BEATS = {"turning_point", "case_study", "punchline"}
REQUIRED = ("whoosh", "pop", "paper_flip", "chalk_draw", "riser")  # the manifest maps these to local clips
SFX_REL_DB = -12.0  # cue peak relative to the voice peak
MANIFEST = SFX_DIR / "manifest.json"
LICENSE = "CC0-1.0 (synthesized locally by audio_pipeline/sfx.py; no third-party audio)"


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
    write_manifest(out)
    return out


def peak_db(path: Path) -> float:
    """Peak level in dBFS (ffmpeg volumedetect)."""
    res = run([which("ffmpeg"), "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"])
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", res.stderr)
    return float(m.group(1)) if m else -6.0


def cue_volume(voice_peak_db: float | None, sfx_peak_db: float, rel_db: float = SFX_REL_DB) -> float:
    """Linear gain that puts a cue's peak rel_db (default -12 dB) below the voice peak."""
    voice = -3.0 if voice_peak_db is None else voice_peak_db
    return round(10 ** ((voice + rel_db - sfx_peak_db) / 20), 4)


def write_manifest(lib: dict[str, Path]) -> dict[str, Any]:
    """audio_pipeline/sfx_library/manifest.json: name -> local clip, license, measured peak."""
    old = {c["name"]: c for c in read_json(MANIFEST).get("sfx", [])} if MANIFEST.exists() else {}
    clips = []
    for name, path in sorted(lib.items()):
        prev = old.get(name)
        peak = prev["peak_db"] if prev and prev.get("peak_db") is not None else round(peak_db(path), 1)
        clips.append(
            {"name": name, "file": path.name, "license": LICENSE, "peak_db": peak, "required": name in REQUIRED}
        )
    data = {"relative_level_db": SFX_REL_DB, "sfx": clips}
    if not MANIFEST.exists() or read_json(MANIFEST) != data:
        write_json(MANIFEST, data)
    return data


def auto_cues(
    timing: dict[str, Any],
    scenes: list[dict[str, Any]],
    theme: str = "concept",
    blueprint_cues: list[str] | None = None,
    voice_peak_db: float | None = None,
) -> list[dict[str, Any]]:
    """One transition sound per scene change, plus a reveal sound on stat/chart/map scenes."""
    lib = ensure_library()
    cues = dict(STYLE_CUES.get(theme, STYLE_CUES["concept"]))
    if blueprint_cues:  # blueprint wins: first known cue = transitions, second = reveals
        known = [c for c in blueprint_cues if c in lib]
        if known:
            cues["transition"] = known[0]
            cues["reveal"] = known[1] if len(known) > 1 else cues["reveal"]
    peaks = {c["name"]: c["peak_db"] for c in read_json(MANIFEST)["sfx"]} if MANIFEST.exists() else {}

    def vol(name: str) -> float:
        return cue_volume(voice_peak_db, peaks.get(name, -6.0))

    out: list[dict[str, Any]] = []
    risered = False
    for i, t in enumerate(timing["scenes"]):
        scene = scenes[i] if i < len(scenes) else {}
        if i > 0:
            if scene.get("beat") in RISER_BEATS and not risered:
                risered = True
                out.append({"file": str(lib["riser"]), "at": max(0.0, t["start"] - 1.0), "volume": vol("riser")})
            at = max(0.0, t["start"] - 0.12)
            out.append({"file": str(lib[cues["transition"]]), "at": at, "volume": vol(cues["transition"])})
        if scene.get("visual", {}).get("type") in REVEAL_VISUALS:
            out.append({"file": str(lib[cues["reveal"]]), "at": t["start"] + 0.35, "volume": vol(cues["reveal"])})
    return out
