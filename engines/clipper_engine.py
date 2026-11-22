"""Long-to-short clipper (offline): source video -> one captioned 9:16 Short.

Picks the highest-density speech window with faster-whisper, snaps its edges to
PySceneDetect cuts, centre-crops to the target aspect, ducks mood music under the
original speech, and burns word captions.

script.json:
    "style": "clip_repurpose",
    "clip": {"source": "path/or/url.mp4", "max_sec": 45, "min_sec": 15}

The full Clipsmith app (Ollama moment picking + speaker tracking) lives in
engines/clipper/ and runs with `engines/clipper/run.bat`; see docs/ADDING_STYLES.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from audio_pipeline.make_voice_and_subs import transcribe_words
from audio_pipeline.mix_music_and_sfx import MUSIC_LIBRARY, choose_track, mix
from common import ROOT, media_duration, run, which, write_json
from engines import DIMENSIONS


def fetch_source(src: str, work: Path) -> Path:
    if src.startswith(("http://", "https://")):
        out = work / "source.mp4"
        run([which("yt-dlp"), "-f", "mp4/bestvideo[height<=1080]+bestaudio", "-o", str(out), src])
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


def snap_to_cuts(video: Path, start: float, end: float) -> tuple[float, float]:
    try:
        from scenedetect import ContentDetector, detect

        cuts = [s[0].get_seconds() for s in detect(str(video), ContentDetector())]
    except Exception:
        return start, end
    near = [c for c in cuts if abs(c - start) < 1.5]
    return (min(near, key=lambda c: abs(c - start)) if near else start), end


def _ass_time(t: float) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_ass(words: list[dict], path: Path, w: int, h: int) -> None:
    """Phrase captions placed above the bottom 22% (Shorts UI safe zone)."""
    margin_v = int(h * 0.24)
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Bold",
        f"Style: Default,Arial,78,&H00FFFFFF,&H00000000,1,5,0,2,{int(w * 0.06)},{int(w * 0.15)},{margin_v},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Text",
    ]  # fmt: skip
    for i in range(0, len(words), 3):
        chunk = words[i : i + 3]
        text = " ".join(x["word"] for x in chunk).replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 0,{_ass_time(chunk[0]['start'])},{_ass_time(chunk[-1]['end'])},Default,{text}")
    path.write_text("\n".join(lines), encoding="utf-8")


def render(script: dict[str, Any], run_dir: Path, out_mp4: Path, aspect: str) -> Path:
    cfg = script.get("clip") or {}
    if "source" not in cfg:
        raise ValueError('clip_repurpose needs "clip": {"source": ...} in script.json')
    run_dir.mkdir(parents=True, exist_ok=True)
    src = fetch_source(cfg["source"], run_dir)
    total = media_duration(src)

    speech = run_dir / "clip_speech_full.wav"
    run([which("ffmpeg"), "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "48000", str(speech)])
    words = transcribe_words(speech, "auto", "auto", None)
    start, end = best_window(words, total, float(cfg.get("min_sec", 15)), float(cfg.get("max_sec", 45)))
    start, end = snap_to_cuts(src, start, end)
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
    ass = run_dir / "captions.ass"
    write_ass(clip_words, ass, w, h)
    ass_arg = str(ass).replace("\\", "/").replace(":", r"\:")
    vf = f"crop='min(iw,ih*{w}/{h})':'min(ih,iw*{h}/{w})',scale={w}:{h},setsar=1,subtitles='{ass_arg}'"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    run(
        [which("ffmpeg"), "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-i", str(master),
         "-map", "0:v:0", "-map", "1:a:0", "-vf", vf, "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out_mp4)]
    )  # fmt: skip
    return out_mp4
