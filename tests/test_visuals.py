"""No text-only scenes, icon list parity with the Remotion templates, SFX manifest and -12 dB level."""

from __future__ import annotations

import re
from pathlib import Path

from audio_pipeline import sfx
from common import ROOT, read_json
from llm import tasks as T
from pipeline.visuals import CONCRETE, ICON_NAMES, ensure_concrete, pick_icon, validate_script


def test_icon_names_match_remotion_icons() -> None:
    src = (ROOT / "studio/src/components/visuals/icons.tsx").read_text(encoding="utf-8")
    block = src[src.index("export const ICONS") : src.index("export const resolveIcon")]
    keys = set(re.findall(r"^\s*'?([a-z-]+)'?:", block, re.M))
    assert keys == set(ICON_NAMES)


def test_text_first_scenes_become_concrete_by_look() -> None:
    head = {"type": "headline", "heading": "Why prices rise"}
    assert ensure_concrete(head, "Prices rise every year.", "whiteboard")["type"] == "sketch"
    assert ensure_concrete(head, "Prices rise every year.", "vox")["type"] == "cutout"
    assert ensure_concrete(head, "x", "concept")["icon"] == "coins"
    bullets = ensure_concrete({"type": "bullets", "items": ["a", "b", "c"]}, "n", "concept")
    assert bullets["type"] == "diagram" and bullets["items"] == ["a", "b", "c"]
    quote = ensure_concrete({"type": "quote", "text": "Be kind"}, "n", "concept")
    assert quote["type"] == "cutout" and quote["heading"] == "Be kind"
    stat = {"type": "stat", "value": "3x", "label": "l"}
    assert ensure_concrete(stat, "n") == stat


def test_validate_script_reports_changes() -> None:
    script = {"scenes": [{"narration": "Money matters.", "visual": {"type": "headline", "heading": "Money"}},
                         {"narration": "n", "visual": {"type": "chart", "data": []}}]}  # fmt: skip
    notes = validate_script(script, "concept")
    assert len(notes) == 1 and "scene 1" in notes[0]
    assert all(s["visual"]["type"] in CONCRETE for s in script["scenes"])


def test_pick_icon_falls_back() -> None:
    assert pick_icon("The loan was repaid") == "wallet"
    assert pick_icon("zzz") == "sparkles"


def test_normalizer_keeps_new_visual_types() -> None:
    v = T.normalize_visual({"type": "stickman", "pose": "dance", "bubble": "Hi"}, "n")
    assert v["pose"] == "idle" and v["bubble"] == "Hi"
    assert T.normalize_visual({"type": "sketch", "icon": "nope", "draw_cues": ["a", "b"]}, "n")["draw_cues"] == [
        "a",
        "b",
    ]
    assert "icon" not in T.normalize_visual({"type": "sketch", "icon": "nope"}, "narration")
    assert T.normalize_visual({"type": "timeline", "items": ["2007: x"]}, "n")["items"] == ["2007: x"]


def test_cue_volume_is_12_db_under_voice() -> None:
    gain = sfx.cue_volume(voice_peak_db=-3.0, sfx_peak_db=-3.0)
    assert abs(20 * __import__("math").log10(gain) - (-12.0)) < 0.01
    quieter = sfx.cue_volume(-3.0, -9.0)  # a quiet clip is boosted to the same level
    assert quieter > gain


def test_sfx_manifest_maps_required_clips() -> None:
    lib = sfx.ensure_library()
    manifest = read_json(Path(sfx.MANIFEST))
    names = {c["name"]: c for c in manifest["sfx"]}
    for required in sfx.REQUIRED:
        assert required in lib and names[required]["required"] is True
        assert (sfx.SFX_DIR / names[required]["file"]).exists() and "CC0" in names[required]["license"]
    assert manifest["relative_level_db"] == -12.0


def test_auto_cues_use_riser_and_relative_level() -> None:
    timing = {"scenes": [{"start": 0.0, "end": 3.0}, {"start": 3.0, "end": 6.0}, {"start": 6.0, "end": 9.0}]}
    scenes = [
        {"visual": {"type": "sketch"}, "beat": "hook"},
        {"visual": {"type": "counter"}, "beat": "case_study"},
        {"visual": {"type": "diagram"}, "beat": "takeaway"},
    ]
    cues = sfx.auto_cues(timing, scenes, "whiteboard", voice_peak_db=-3.0)
    files = [Path(c["file"]).stem for c in cues]
    assert "riser" in files and "chalk_draw" in files and "pop" in files
    assert all(0 < c["volume"] < 1.5 for c in cues)
