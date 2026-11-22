"""Pixel QA, post caps, settings, SFX cues, cover text, clipper crop, UI security. No rendering."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from audio_pipeline import sfx
from common import settings
from engines.clipper_engine import crop_x_expr
from pipeline import qa
from pipeline.render import cover_text_for
from publisher import post_log


def _png(path: Path, arr: np.ndarray) -> Path:
    Image.fromarray(arr.astype("uint8")).save(path)
    return path


@pytest.fixture
def frames(tmp_path: Path):  # type: ignore[no-untyped-def]
    def make(name: str, box: tuple[int, int, int, int] | None, bg: int = 20) -> tuple[Path, Path]:
        h, w = 192, 108
        base = np.full((h, w, 3), bg)
        full = base.copy()
        if box:
            y0, y1, x0, x1 = box
            full[y0:y1, x0:x1] = 250
        return _png(tmp_path / f"{name}.png", full), _png(tmp_path / f"_{name}.bg.png", base)

    return make


def test_qa_clean_frame_passes(frames) -> None:  # type: ignore[no-untyped-def]
    full, bg = frames("mid", (60, 100, 20, 80))
    r = qa.check_frame(full, bg, "9:16", "mid")
    assert r["ok"] and (full.parent / "mid.overlay.png").exists()


def test_qa_flags_unsafe_zone_and_edges(frames) -> None:  # type: ignore[no-untyped-def]
    full, bg = frames("outro", (160, 190, 20, 108))  # bottom band + right band + frame edge
    r = qa.check_frame(full, bg, "9:16", "outro")
    assert not r["ok"]
    assert any("unsafe zone" in i for i in r["issues"]) and any("frame edge" in i for i in r["issues"])


def test_qa_flags_empty_frame_and_low_contrast_cover(frames) -> None:  # type: ignore[no-untyped-def]
    full, bg = frames("early", None)
    assert any("empty" in i for i in qa.check_frame(full, bg, "9:16", "early")["issues"])
    full, bg = frames("cover", None)
    assert any("contrast" in i for i in qa.check_frame(full, bg, "9:16", "cover")["issues"])


def test_qa_16x9_has_no_shorts_bands(frames) -> None:  # type: ignore[no-untyped-def]
    full, bg = frames("hook", (160, 185, 30, 70))
    assert qa.check_frame(full, bg, "16:9", "hook")["ok"]


def test_post_log_caps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "state.sqlite"
    monkeypatch.setattr(post_log, "cap_for", lambda p: 2)
    monkeypatch.setattr(post_log, "today", lambda tz=None: "2026-01-01")
    for _ in range(2):
        post_log.check_cap("instagram", path=db)
        post_log.record("instagram", "cookie", "x", path=db)
    with pytest.raises(post_log.CapReached):
        post_log.check_cap("instagram", path=db)
    post_log.check_cap("youtube", path=db)  # caps are per platform
    assert post_log.count_today("instagram", path=db) == 2 and len(post_log.recent(path=db)) == 2


def test_settings_secrets_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings.save_env({"GEMINI_API_KEY": "abcdefghijklmnop"})
    assert settings.read_env_file()["GEMINI_API_KEY"] == "abcdefghijklmnop"
    view = settings.public_view()["env"]["GEMINI_API_KEY"]
    assert view["set"] and view["value"].endswith("mnop") and "abcdef" not in view["value"]
    with pytest.raises(ValueError):
        settings.save_env({"EVIL": "x"})
    with pytest.raises(ValueError):
        settings.save_env({"OLLAMA_HOST": "a\nGEMINI_API_KEY=b"})
    settings.save_env({"GEMINI_API_KEY": ""})
    assert "GEMINI_API_KEY" not in settings.read_env_file()
    merged = settings.save_prefs({"llm": {"provider": "ollama"}})
    assert merged["llm"]["provider"] == "ollama" and merged["llm"]["gemini_model"]  # deep merge keeps defaults


def test_sfx_auto_cues(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sfx, "ensure_library", lambda: {n: Path(f"{n}.wav") for n in sfx.RECIPES})
    timing = {"scenes": [{"start": 0, "end": 2}, {"start": 2, "end": 5}, {"start": 5, "end": 8}]}
    scenes = [{"visual": {"type": "headline"}}, {"visual": {"type": "stat"}}, {"visual": {"type": "quote"}}]
    cues = sfx.auto_cues(timing, scenes, "vox")
    names = [Path(c["file"]).stem for c in cues]
    assert names == ["paper_flip", "click", "paper_flip"]  # 2 transitions + 1 reveal on the stat
    cues = sfx.auto_cues(timing, scenes, "concept", blueprint_cues=["pop", "unknown", "ding"])
    assert [Path(c["file"]).stem for c in cues] == ["pop", "ding", "pop"]


def test_cover_text() -> None:
    assert cover_text_for({"cover_text": "Big hook here now please extra"}) == "Big hook here now please"
    assert cover_text_for({"title": "T", "scenes": [{"visual": {"heading": "First heading"}}]}) == "First heading"
    assert cover_text_for({"cover_text": ""}) == ""


def test_crop_expr_per_shot() -> None:
    expr = crop_x_expr([(0.0, 0.5), (3.2, 0.25)], "min(iw,ih*1080/1920)")
    assert expr.startswith("if(gte(t,0.000)") and "gte(t,3.200)" in expr and "0.2500*iw" in expr
    assert "ow" not in expr  # crop width substituted


def test_ui_requires_token_and_blocks_traversal() -> None:
    from fastapi.testclient import TestClient

    from ui import server

    c = TestClient(server.app, base_url="http://127.0.0.1:8765")
    assert c.get("/api/projects").status_code == 401
    assert c.get("/", headers={"host": "evil.example"}).status_code == 400
    page = c.get("/").text
    assert server.TOKEN in page
    h = {"X-VF-Token": server.TOKEN}
    assert c.get("/api/options", headers=h).status_code == 200
    assert c.get("/files/.env", params={"t": server.TOKEN}).status_code == 404
    assert c.put("/api/settings/secrets", headers=h, json={"EVIL": "x"}).status_code == 400
    assert c.post("/api/analyze", headers=h, json={"urls": ["file:///etc/passwd"]}).status_code == 400
