"""Narration + word-level captions.

script.json -> (Edge-TTS | Kokoro) per scene -> narration.wav (48 kHz mono)
            -> faster-whisper word timestamps -> captions.json + timing.json

The audio is the master clock: ``timing.json`` holds the total duration and the
start/end of every scene, and every later step reads those numbers.

Usage:
    python audio_pipeline/make_voice_and_subs.py --script projects/demo/script.json \
        --out studio/public/assets
"""

from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from common import ROOT, read_json, run, sha256_text, which, write_json  # noqa: E402

SAMPLE_RATE = 48_000
SCENE_GAP_SEC = 0.25
CACHE_DIR = ROOT / "audio_pipeline" / "cache"
DEFAULT_VOICES = {"edge-tts": "en-US-AndrewNeural", "kokoro": "af_heart"}


def scene_texts(script: dict[str, Any]) -> list[str]:
    """Narration text for each scene (a bare `narration` string becomes one scene)."""
    if script.get("scenes"):
        return [str(s.get("narration", "")).strip() for s in script["scenes"]]
    if script.get("narration"):
        return [str(script["narration"]).strip()]
    raise ValueError("script.json needs `scenes[].narration` or a top-level `narration`.")


def _to_wav48(src: Path, dest: Path) -> None:
    run([which("ffmpeg"), "-y", "-i", str(src), "-ar", str(SAMPLE_RATE), "-ac", "1", str(dest)])


async def _edge_tts(text: str, voice: str, rate: str, dest: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, voice, rate=rate).save(str(dest))


def synth_edge(text: str, voice: str, rate: str, dest: Path, attempts: int = 8) -> None:
    """Edge-TTS occasionally returns no audio; retry with backoff before giving up."""
    tmp = dest.with_suffix(".mp3")
    for attempt in range(1, attempts + 1):
        try:
            asyncio.run(_edge_tts(text, voice, rate, tmp))
            if tmp.exists() and tmp.stat().st_size > 0:
                break
        except Exception as exc:  # edge_tts raises several transport/protocol errors
            if attempt == attempts:
                raise RuntimeError(f"Edge-TTS failed after {attempts} attempts: {exc}") from exc
        time.sleep(min(20.0, 2.0**attempt))  # failures come in bursts; back off up to 20 s
    _to_wav48(tmp, dest)
    tmp.unlink(missing_ok=True)


def synth_kokoro(text: str, voice: str, rate: str, dest: Path) -> None:
    """Local Kokoro TTS. Needs `pip install kokoro soundfile` and espeak-ng for some voices."""
    try:
        from kokoro import KPipeline
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Kokoro is not installed. Use engine 'edge-tts' or `pip install kokoro`.") from exc
    import torch

    speed = 1.0 + _rate_to_fraction(rate)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    with warnings.catch_warnings():  # upstream torch deprecation noise, not actionable here
        warnings.simplefilter("ignore", (UserWarning, FutureWarning))
        pipeline = KPipeline(lang_code=voice[0] if voice else "a", repo_id="hexgrad/Kokoro-82M", device=device)
        chunks = [np.asarray(audio, dtype=np.float32) for _, _, audio in pipeline(text, voice=voice, speed=speed)]
    if not chunks:
        raise RuntimeError("Kokoro returned no audio.")
    tmp = dest.with_suffix(".k.wav")
    sf.write(str(tmp), np.concatenate(chunks), 24_000)
    _to_wav48(tmp, dest)
    tmp.unlink(missing_ok=True)


def _rate_to_fraction(rate: str) -> float:
    m = re.fullmatch(r"([+-]?\d+)%", rate.strip())
    return int(m.group(1)) / 100 if m else 0.0


