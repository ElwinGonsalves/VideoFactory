"""Remotion rendering: props assembly, batched stills (QA + cover), final H.264/AAC render, validation."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

from common import ASSETS, STUDIO, ffprobe_json, read_json, run, run_stream, safe_replace, which, write_json

FPS = 30
QA_POINTS = {"hook": 0.05, "early": 0.25, "mid": 0.55, "outro": 0.92}
TRANSITIONS = ("hard_cut", "fade", "whip_pan", "paper_slide", "pen_draw")


def _listing_has_reparse(root: Path) -> bool:
    """True when the directory listing flags any file as a reparse point (FILE_ATTRIBUTE_REPARSE_POINT).

    Read from the listing (os.scandir), like Node's readdir: opening the file with lstat can hide the
    flag on OneDrive cloud files while the bundler still sees it.
    """
    stack = [root]
    while stack:
        with os.scandir(stack.pop()) as it:
            for e in it:
                attrs = getattr(e.stat(follow_symlinks=False), "st_file_attributes", 0)
                if e.is_dir(follow_symlinks=False) and not attrs & 0x400:
                    stack.append(Path(e.path))
                elif attrs & 0x400:
                    return True
    return False


def public_dir() -> Path:
    """The folder Remotion bundles as `public/`.

    OneDrive turns synced files into cloud-file reparse points, which Remotion's bundler copies as
    symlinks and fails with EPERM. Inside OneDrive (or when any file under studio/public is one), mirror
    the folder as plain files to ~/.video-factory/remotion-public and render from there.
    """
    src = STUDIO / "public"
    if os.name != "nt":
        return src
    # Inside OneDrive the flag flips as Files-On-Demand frees space, so always mirror there.
    if "onedrive" not in str(src).lower() and not _listing_has_reparse(src):
        return src
    files = [p for p in src.rglob("*") if p.is_file()]
    # Not %LOCALAPPDATA%: Microsoft Store Python redirects writes there into its own package folder,
    # so Node would not see them. The home folder is neither virtualized nor synced by OneDrive.
    dest = Path.home() / ".video-factory" / "remotion-public"
    keep: set[Path] = set()
    for p in files:
        target = dest / p.relative_to(src)
        keep.add(target)
        st = p.stat()
        if target.exists() and target.stat().st_size == st.st_size and target.stat().st_mtime >= st.st_mtime:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        # Read the bytes ourselves: the Windows copy API (shutil.copyfile -> CopyFile2) copies a OneDrive
        # placeholder without its content and leaves a 0-byte file. Reading forces hydration.
        with p.open("rb") as fin, target.open("wb") as fout:
            shutil.copyfileobj(fin, fout, 1 << 20)
        if target.stat().st_size != st.st_size:
            raise RuntimeError(f"could not read {p} (OneDrive may still be downloading it); retry in a moment")
    for stale in [p for p in dest.rglob("*") if p.is_file() and p not in keep]:
        stale.unlink(missing_ok=True)
    return dest


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
    variant: str | None = None,
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
    if variant:
        props["variant"] = variant
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
        run_stream(
            [which("node"), "scripts/stills.mjs", str(jobs_file)],
            cwd=STUDIO,
            quiet=True,
            env={"VF_PUBLIC_DIR": str(public_dir())},
        )
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


def _render_target(out_mp4: Path) -> Path:
    """Where Remotion writes. Inside OneDrive, a scratch file outside it: Remotion finishes by renaming its
    in-progress file, and OneDrive's lock on fresh files makes that rename fail with EPERM."""
    if os.name == "nt" and "onedrive" in str(out_mp4.resolve()).lower():
        scratch = Path.home() / ".video-factory" / "render-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        return scratch / out_mp4.name
    return out_mp4


def _move_into_place(src: Path, dest: Path) -> None:
    """Move the finished file into output/, retrying while OneDrive or antivirus holds it."""
    for i in range(40):
        try:
            if dest.exists():
                dest.unlink()
            shutil.move(str(src), str(dest))
            return
        except PermissionError:
            if i == 39:
                raise
            time.sleep(0.25 * min(i + 1, 8))


def render_video(composition: str, props_file: Path, out_mp4: Path, concurrency: str | None = None) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    target = _render_target(out_mp4)
    args = [
        "render",
        "src/index.ts",
        composition,
        str(target),
        f"--props={props_file}",
        "--codec=h264",
        "--pixel-format=yuv420p",
        "--audio-codec=aac",
        # Without this, JPEG frames yield full-range yuvj420p; bt709 gives standard tv-range yuv420p.
        "--color-space=bt709",
        f"--public-dir={public_dir()}",
    ]
    if concurrency:
        args.append(f"--concurrency={concurrency}")
    try:
        run_stream([npx(), "remotion", *args], cwd=STUDIO)
    except RuntimeError as exc:
        # Under memory pressure Chrome can miss Remotion's 30 s startup window. One retry with
        # fewer parallel tabs fixes it; any other failure is re-raised unchanged.
        # The same pressure shows up as "takes a long time to load" when the page misses its props timeout.
        slow = ("setting up the headless browser", "takes a long time to load", "browser is not responding")
        if not any(s in str(exc) for s in slow) or concurrency:
            raise
        print(
            "      the render browser was slow to start; retrying with --concurrency=2 and a longer timeout", flush=True
        )
        run_stream([npx(), "remotion", *args, "--concurrency=2", "--timeout=120000"], cwd=STUDIO)
    if target != out_mp4:
        _move_into_place(target, out_mp4)
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
