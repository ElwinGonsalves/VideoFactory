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

from common import PROJECTS, ROOT, ffprobe_json, read_json, run, settings, which, write_json  # noqa: E402
from common.slugs import title_slug  # noqa: E402

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
    out_tpl = str(media_dir / "%(id)s.%(ext)s")
    run(
        [which("yt-dlp"), "-q", "--no-warnings", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
         "--merge-output-format", "mp4", "--socket-timeout", "30", "--retries", "3", "-o", out_tpl, src]
    )  # fmt: skip
    # Platform captions are only a cross-check (Whisper is the transcript of record), so they are
    # best-effort and limited to original English: "en.*" also matched every auto-translation
    # (en-de, en-fr, ...) and tripped YouTube's 429 rate limit.
    run(
        [which("yt-dlp"), "-q", "--no-warnings", "--skip-download", "--write-auto-sub", "--write-sub",
         "--sub-langs", "en,en-orig", "--convert-subs", "srt", "-o", out_tpl, src],
        check=False,
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


class SheetGateExceeded(RuntimeError):
    pass


def ideas_sheet(style: str, blueprint_path: Path, ideas: list[dict[str, Any]] | None = None) -> str:
    if ideas:
        rows = "\n".join(
            f"| {i['n']} | {i['title']} | {i['hook']} | {i['angle']} | {i['case_study']} | {i['style']} | {i['music_mood']} |"
            for i in ideas
        )
    else:
        rows = "\n".join(f"| {i} | " + " | ".join("TODO" for _ in IDEA_FIELDS) + " |" for i in range(1, 6))
    return (
        f"# Video ideas for blueprint `{style}`\n\n"
        f"Blueprint: `{blueprint_path.relative_to(ROOT).as_posix()}`\n\n"
        "Nothing is voiced, mixed or rendered until you approve ideas (Ideas tab, or):\n\n"
        "```\npython analyzer/analyze_reference.py approve --work <this folder> --ideas 1,3\n```\n\n"
        f"| # | {' | '.join(IDEA_FIELDS)} |\n|---|{'---|' * len(IDEA_FIELDS)}\n{rows}\n"
    )


def estimate_sheets(sources: list[str], mode: str) -> int:
    total = 0
    for src in sources:
        if src.startswith(("http://", "https://")):
            dur = float(run([which("yt-dlp"), "--no-warnings", "--print", "%(duration)s", src]).stdout.strip() or 0)
        else:
            dur = probe(Path(src))["duration"]
        total += sheet_count(dur, mode)
    return total


def reference_notes(analyses: list[dict[str, Any]]) -> str:
    """Compact text summary of the references for the idea prompt (hooks + pacing + transcript start)."""
    notes = []
    for a in analyses:
        transcript = read_json(ROOT / Path(a["video"]).parent.parent / "transcript.json") if a.get("video") else []
        text = " ".join(s["text"] for s in transcript)[:700]
        notes.append(
            f"- {a['source']} ({a['aspect_ratio']}, {a['duration']:.0f}s, {a['pacing']['scene_count']} shots, "
            f"avg shot {a['pacing']['avg_shot_sec']}s, {a['words_per_minute']} wpm)\n"
            f"  first 3s said: {a['hook_first_3s']['said']!r}\n  transcript: {text}"
        )
    return "\n".join(notes)


def analyze_references(sources: list[str], style: str, mode: str = "condensed", yes: bool = False) -> Path:
    """Download + analyze references, draft the blueprint. Returns the work folder."""
    style = slugify(style)
    if not yes:
        total = estimate_sheets(sources, mode)
        if total > SHEET_GATE:
            raise SheetGateExceeded(
                f"{total} contact sheets in {mode} mode exceeds the {SHEET_GATE}-sheet gate. "
                "Use mode 'hook' or 'condensed', or confirm to proceed."
            )
    run_dir = WORK / f"{date.today().isoformat()}-{style}"
    run_dir.mkdir(parents=True, exist_ok=True)
    analyses = []
    for i, src in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}] analyzing {src}", flush=True)
        analyses.append(analyze_one(src, run_dir / f"ref{i}", mode))
    write_json(run_dir / "analysis.json", analyses)
    bp = draft_blueprint(style, analyses)
    bp_path = BLUEPRINTS / f"{style}.json"
    write_json(bp_path, bp)
    (run_dir / "IDEAS.md").write_text(ideas_sheet(style, bp_path), encoding="utf-8")
    write_json(
        run_dir / "approval.json",
        {"blueprint": bp_path.relative_to(ROOT).as_posix(), "status": "pending", "approved": []},
    )
    print(f"analysis : {run_dir}", flush=True)
    print(f"blueprint: {bp_path}", flush=True)
    return run_dir


def propose_ideas(run_dir: Path, topic_hint: str = "", niche: str = "") -> list[dict[str, Any]]:
    """Ask the configured LLM for 5 ideas mapped to the blueprint. Writes ideas.json + IDEAS.md."""
    from llm.tasks import generate_ideas, read_reference_frames

    approval = read_json(run_dir / "approval.json")
    bp_path = ROOT / approval["blueprint"]
    bp = read_json(bp_path)
    analyses = read_json(run_dir / "analysis.json")
    if "TODO" in json.dumps(bp.get("hook_first_3s", {})):
        # Vision step: let the model read the contact sheets (first-3s sheet first) and fill the TODOs.
        sheets = sorted((ROOT / p for p in analyses[0]["contact_sheets"]), key=lambda p: (p.stem != "first-3s", p.name))
        try:
            bp = read_reference_frames(bp, sheets, analyses[0]["hook_first_3s"]["said"])
            write_json(bp_path, bp)
            print("blueprint: visual fields filled from contact sheets", flush=True)
        except Exception as exc:  # noqa: BLE001 - ideas still work from transcript + pacing
            print(f"blueprint: vision step skipped ({str(exc)[:120]})", flush=True)
    ideas = generate_ideas(blueprint=bp, topic_hint=topic_hint, niche=niche, reference_notes=reference_notes(analyses))
    write_json(run_dir / "ideas.json", ideas)
    (run_dir / "IDEAS.md").write_text(ideas_sheet(bp["style_name"], bp_path, ideas), encoding="utf-8")
    return ideas


