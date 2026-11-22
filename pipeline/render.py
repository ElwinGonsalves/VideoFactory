"""Remotion rendering: props assembly, batched stills (QA + cover), final H.264/AAC render, validation."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from common import ASSETS, STUDIO, ffprobe_json, read_json, run, run_stream, safe_replace, which, write_json

FPS = 30
QA_POINTS = {"hook": 0.05, "early": 0.25, "mid": 0.55, "outro": 0.92}
TRANSITIONS = ("hard_cut", "fade", "whip_pan", "paper_slide", "pen_draw")


def npx() -> str:
    return which("npx.cmd" if os.name == "nt" else "npx")


def cover_text_for(script: dict[str, Any]) -> str:
    """Frame-0 hook text: explicit cover_text, else the first scene heading, else the title (max 5 words)."""
    if "cover_text" in script:
        text = script["cover_text"] or ""
    else:
        first = (script.get("scenes") or [{}])[0].get("visual", {})
        text = first.get("heading") or script.get("title", "")
    text = text.replace("#shorts", "").strip()
    words = text.split()
    return " ".join(words[:5])


def build_props(
    script: dict[str, Any],
    timing: dict[str, Any],
    captions: list[dict[str, Any]],
    *,
    aspect_ratio: str,
    caption_style: str,
    theme: str | None,
    asset_prefix: str,
    brand_name: str = "default",
    show_safe_zones: bool = False,
    transition: str = "fade",
) -> dict[str, Any]:
    """Merge script visuals with audio timing. Audio duration is the master clock."""
    script_scenes = script.get("scenes") or [{"visual": {"type": "headline", "heading": script.get("title", "")}}]
    scenes = []
    for sc, t in zip(script_scenes, timing["scenes"], strict=False):
        visual = sc.get("visual") or {"type": "headline", "heading": sc.get("narration", "")}
        scenes.append({"start": t["start"], "end": t["end"], "visual": visual})
    duration = float(timing["total_duration_sec"]) + 0.5  # matches music tail in the mixer
    if scenes:
        scenes[-1]["end"] = duration
    transition = script.get("transition", transition)
    props: dict[str, Any] = {
        "aspectRatio": aspect_ratio,
        "title": script.get("title", "Untitled"),
        "durationSec": round(duration, 3),
        "scenes": scenes,
        "captions": captions,
        "captionStyle": caption_style,
        "brand": read_json(STUDIO / "brands" / brand_name / "brand.json"),
        "audioSrc": f"{asset_prefix}/mixed_master.wav",
        "showSafeZones": show_safe_zones,
        "coverText": cover_text_for(script),
        "transition": transition if transition in TRANSITIONS else "fade",
    }
    if theme:
        props["theme"] = theme
    return props


def stage_assets(run_dir: Path, slug: str) -> str:
    """Copy per-run audio into studio/public/assets/<slug>/ and return the staticFile prefix."""
    dest = ASSETS / slug
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("mixed_master.wav", "captions.json", "attribution.json"):
        if (run_dir / name).exists():
            shutil.copy2(run_dir / name, dest / name)
    media = run_dir / "media"
    if media.exists():
        shutil.copytree(media, dest / "media", dirs_exist_ok=True)
    return f"assets/{slug}"


def render_stills_batch(jobs: list[dict[str, Any]], work_dir: Path) -> list[Path]:
    """Render many stills with one bundle + one browser (studio/scripts/stills.mjs)."""
    # Node runs from studio/, so every path handed to it must be absolute.
    jobs_file = (work_dir / "_stills_jobs.json").resolve()
    write_json(
        jobs_file,
        [{**j, "props": str(Path(j["props"]).resolve()), "output": str(Path(j["output"]).resolve())} for j in jobs],
    )
    try:
        run_stream([which("node"), "scripts/stills.mjs", str(jobs_file)], cwd=STUDIO, quiet=True)
    finally:
        jobs_file.unlink(missing_ok=True)
    return [Path(j["output"]) for j in jobs]


def qa_frames(duration_sec: float) -> dict[str, int]:
    total = max(1, int(duration_sec * FPS))
    return {name: min(total - 1, int(total * pct)) for name, pct in QA_POINTS.items()}


def render_qa(composition: str, props_file: Path, duration_sec: float, out_dir: Path) -> dict[str, Any]:
    """4 QA stills + the frame-0 cover, each with a background-only twin for the pixel check."""
    from pipeline import qa

    out_dir.mkdir(parents=True, exist_ok=True)
    frames = {"cover": 0, **qa_frames(duration_sec)}
    jobs = []
    for name, frame in frames.items():
        jobs.append(
            {"composition": composition, "props": props_file, "frame": frame, "output": out_dir / f"{name}.png"}
        )
        jobs.append(
            {
                "composition": composition,
                "props": props_file,
                "frame": frame,
                "output": out_dir / f"_{name}.bg.png",
                "override": {"qaHideContent": True},
            }
        )
    render_stills_batch(jobs, out_dir)
    props = read_json(props_file)
    report = qa.check_frames(out_dir, frames, props["aspectRatio"])
    write_json(out_dir / "report.json", report)
    return report


def render_video(composition: str, props_file: Path, out_mp4: Path, concurrency: str | None = None) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "render",
        "src/index.ts",
        composition,
        str(out_mp4),
        f"--props={props_file}",
        "--codec=h264",
        "--pixel-format=yuv420p",
        "--audio-codec=aac",
        # Without this, JPEG frames yield full-range yuvj420p; bt709 gives standard tv-range yuv420p.
        "--color-space=bt709",
    ]
    if concurrency:
        args.append(f"--concurrency={concurrency}")
    try:
        run_stream([npx(), "remotion", *args], cwd=STUDIO)
    except RuntimeError as exc:
        # Under memory pressure Chrome can miss Remotion's 30 s startup window. One retry with
        # fewer parallel tabs fixes it; any other failure is re-raised unchanged.
        if "setting up the headless browser" not in str(exc) or concurrency:
            raise
        print("      browser startup timed out; retrying with --concurrency=2", flush=True)
        run_stream([npx(), "remotion", *args, "--concurrency=2"], cwd=STUDIO)
    faststart(out_mp4)
    return out_mp4


def faststart(mp4: Path) -> None:
    """Move the moov atom to the front so uploads/previews start instantly."""
    tmp = mp4.with_suffix(".faststart.mp4")
    run([which("ffmpeg"), "-y", "-i", str(mp4), "-c", "copy", "-movflags", "+faststart", str(tmp)])
    safe_replace(tmp, mp4)


def validate_mp4(mp4: Path) -> dict[str, Any]:
    """Assert the file is H.264 yuv420p video + AAC audio. Returns a short report."""
    info = ffprobe_json(mp4)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    problems = []
    if not v or v.get("codec_name") != "h264":
        problems.append(f"video codec is {v and v.get('codec_name')}, expected h264")
    if v and v.get("pix_fmt") != "yuv420p":
        problems.append(f"pixel format is {v.get('pix_fmt')}, expected yuv420p")
    if not a or a.get("codec_name") != "aac":
        problems.append(f"audio codec is {a and a.get('codec_name')}, expected aac")
    if problems:
        raise RuntimeError(f"{mp4} failed validation: " + "; ".join(problems))
    return {
        "file": str(mp4),
        "video": f"{v['codec_name']} {v['width']}x{v['height']} {v['pix_fmt']}",
        "audio": f"{a['codec_name']} {a.get('sample_rate')} Hz",
        "duration_sec": round(float(info["format"]["duration"]), 2),
    }


def write_props(props: dict[str, Any], path: Path) -> Path:
    write_json(path, props)
    return path
