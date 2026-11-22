"""Long-to-short clipper (offline): source video -> one captioned 9:16 Short.

Picks the highest-density speech window with faster-whisper, snaps its start to a
PySceneDetect cut, crops to the target aspect, ducks mood music under the original speech,
and burns word captions.

Cropping: centre crop by default (fast). With speaker tracking ON (Settings, or
`"clip": {"speaker_tracking": true}`), OpenCV's bundled face detector samples each shot
and the crop follows the main face, one position per shot (no jitter within a shot).

script.json:
    "style": "clip_repurpose",
    "clip": {"source": "path/or/url.mp4", "max_sec": 45, "min_sec": 15, "speaker_tracking": false}

The full Clipsmith app (Ollama moment picking) lives in engines/clipper/ (`run.bat`).
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from audio_pipeline.make_voice_and_subs import transcribe_words
from audio_pipeline.mix_music_and_sfx import MUSIC_LIBRARY, choose_track, mix
from common import ROOT, media_duration, run, settings, which, write_json
from engines import DIMENSIONS, subtitles_filter, write_ass


def fetch_source(src: str, work: Path) -> Path:
    if src.startswith(("http://", "https://")):
        out = work / "source.mp4"
        run([which("yt-dlp"), "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4", "-o", str(out), src])
        return out
    path = Path(src)
    return path if path.is_absolute() else ROOT / path


def best_window(words: list[dict], total: float, min_sec: float, max_sec: float) -> tuple[float, float]:
    """Window of length <= max_sec with the most spoken words."""
    if not words:
        return 0.0, min(total, max_sec)
    best = (0.0, min(total, max_sec), -1)
    j = 0
    for i, w in enumerate(words):
        while j < len(words) and words[j]["end"] - w["start"] <= max_sec:
            j += 1
        count = j - i
        if count > best[2] and words[j - 1]["end"] - w["start"] >= min_sec:
            best = (w["start"], words[j - 1]["end"], count)
    return max(0.0, best[0] - 0.2), min(total, best[1] + 0.3)


def scene_cuts(video: Path) -> list[float]:
    try:
        from scenedetect import ContentDetector, detect

        return [s[0].get_seconds() for s in detect(str(video), ContentDetector())][1:]
    except Exception:  # noqa: BLE001 - scene detection is an optimisation, never fatal
        return []


def snap_to_cuts(cuts: list[float], start: float, end: float) -> tuple[float, float]:
    near = [c for c in cuts if abs(c - start) < 1.5]
    return (min(near, key=lambda c: abs(c - start)) if near else start), end


def face_centers(video: Path, start: float, end: float, cuts: list[float], fps_sample: float = 2.0) -> list[tuple[float, float]]:
    """Per shot inside [start, end): (shot start relative to clip, median face centre x in 0..1)."""
    import cv2

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(video))
    bounds = [start, *[c for c in cuts if start < c < end], end]
    shots: list[tuple[float, float]] = []
    try:
        for a, b in zip(bounds, bounds[1:], strict=False):
            xs: list[float] = []
            t = a + 0.1
            while t < b:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
                ok, frame = cap.read()
                if not ok:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                small = cv2.resize(gray, (gray.shape[1] // 2, gray.shape[0] // 2))
                faces = cascade.detectMultiScale(small, scaleFactor=1.15, minNeighbors=6, minSize=(30, 30))
                if len(faces):
                    x, _y, w, _h = max(faces, key=lambda f: f[2] * f[3])  # biggest face = main speaker
                    xs.append((x + w / 2) / small.shape[1])
                t += 1 / fps_sample
            shots.append((round(a - start, 3), statistics.median(xs) if xs else 0.5))
    finally:
        cap.release()
    return shots


def crop_x_expr(shots: list[tuple[float, float]], crop_w_expr: str) -> str:
    """Piecewise-constant crop x: one position per shot, clamped inside the frame."""
    expr = "(iw-ow)/2"
    for t0, cx in reversed(shots):
        x = f"min(max(0,{cx:.4f}*iw-ow/2),iw-ow)"
        expr = f"if(gte(t,{t0:.3f}),{x},{expr})"
    return expr.replace("ow", crop_w_expr)


def render(script: dict[str, Any], run_dir: Path, out_mp4: Path, aspect: str) -> Path:
    cfg = script.get("clip") or {}
    if "source" not in cfg:
        raise ValueError('clip_repurpose needs "clip": {"source": ...} in script.json')
    tracking = bool(cfg.get("speaker_tracking", settings.load()["clipper"]["speaker_tracking"]))
    run_dir.mkdir(parents=True, exist_ok=True)
    src = fetch_source(cfg["source"], run_dir)
    total = media_duration(src)

    speech = run_dir / "clip_speech_full.wav"
    run([which("ffmpeg"), "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "48000", str(speech)])
    words = transcribe_words(speech, "auto", "auto", None)
    start, end = best_window(words, total, float(cfg.get("min_sec", 15)), float(cfg.get("max_sec", 45)))
    cuts = scene_cuts(src)
    start, end = snap_to_cuts(cuts, start, end)
    dur = end - start

    clip_words = [
        {"word": x["word"], "start": round(x["start"] - start, 3), "end": round(x["end"] - start, 3)}
        for x in words
        if start <= x["start"] < end
    ]
    write_json(run_dir / "captions.json", clip_words)

    narration = run_dir / "clip_speech.wav"
    run([which("ffmpeg"), "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(speech), str(narration)])
    track = choose_track(script.get("music_mood", "upbeat"), script.get("title", "clip"))
    master = run_dir / "mixed_master.wav"
    mix(narration, MUSIC_LIBRARY / track["file"], master, music_volume=0.12)

    w, h = DIMENSIONS[aspect]
    crop_w, crop_h = f"min(iw,ih*{w}/{h})", f"min(ih,iw*{h}/{w})"
    if tracking:
        shots = face_centers(src, start, end, cuts)
        write_json(run_dir / "speaker_tracking.json", [{"t": t, "cx": cx} for t, cx in shots])
        crop = f"crop='{crop_w}':'{crop_h}':'{crop_x_expr(shots, crop_w)}':'(ih-oh)/2'"
    else:
        crop = f"crop='{crop_w}':'{crop_h}'"
    ass = write_ass(clip_words, run_dir / "captions.ass", w, h, aspect)
    vf = f"{crop},scale={w}:{h},setsar=1,{subtitles_filter(ass)}"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    run(
        [which("ffmpeg"), "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-i", str(master),
         "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out_mp4)]
    )  # fmt: skip
    return out_mp4