def approve_ideas(run_dir: Path, chosen: list[int], write_scripts: bool = True) -> list[str]:
    """Record the user's approval; create projects/<blueprint>-idea<N>/script.json for each idea.

    With an LLM configured, each script is fully written from the idea + blueprint; without one,
    a scaffold is created for you (or Kiro) to fill in.
    """
    from pipeline.router import BLUEPRINT_ENGINE_TO_STYLE

    approval = read_json(run_dir / "approval.json")
    bp = read_json(ROOT / approval["blueprint"])
    ideas = {i["n"]: i for i in (read_json(run_dir / "ideas.json") if (run_dir / "ideas.json").exists() else [])}
    prefs = settings.load()["defaults"]
    voice = {"engine": prefs["voice_engine"], "voice": prefs["voice"], "rate": prefs["rate"]}
    created = []
    for n in chosen:
        idea = ideas.get(n, {})
        style = idea.get("style") or BLUEPRINT_ENGINE_TO_STYLE.get(bp["recommended_engine"], "concept_explainer")
        mood = idea.get("music_mood") or bp["audio_profile"]["music_mood"]
        script: dict[str, Any] | None = None
        if write_scripts and idea:
            from llm.tasks import write_script

            brief = f"{idea['title']}. Hook: {idea['hook']}. Angle: {idea['angle']}. Case study: {idea['case_study']}."
            try:
                script = write_script(
                    brief=brief,
                    style=style,
                    aspect=bp["aspect_ratio"],
                    mood=mood,
                    duration_sec=int(bp.get("target_duration_sec") or prefs["target_duration_sec"]),
                    voice=voice,
                    language=prefs["language"],
                    blueprint=bp,
                )
            except Exception as exc:  # noqa: BLE001 - fall back to a scaffold, never lose the approval
                print(f"idea {n}: script writing failed ({str(exc)[:160]}); created a scaffold instead", flush=True)
        if script is None:
            script = {
                "title": idea.get("title") or f"TODO idea {n} title",
                "description": idea.get("angle", ""),
                "style": style,
                "aspect_ratio": bp["aspect_ratio"],
                "music_mood": mood,
                "voice": voice,
                "scenes": [
                    {"narration": "TODO", "visual": {"type": "headline", "heading": "TODO"}}
                    for _ in bp["beat_template"]
                ],
            }
        proj = PROJECTS / title_slug(script.get("title") or idea.get("title") or "")
        proj.mkdir(parents=True, exist_ok=True)
        script.update(
            {
                "caption_style": bp["pacing"]["caption_style"],
                "blueprint": approval["blueprint"],
                "approval": "approved",
                "idea": idea,
            }
        )
        write_json(proj / "script.json", script)
        created.append(proj.relative_to(ROOT).as_posix())
    approval.update({"status": "approved", "approved": chosen, "projects": created})
    write_json(run_dir / "approval.json", approval)
    return created


def cmd_analyze(args: argparse.Namespace) -> int:
    try:
        run_dir = analyze_references(args.sources, args.style, args.mode, args.yes)
    except SheetGateExceeded as exc:
        print(exc)
        return 2
    if not args.no_ideas:
        try:
            ideas = propose_ideas(run_dir, args.topic or "", settings.load()["defaults"]["niche"])
            for i in ideas:
                print(f"  {i['n']}. {i['title']}  [{i['style']}, {i['music_mood']}]\n     hook: {i['hook']}")
        except Exception as exc:  # noqa: BLE001
            print(f"ideas: LLM unavailable ({str(exc)[:160]}). Fill {run_dir / 'IDEAS.md'} by hand or ask Kiro.")
    print(
        f"ideas    : {run_dir / 'IDEAS.md'} -> approve with: analyze_reference.py approve --work {run_dir} --ideas 1,3"
    )
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    created = approve_ideas(
        Path(args.work), [int(x) for x in args.ideas.split(",") if x.strip()], not args.scaffold_only
    )
    print(json.dumps({"approved": args.ideas, "projects": created}, indent=2), flush=True)
    if args.render:
        from make_video import produce

        for rel_path in created:
            print(f"rendering {rel_path}", flush=True)
            produce(ROOT / rel_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="Analyze reference video(s) into a blueprint")
    a.add_argument("sources", nargs="+", help="URLs or local video files")
    a.add_argument("--style", required=True, help="Blueprint name, e.g. vox_maps")
    a.add_argument("--mode", choices=list(MODES), default="condensed")
    a.add_argument("--yes", action="store_true", help="Skip the 15-sheet gate")
    a.add_argument("--topic", help="Optional topic hint for the 5 ideas")
    a.add_argument("--no-ideas", action="store_true", help="Only analyze; do not call the LLM for ideas")
    a.set_defaults(func=cmd_analyze)
    b = sub.add_parser("approve", help="Record which ideas the user approved")
    b.add_argument("--work", required=True)
    b.add_argument("--ideas", required=True, help="Comma list, e.g. 1,3")
    b.add_argument("--scaffold-only", action="store_true", help="Create script scaffolds without the LLM")
    b.add_argument("--render", action="store_true", help="Render each approved project after writing it")
    b.set_defaults(func=cmd_approve)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
