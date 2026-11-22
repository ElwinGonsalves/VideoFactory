"""Code-rendered thumbnails: a frame from the video (or an archive image) + hook text in brand style.

Outputs output/<slug>/<slug>.thumb.jpg (YouTube needs JPG/PNG under 2 MB). For 9:16 the frame-0 cover
already is the in-feed image; the thumbnail is still made for Reels covers and Library previews.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from common import ASSETS, STUDIO, paths, read_json, run, which, write_json
from pipeline.render import render_stills_batch


def pick_background(mp4: Path, script: dict[str, Any], run_dir: Path, slug: str) -> str | None:
    """Prefer an archive image used in the video; else grab a mid-video frame (past the cover)."""
    for scene in script.get("scenes", []):
        src = scene.get("visual", {}).get("src")
        if src and (STUDIO / "public" / src).exists():
            return src
    dest_dir = ASSETS / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    frame = dest_dir / "thumb_bg.jpg"
    if mp4.exists():
        info = run(
            [which("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)]
        ).stdout
        at = max(1.0, float(info.strip() or 2) * 0.55)
        run(
            [
                which("ffmpeg"),
                "-y",
                "-v",
                "error",
                "-ss",
                f"{at:.2f}",
                "-i",
                str(mp4),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(frame),
            ]
        )
        return f"assets/{slug}/thumb_bg.jpg"
    return None


def make_thumbnail(
    *,
    slug: str,
    text: str,
    aspect: str,
    script: dict[str, Any],
    run_dir: Path,
    subtext: str = "",
    brand_name: str = "default",
    theme: str | None = None,
) -> Path:
    mp4 = paths.video_path(slug)
    props = {
        "aspectRatio": aspect,
        "text": " ".join(text.split()[:5]) or slug,
        "subtext": subtext,
        "brand": read_json(STUDIO / "brands" / brand_name / "brand.json"),
        "theme": theme or "concept",
    }
    bg = pick_background(mp4, script, run_dir, slug)
    if bg:
        props["bgSrc"] = bg
        props["bgBlur"] = 18 if bg.endswith("thumb_bg.jpg") else 0  # video frames hold text; photos don't
    props_file = run_dir / "thumbnail_props.json"
    write_json(props_file, props)
    png = run_dir / "thumbnail.png"
    render_stills_batch([{"composition": "Thumbnail", "props": props_file, "frame": 0, "output": png}], run_dir)
    out = paths.thumb_path(slug)
    run([which("ffmpeg"), "-y", "-v", "error", "-i", str(png), "-q:v", "3", str(out)])
    qa_dir = run_dir.parent / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(png, qa_dir / "thumbnail.png")  # shown next to the QA frames in the Library tab
    return out
