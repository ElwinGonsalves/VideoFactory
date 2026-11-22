"""Reference video analyzer: watchvideo pipeline + PySceneDetect -> style_blueprint.json.

Follows the watchvideo skill's media pipeline (.agent/skills/watchvideo/skill/frameworks/
media-pipeline.md): yt-dlp at 720p, 30-frame contact sheets with ffmpeg, local Whisper
transcript (faster-whisper here), and a split of what the first 3 seconds SAY vs SHOW.
PySceneDetect adds measured shot pacing.

Subcommands:
    analyze  URL_OR_FILE [...] --style NAME [--mode hook|condensed|forensic]
             -> analyzer/work/<slug>/ (media, frames, transcript.json, scenes.csv, analysis.json)
             -> analyzer/blueprints/<NAME>.json (measured fields filled, judgement fields marked TODO)
             -> analyzer/work/<slug>/IDEAS.md (5-idea approval sheet for the agent to fill in)
    approve  --work analyzer/work/<slug> --ideas 1,3
             -> records the human decision and scaffolds projects/<slug>-idea<N>/script.json

Approval gate: nothing renders from a reference until `approve` has been run with the
user's explicit choice. make_video.py refuses projects whose `approval` is not "approved".
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import PROJECTS, ROOT, ffprobe_json, read_json, run, which, write_json  # noqa: E402

WORK = ROOT / "analyzer" / "work"
BLUEPRINTS = ROOT / "analyzer" / "blueprints"
SHEET_GATE = 15
MODES = {"hook": 1.0, "condensed": 3.0, "forensic": 1.0}
HOOK_SEC = 3.0


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "-", text.lower()).strip("-")[:60] or "reference"


def download(src: str, media_dir: Path) -> Path:
    media_dir.mkdir(parents=True, exist_ok=True)
    if not src.startswith(("http://", "https://")):
        dest = media_dir / Path(src).name
        shutil.copy2(src, dest)
        return dest
    run(
        [which("yt-dlp"), "-q", "--no-warnings", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
         "--merge-output-format", "mp4", "--write-auto-sub", "--write-sub", "--sub-lang", "en.*",
         "--convert-subs", "srt", "--socket-timeout", "30", "--retries", "3",
         "-o", str(media_dir / "%(id)s.%(ext)s"), src]
    )  # fmt: skip
    return max(media_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)


def probe(video: Path) -> dict[str, Any]:
    info = ffprobe_json(video)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    return {
        "width": int(v["width"]),
        "height": int(v["height"]),
        "duration": float(info["format"]["duration"]),
        "has_audio": has_audio,
    }


def aspect_of(w: int, h: int) -> str:
    r = w / h
    return "9:16" if r < 0.8 else "1:1" if r < 1.2 else "16:9"


def sheet_count(duration: float, mode: str) -> int:
    if mode == "hook":
        return 1
    return math.ceil((duration / MODES[mode]) / 30)


def contact_sheets(video: Path, frames_dir: Path, mode: str, vertical: bool) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    scale = "250" if vertical else "304"
    if mode == "hook":
        tile = "10x2" if vertical else "5x4"
        out = frames_dir / "hook.jpg"
        run([which("ffmpeg"), "-nostdin", "-loglevel", "error", "-y", "-t", "20", "-i", str(video),
             "-vf", f"fps=1,scale={scale}:-1,tile={tile}", "-frames:v", "1", "-q:v", "4", str(out)])  # fmt: skip
        return [out]
    tile = "10x3" if vertical else "6x5"
    fps = "1/3" if mode == "condensed" else "1"
    run([which("ffmpeg"), "-nostdin", "-loglevel", "error", "-y", "-i", str(video),
         "-vf", f"fps={fps},scale={scale}:-1,tile={tile}", "-q:v", "4", str(frames_dir / "sheet-%02d.jpg")])  # fmt: skip
    # Separate first-3-second sheet so the visual hook can be read on its own.
    run([which("ffmpeg"), "-nostdin", "-loglevel", "error", "-y", "-t", str(HOOK_SEC), "-i", str(video),
         "-vf", f"fps=3,scale={scale}:-1,tile=9x1", "-frames:v", "1", "-q:v", "4",
         str(frames_dir / "first-3s.jpg")])  # fmt: skip
    return sorted(frames_dir.glob("*.jpg"))


def transcribe(video: Path, audio_dir: Path, mode: str) -> list[dict[str, Any]]:
    from audio_pipeline.make_voice_and_subs import transcribe_words

    audio_dir.mkdir(parents=True, exist_ok=True)
    wav = audio_dir / "audio.wav"
    trim = ["-t", "20"] if mode == "hook" else []
    run([which("ffmpeg"), "-nostdin", "-loglevel", "error", "-y", *trim, "-i", str(video),
         "-vn", "-ac", "1", "-ar", "16000", str(wav)])  # fmt: skip
    words = transcribe_words(wav, "auto", "auto", None)
    # Group words into ~sentence segments for the beat sheet.
    segments: list[dict[str, Any]] = []
    cur: list[dict[str, Any]] = []
    for w in words:
        cur.append(w)
        if re.search(r"[.!?]$", w["word"]) or len(cur) >= 18:
            segments.append(_segment(cur))
            cur = []
    if cur:
        segments.append(_segment(cur))
    return segments


def _segment(words: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "start": words[0]["start"],
        "end": words[-1]["end"],
        "text": " ".join(w["word"] for w in words),
        "words": words,
    }


def detect_scenes(video: Path, csv_path: Path) -> list[float]:
    """Shot boundaries via PySceneDetect ContentDetector. Returns cut timestamps (seconds)."""
    from scenedetect import ContentDetector, detect

    scenes = detect(str(video), ContentDetector())
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["scene", "start_sec", "end_sec", "length_sec"])
        for i, (s, e) in enumerate(scenes, 1):
            wr.writerow(
                [i, f"{s.get_seconds():.3f}", f"{e.get_seconds():.3f}", f"{e.get_seconds() - s.get_seconds():.3f}"]
            )
    return [round(s.get_seconds(), 3) for s, _ in scenes[1:]]


def pacing(cuts: list[float], duration: float) -> dict[str, Any]:
    bounds = [0.0, *cuts, duration]
    shots = [b - a for a, b in zip(bounds, bounds[1:], strict=False) if b - a > 0.05]
    return {
        "scene_count": len(shots),
        "median_shot_sec": round(statistics.median(shots), 2) if shots else duration,
        "avg_shot_sec": round(statistics.fmean(shots), 2) if shots else duration,
        "cut_timestamps": cuts,
        "cuts_in_first_3s": sum(1 for c in cuts if c < HOOK_SEC),
    }


def words_per_minute(segments: list[dict[str, Any]], duration: float) -> float:
    n = sum(len(s["words"]) for s in segments)
    return round(n / max(duration, 1) * 60, 1)


def analyze_one(src: str, run_dir: Path, mode: str) -> dict[str, Any]:
    video = download(src, run_dir / "media")
    meta = probe(video)
    vertical = meta["height"] > meta["width"]
    sheets = contact_sheets(video, run_dir / "frames", mode, vertical)
    segments = transcribe(video, run_dir / "audio", mode) if meta["has_audio"] else []
    write_json(run_dir / "transcript.json", segments)
    cuts = detect_scenes(video, run_dir / "scenes.csv")
    hook_words = [w["word"] for s in segments for w in s["words"] if w["start"] < HOOK_SEC]
    return {
        "source": src,
        "video": str(video.relative_to(ROOT).as_posix()),
        **meta,
        "aspect_ratio": aspect_of(meta["width"], meta["height"]),
        "contact_sheets": [str(p.relative_to(ROOT).as_posix()) for p in sheets],
        "pacing": pacing(cuts, meta["duration"]),
        "words_per_minute": words_per_minute(segments, meta["duration"]),
        "hook_first_3s": {
            "said": " ".join(hook_words),
            "shown": "TODO: read frames/first-3s.jpg and describe what is on screen",
        },
    }


def draft_blueprint(style: str, analyses: list[dict[str, Any]]) -> dict[str, Any]:
    """Measured values are filled in; judgement calls are marked TODO for the agent."""
    a = analyses[0]
    avg_shot = statistics.fmean(x["pacing"]["avg_shot_sec"] for x in analyses)
    wpm = statistics.fmean(x["words_per_minute"] for x in analyses)
    fast = avg_shot < 2.5
    return {
        "style_name": style,
        "aspect_ratio": a["aspect_ratio"],
        "target_duration_sec": round(statistics.fmean(x["duration"] for x in analyses)),
        "recommended_engine": "remotion" if fast else "vox_remotion",
        "hook_first_3s": {
            "visual_pattern": a["hook_first_3s"]["shown"],
            "verbal_pattern": a["hook_first_3s"]["said"],
            "visual_vs_verbal_contrast": "TODO: compare frames/first-3s.jpg with the spoken hook",
        },
        "pacing": {
            "avg_shot_sec": round(avg_shot, 2),
            "median_shot_sec": a["pacing"]["median_shot_sec"],
            "words_per_minute": round(wpm, 1),
            "caption_style": "word_highlight" if fast else "minimal_editorial",
            "transition_style": "hard_cut" if fast else "paper_slide",
        },
        "audio_profile": {
            "narration_tone": "energetic_short" if wpm > 165 else "measured_vox",
            "music_mood": "upbeat" if fast else "documentary",
            "sfx_cues": ["subtle_whoosh", "pop"] if fast else ["paper_flip", "subtle_whoosh"],
        },
        "beat_template": [
            {"beat": "hook", "pct_duration": 0.06, "visual_role": "pattern interrupt"},
            {"beat": "concept", "pct_duration": 0.30, "visual_role": "diagram / kinetic text"},
            {"beat": "case_study", "pct_duration": 0.46, "visual_role": "real figures, timeline, archive media"},
            {"beat": "takeaway", "pct_duration": 0.18, "visual_role": "one-line takeaway + loop to hook"},
        ],
        "sources": [x["source"] for x in analyses],
        "created": date.today().isoformat(),
    }


IDEA_FIELDS = ["Title", "Hook", "Core Concept/Angle", "Case Study/Example", "Engine Selection", "Music Mood"]


def ideas_sheet(style: str, blueprint_path: Path) -> str:
    rows = "\n".join(f"| {i} | " + " | ".join("TODO" for _ in IDEA_FIELDS) + " |" for i in range(1, 6))
    return (
        f"# Video ideas for blueprint `{style}`\n\n"
        f"Blueprint: `{blueprint_path.relative_to(ROOT)}`\n\n"
        "The agent fills in five ideas mapped to this blueprint, then STOPS.\n"
        "Nothing is voiced, mixed or rendered until the user approves with:\n\n"
        "```\npython analyzer/analyze_reference.py approve --work <this folder> --ideas 1,3\n```\n\n"
        f"| # | {' | '.join(IDEA_FIELDS)} |\n|---|{'---|' * len(IDEA_FIELDS)}\n{rows}\n"
    )


def cmd_analyze(args: argparse.Namespace) -> int:
    style = slugify(args.style)
    run_dir = WORK / f"{date.today().isoformat()}-{style}"
    run_dir.mkdir(parents=True, exist_ok=True)

    if not args.yes:
        total = 0
        for src in args.sources:
            if src.startswith(("http://", "https://")):
                dur = float(run([which("yt-dlp"), "--no-warnings", "--print", "%(duration)s", src]).stdout.strip() or 0)
            else:
                dur = probe(Path(src))["duration"]
            total += sheet_count(dur, args.mode)
        if total > SHEET_GATE:
            print(f"{total} contact sheets in {args.mode} mode exceeds the {SHEET_GATE}-sheet gate.")
            print("Re-run with --mode hook or --mode condensed, or pass --yes to proceed.")
            return 2

    analyses = []
    for i, src in enumerate(args.sources, 1):
        sub = run_dir / f"ref{i}"
        print(f"[{i}/{len(args.sources)}] analyzing {src}")
        analyses.append(analyze_one(src, sub, args.mode))
    write_json(run_dir / "analysis.json", analyses)

    bp = draft_blueprint(style, analyses)
    bp_path = BLUEPRINTS / f"{style}.json"
    write_json(bp_path, bp)
    (run_dir / "IDEAS.md").write_text(ideas_sheet(style, bp_path), encoding="utf-8")
    write_json(
        run_dir / "approval.json",
        {"blueprint": str(bp_path.relative_to(ROOT).as_posix()), "status": "pending", "approved": []},
    )
    print(f"analysis : {run_dir}")
    print(f"blueprint: {bp_path}  (fill the TODO fields after reading the contact sheets)")
    print(f"ideas    : {run_dir / 'IDEAS.md'}  -> present 5 ideas, then wait for approval")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    work = Path(args.work)
    approval = read_json(work / "approval.json")
    bp = read_json(ROOT / approval["blueprint"])
    chosen = [int(x) for x in args.ideas.split(",") if x.strip()]
    from pipeline.router import BLUEPRINT_ENGINE_TO_STYLE

    created = []
    for n in chosen:
        slug = f"{bp['style_name']}-idea{n}"
        proj = PROJECTS / slug
        proj.mkdir(parents=True, exist_ok=True)
        script_path = proj / "script.json"
        if not script_path.exists():
            write_json(
                script_path,
                {
                    "title": f"TODO idea {n} title",
                    "description": "",
                    "tags": [],
                    "style": BLUEPRINT_ENGINE_TO_STYLE.get(bp["recommended_engine"], "concept_explainer"),
                    "aspect_ratio": bp["aspect_ratio"],
                    "music_mood": bp["audio_profile"]["music_mood"],
                    "caption_style": bp["pacing"]["caption_style"],
                    "blueprint": approval["blueprint"],
                    "approval": "approved",
                    "voice": {"engine": "edge-tts", "voice": "en-US-AndrewNeural", "rate": "+0%"},
                    "scenes": [
                        {"narration": "TODO", "visual": {"type": "headline", "heading": "TODO"}}
                        for _ in bp["beat_template"]
                    ],
                },
            )
        created.append(str(proj.relative_to(ROOT).as_posix()))
    approval.update({"status": "approved", "approved": chosen, "projects": created})
    write_json(work / "approval.json", approval)
    print(json.dumps(approval, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="Analyze reference video(s) into a blueprint")
    a.add_argument("sources", nargs="+", help="URLs or local video files")
    a.add_argument("--style", required=True, help="Blueprint name, e.g. vox_maps")
    a.add_argument("--mode", choices=list(MODES), default="condensed")
    a.add_argument("--yes", action="store_true", help="Skip the 15-sheet gate")
    a.set_defaults(func=cmd_analyze)
    b = sub.add_parser("approve", help="Record which ideas the user approved")
    b.add_argument("--work", required=True)
    b.add_argument("--ideas", required=True, help="Comma list, e.g. 1,3")
    b.set_defaults(func=cmd_approve)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
