"""End-to-end smoke test: a real ~5 second 9:16 render.

Edge-TTS -> faster-whisper word captions -> ducked music (-14 LUFS) -> Remotion ConceptExplainer
-> ffprobe validation (H.264 yuv420p + AAC, 1080x1920, duration matches audio).
It also measures the ducking: music under speech must be quieter than the same music undocked.

Usage: python scripts/smoke_test.py [--keep]
Output: output/smoke_test.mp4 (+ projects/_smoke/qa/*.png stills)
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from audio_pipeline.mix_music_and_sfx import (  # noqa: E402
    MUSIC_LIBRARY,
    TAIL_SEC,
    build_filter,
    measure_lufs,
    music_gain,
)
from common import ASSETS, OUTPUT, media_duration, read_json, run, which, write_json  # noqa: E402
from make_video import produce  # noqa: E402

PROJECT = ROOT / "projects" / "_smoke"
SCRIPT = {
    "title": "Smoke test",
    "slug": "smoke_test",
    "description": "video-factory end-to-end smoke test",
    "style": "concept_explainer",
    "aspect_ratio": "9:16",
    "music_mood": "upbeat",
    "voice": {"engine": "edge-tts", "voice": "en-US-AndrewNeural", "rate": "+0%"},
    "scenes": [
        {
            "narration": "This is a quick test.",
            "visual": {"type": "headline", "heading": "Smoke test", "text": "video-factory"},
        },
        {"narration": "Voice, music, and captions.", "visual": {"type": "stat", "value": "5s", "label": "end to end"}},
    ],
}


def mean_volume(narration: Path, music: Path, label: str) -> float:
    """Mean dB of one internal label of the mix graph over the narration span."""
    speech = media_duration(narration)
    volume = round(0.22 * music_gain(music), 5)
    split, music_base, sidechain, _amix = build_filter(speech + TAIL_SEC, [], volume).split(";")
    if label == "[music_ducked]":
        graph = [split, music_base, sidechain, "[vo]anullsink"]
    else:
        graph = [split, music_base, "[vo]anullsink", "[vo_sc]anullsink"]
    graph.append(f"{label}atrim=0:{speech:.3f},volumedetect[o]")
    res = run([which("ffmpeg"), "-hide_banner", "-i", str(narration), "-stream_loop", "-1", "-i", str(music),
               "-filter_complex", ";".join(graph), "-map", "[o]", "-f", "null", "-"])  # fmt: skip
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", res.stderr)
    if not m:
        raise RuntimeError("volumedetect produced no reading")
    return float(m.group(1))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--keep", action="store_true", help="Keep projects/_smoke after the run")
    a = p.parse_args()
    t0 = time.time()
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    write_json(PROJECT / "script.json", SCRIPT)

    result = produce(PROJECT, use_llm=False)  # deterministic: no API key needed
    report = result["report"]
    run_dir = PROJECT / "assets"
    failures: list[str] = []

    timing = read_json(run_dir / "timing.json")
    captions = read_json(run_dir / "captions.json")
    expected = timing["total_duration_sec"] + TAIL_SEC
    if not (3.0 <= timing["total_duration_sec"] <= 8.0):
        failures.append(f"narration {timing['total_duration_sec']}s is not ~5s")
    if len(captions) < 5 or not all({"word", "start", "end"} <= c.keys() for c in captions):
        failures.append(f"captions.json looks wrong ({len(captions)} words)")
    if abs(report["duration_sec"] - expected) > 0.4:
        failures.append(f"video {report['duration_sec']}s vs audio clock {expected:.2f}s")
    if "1080x1920" not in report["video"]:
        failures.append(f"expected 1080x1920, got {report['video']}")

    lufs = measure_lufs(run_dir / "mixed_master.wav")
    if abs(lufs - (-14.0)) > 1.0:
        failures.append(f"mixed master {lufs} LUFS, expected -14 +/- 1")

    track = read_json(run_dir / "attribution.json")["music"]
    music = MUSIC_LIBRARY / track["file"]
    base = mean_volume(run_dir / "narration.wav", music, "[music_base]")
    ducked = mean_volume(run_dir / "narration.wav", music, "[music_ducked]")
    if ducked > base - 2.0:
        failures.append(f"ducking too weak: music {base:.1f} dB -> {ducked:.1f} dB under speech")

    qa_dir = PROJECT / "qa"
    stills = [qa_dir / f"{n}.png" for n in ("cover", "hook", "early", "mid", "outro")]
    if not all(p.exists() for p in stills):
        failures.append("missing QA stills (cover + hook/early/mid/outro)")
    qa_report = result.get("qa") or {}
    if not qa_report.get("ok"):
        issues = [f"{f['frame']}: {i}" for f in qa_report.get("frames", []) for i in f["issues"]]
        failures.append("visual QA failed: " + "; ".join(issues))
    thumb = OUTPUT / "smoke_test.thumb.jpg"
    if not thumb.exists() or thumb.stat().st_size > 2_000_000:
        failures.append("thumbnail missing or over YouTube's 2 MB limit")
    sfx_used = read_json(run_dir / "attribution.json").get("sfx", [])
    if not sfx_used:
        failures.append("no sound effects were mixed")

    print("\n=== smoke test ===")
    print(f"file      : {report['file']}")
    print(f"video     : {report['video']}")
    print(f"audio     : {report['audio']}")
    print(f"duration  : {report['duration_sec']}s (audio clock {expected:.2f}s)")
    print(f"captions  : {len(captions)} words, first: {captions[0]['word'] if captions else '-'}")
    print(f"loudness  : {lufs:.1f} LUFS")
    print(f"ducking   : music {base:.1f} dB -> {ducked:.1f} dB under speech ({base - ducked:.1f} dB)")
    print(f"music     : {track['file']}")
    print(f"visual QA : {'pass' if qa_report.get('ok') else 'FAIL'} ({len(stills)} frames incl. cover) in {qa_dir}")
    print(f"sfx       : {', '.join(sfx_used) or 'none'}")
    print(f"thumbnail : {thumb} ({thumb.stat().st_size // 1024 if thumb.exists() else 0} KB)")
    print(f"time      : {time.time() - t0:.0f}s")

    if not a.keep:
        shutil.rmtree(ASSETS / "smoke_test", ignore_errors=True)
    if failures:
        print("\nFAILED:\n  - " + "\n  - ".join(failures))
        return 1
    print(f"\nPASSED -> {OUTPUT / 'smoke_test.mp4'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
