"""Fast unit tests for pure helpers (no network, no rendering)."""

from __future__ import annotations

import pytest

from analyzer.analyze_reference import aspect_of, pacing, sheet_count
from audio_pipeline.make_voice_and_subs import language_from_voice, resolve_model, scene_texts
from audio_pipeline.mix_music_and_sfx import build_filter
from engines.clipper_engine import best_window
from pipeline.render import build_props
from pipeline.router import route


def test_router_known_and_unknown() -> None:
    assert route("vox_documentary").composition == "VoxEditorial"
    assert route("math_science").engine == "manim"
    with pytest.raises(ValueError):
        route("nope")


def test_filter_has_sidechain_ducking() -> None:
    f = build_filter(10.0, [], 0.22)
    assert "sidechaincompress=threshold=0.02:ratio=6:attack=30:release=350" in f
    assert "afade=t=out:st=8.800" in f and f.endswith("[out]")


def test_filter_with_sfx() -> None:
    f = build_filter(5.0, [{"file": "x.wav", "at": 1.5}], 0.2)
    assert "adelay=1500|1500" in f and "amix=inputs=3" in f


def test_scene_texts() -> None:
    assert scene_texts({"scenes": [{"narration": " a "}, {"narration": "b"}]}) == ["a", "b"]
    assert scene_texts({"narration": "x"}) == ["x"]
    with pytest.raises(ValueError):
        scene_texts({})


def test_language_from_voice() -> None:
    assert language_from_voice("en-US-AndrewNeural") == "en"
    assert language_from_voice("af_heart") == "en"
    assert language_from_voice("ef_dora") == "es"
    assert language_from_voice("custom") is None


def test_resolve_model() -> None:
    assert resolve_model("auto", "cuda", "en") == "small.en"
    assert resolve_model("auto", "cpu", None) == "base.en"
    assert resolve_model("auto", "cuda", "es") == "small"


def test_analyzer_helpers() -> None:
    assert aspect_of(1080, 1920) == "9:16" and aspect_of(1920, 1080) == "16:9" and aspect_of(1080, 1080) == "1:1"
    assert sheet_count(45, "forensic") == 2 and sheet_count(600, "condensed") == 7 and sheet_count(9999, "hook") == 1
    p = pacing([2.0, 4.0], 6.0)
    assert p["scene_count"] == 3 and p["median_shot_sec"] == 2.0 and p["cuts_in_first_3s"] == 1


def test_best_window_prefers_dense_speech() -> None:
    words = [{"word": "w", "start": t, "end": t + 0.3} for t in [0, 10, 20, 30, 31, 32, 33, 34]]
    start, end = best_window(words, 40, min_sec=2, max_sec=5)
    assert 29 <= start <= 30 and end <= 40


def test_build_props_uses_audio_clock() -> None:
    timing = {"total_duration_sec": 4.0, "scenes": [{"start": 0, "end": 2}, {"start": 2, "end": 4}]}
    script = {
        "title": "T",
        "scenes": [{"narration": "a", "visual": {"type": "stat", "value": "1"}}, {"narration": "b"}],
    }
    props = build_props(
        script, timing, [], aspect_ratio="16:9", caption_style="none", theme=None, asset_prefix="assets/t"
    )
    assert props["durationSec"] == 4.5 and props["scenes"][-1]["end"] == 4.5
    assert props["scenes"][1]["visual"] == {"type": "headline", "heading": "b"}
    assert props["audioSrc"] == "assets/t/mixed_master.wav"