def synth_scene(text: str, engine: str, voice: str, rate: str) -> Path:
    """Synthesize one scene, cached by content hash so re-runs are free."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CACHE_DIR / f"{sha256_text(engine, voice, rate, text)}.wav"
    if dest.exists():
        return dest
    if engine == "edge-tts":
        synth_edge(text, voice, rate, dest)
    elif engine == "kokoro":
        synth_kokoro(text, voice, rate, dest)
    else:
        raise ValueError(f"Unknown TTS engine: {engine}")
    return dest


def build_narration(texts: list[str], engine: str, voice: str, rate: str, out_wav: Path) -> list[dict]:
    """Concatenate scene audio with short gaps. Returns scene timings in seconds."""
    pieces: list[np.ndarray] = []
    scenes: list[dict] = []
    cursor = 0.0
    gap = np.zeros(int(SCENE_GAP_SEC * SAMPLE_RATE), dtype=np.float32)
    for i, text in enumerate(texts):
        if text:
            data, sr = sf.read(str(synth_scene(text, engine, voice, rate)), dtype="float32")
            if sr != SAMPLE_RATE:
                raise RuntimeError(f"Unexpected sample rate {sr}")
            if data.ndim > 1:
                data = data.mean(axis=1)
        else:
            data = np.zeros(int(1.0 * SAMPLE_RATE), dtype=np.float32)
        length = len(data) / SAMPLE_RATE
        end = cursor + length + (SCENE_GAP_SEC if i < len(texts) - 1 else 0.0)
        scenes.append({"index": i, "start": round(cursor, 3), "end": round(end, 3), "text": text})
        pieces.append(data)
        if i < len(texts) - 1:
            pieces.append(gap)
        cursor = end
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), np.concatenate(pieces), SAMPLE_RATE, subtype="PCM_16")
    return scenes


def resolve_model(model_name: str, device: str, language: str | None) -> str:
    """`auto` = small (accurate) on GPU, base (fast) on CPU. English-only `.en` models for English."""
    if model_name == "auto":
        model_name = "small.en" if device == "cuda" else "base.en"
    if language not in (None, "en"):
        model_name = model_name.replace(".en", "")
    return model_name


def transcribe_words(wav: Path, model_name: str, device: str, language: str | None) -> list[dict]:
    """Word-level timestamps with faster-whisper. `model_name` may be "auto" (see resolve_model)."""
    from faster_whisper import WhisperModel

    # Decode with FFmpeg to a 16 kHz float array, avoiding PyAV version mismatches.
    raw = subprocess.run(
        [which("ffmpeg"), "-v", "error", "-i", str(wav), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True,
        check=True,
    ).stdout
    audio = np.frombuffer(raw, dtype=np.float32)

    def _run(dev: str, compute: str) -> list[dict]:
        name = resolve_model(model_name, dev, language)
        model = WhisperModel(name, device=dev, compute_type=compute)
        segments, _info = model.transcribe(audio, word_timestamps=True, language=language, beam_size=1)
        out: list[dict] = []
        for seg in segments:
            for w in seg.words or []:
                token = w.word.strip()
                if token:
                    out.append({"word": token, "start": round(w.start, 3), "end": round(w.end, 3)})
        return out

    if device == "cpu":
        return _run("cpu", "int8")
    try:
        return _run("cuda", "float16")
    except (RuntimeError, ValueError) as exc:
        if device == "cuda":
            raise
        print(f"faster-whisper: CUDA unavailable ({exc}); using CPU int8.", file=sys.stderr)
        return _run("cpu", "int8")


# Kokoro voice ids start with a language letter: af_heart = American English, ef_dora = Spanish, ...
KOKORO_LANGS = {"a": "en", "b": "en", "e": "es", "f": "fr", "h": "hi", "i": "it", "j": "ja", "p": "pt", "z": "zh"}


def language_from_voice(voice: str) -> str | None:
    """ISO language for Whisper from an Edge (en-US-AndrewNeural) or Kokoro (ef_dora) voice id."""
    m = re.match(r"^([a-z]{2})-[A-Z]{2}-", voice)
    if m:
        return m.group(1)
    m = re.match(r"^([a-z])[fm]_", voice)
    return KOKORO_LANGS.get(m.group(1)) if m else None


def run_pipeline(
    script_path: Path,
    out_dir: Path,
    engine: str | None = None,
    voice: str | None = None,
    rate: str | None = None,
    whisper_model: str = "auto",
    device: str = "auto",
) -> dict[str, Any]:
    script = read_json(script_path)
    cfg = script.get("voice", {})
    engine = engine or cfg.get("engine", "edge-tts")
    voice = voice or cfg.get("voice") or DEFAULT_VOICES[engine]
    rate = rate or cfg.get("rate", "+0%")
    texts = scene_texts(script)

    narration = out_dir / "narration.wav"
    scenes = build_narration(texts, engine, voice, rate, narration)
    total = scenes[-1]["end"]

    lang = language_from_voice(voice)
    words = transcribe_words(narration, whisper_model, device, lang)

    write_json(out_dir / "captions.json", words)
    timing = {
        "total_duration_sec": total,
        "engine": engine,
        "voice": voice,
        "rate": rate,
        "scenes": scenes,
        "narration": narration.name,
    }
    write_json(out_dir / "timing.json", timing)
    return timing


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--script", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True, help="Directory for narration.wav/captions.json/timing.json")
    p.add_argument("--engine", choices=["edge-tts", "kokoro"])
    p.add_argument("--voice")
    p.add_argument("--rate", help='Edge-style rate, e.g. "+10%%"')
    p.add_argument("--whisper-model", default="auto", help="auto = small.en on GPU, base.en on CPU")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    args = p.parse_args(argv)
    timing = run_pipeline(args.script, args.out, args.engine, args.voice, args.rate, args.whisper_model, args.device)
    print(f"narration: {timing['total_duration_sec']:.2f}s, {len(timing['scenes'])} scene(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
