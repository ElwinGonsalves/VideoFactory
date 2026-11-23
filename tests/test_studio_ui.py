"""Studio v3 backend: pill/drawer progress parsing, engines, onboarding/demo endpoints, the React shell
routes, and the OneDrive-safe Remotion public mirror."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pipeline import render
from ui import server, studio

H = {"X-VF-Token": server.TOKEN}


@pytest.fixture
def client() -> TestClient:
    return TestClient(server.app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)


# ------------------------------------------------------------------ parse_progress
def test_progress_llm_and_non_pipeline_jobs() -> None:
    assert studio.parse_progress("llm", "", "running")["node"] == "script"
    assert studio.parse_progress("llm", "", "done") == {
        "node": "script",
        "node_index": 0,
        "percent": 100,
        "done_nodes": ["script"],
    }
    assert studio.parse_progress("publish", "anything", "running")["node"] is None


def test_progress_maps_make_video_steps_to_nodes() -> None:
    assert studio.parse_progress("render", "starting", "running")["node"] == "script"
    music = studio.parse_progress("render", "[1/6] voice\n[2/6] music bed", "running")
    assert music["node"] == "music" and music["done_nodes"] == ["script", "voice"] and music["percent"] == 20
    qa = studio.parse_progress("render", "[6/6] validating", "running")
    assert qa["node"] == "qa" and qa["node_index"] == 4


def test_progress_uses_remotion_frame_counter_inside_render_step() -> None:
    log = "[4/6] stills\nRendered 900/1500\n[5/6] final render\nRendered 375/1500\nRendered 750/1500\n"
    p = studio.parse_progress("render", log, "running")
    # step 5 spans 42..92 %; half the frames is 67 %. The QA-stills counter before [5/6] is ignored.
    assert p["node"] == "render" and p["percent"] == 67 and p["done_nodes"] == ["script", "voice", "music"]


def test_progress_done_lights_every_node() -> None:
    p = studio.parse_progress("smoke", "[3/6] route", "done")
    assert p["percent"] == 100 and p["done_nodes"] == studio.NODES


# ------------------------------------------------------------------ engines
def test_engines_summary_counts_required() -> None:
    data = [
        {"ok": True, "required": True},
        {"ok": False, "required": False},
        {"ok": True, "required": False},
    ]
    assert studio.engines_summary(data) == {"alive": 2, "total": 3, "required_ok": True}
    data[0]["ok"] = False
    assert studio.engines_summary(data)["required_ok"] is False


def test_engines_endpoint_lists_the_stitched_organs(client: TestClient) -> None:
    res = client.get("/api/engines", headers=H)
    assert res.status_code == 200
    body = res.json()
    keys = {e["key"] for e in body["engines"]}
    assert {"remotion", "ffmpeg", "whisper", "playwright"} <= keys
    assert body["total"] == len(body["engines"]) and 0 <= body["alive"] <= body["total"]
    for e in body["engines"]:
        assert set(e) >= {"key", "name", "organ", "role", "ok", "detail", "required"}


# ------------------------------------------------------------------ studio / onboarding / demo
def test_studio_status_shape(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_upcoming", lambda limit=6: ([], 0))
    res = client.get("/api/studio", headers=H)
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"now", "running", "queued", "upcoming", "scheduled", "recent", "daemon", "nodes"}
    assert [n["id"] for n in body["nodes"]] == studio.NODES
    assert body["upcoming"] == [] and body["scheduled"] == 0


def test_studio_requires_token(client: TestClient) -> None:
    assert client.get("/api/studio").status_code == 401


def test_onboarding_reports_key_and_demo(client: TestClient) -> None:
    body = client.get("/api/onboarding", headers=H).json()
    assert {"provider", "key_name", "key_set", "engines", "projects", "rendered", "demo"} <= set(body)
    assert set(body["demo"]) == {"sample_short", "can_render_sample", "sample_project", "blueprint"}
    assert isinstance(body["key_set"], bool)


def test_demo_batch_validates_sample_rows(client: TestClient) -> None:
    body = client.get("/api/demo/batch", headers=H).json()
    assert body["sample"] is True and body["raw"]
    assert len(body["results"]) == len(body["raw"])


# ------------------------------------------------------------------ shell routes
def test_classic_ui_is_kept(client: TestClient) -> None:
    res = client.get("/classic")
    assert res.status_code == 200 and "__VF_TOKEN__" not in res.text and server.TOKEN in res.text


def test_style_cards_cannot_escape_their_folder(client: TestClient) -> None:
    assert client.get("/styles/..%2Fserver.py").status_code == 404
    assert client.get("/assets/..%2F..%2Fserver.py").status_code == 404
    if (server.DIST / "styles" / "concept.webp").exists():
        assert client.get("/styles/concept.webp").status_code == 200


# ------------------------------------------------------------------ OneDrive-safe public dir
@pytest.mark.skipif(os.name != "nt", reason="the mirror only exists on Windows")
def test_public_dir_mirrors_onedrive_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    studio_dir = tmp_path / "OneDrive" / "studio"
    (studio_dir / "public" / "fonts").mkdir(parents=True)
    (studio_dir / "public" / "fonts" / "a.ttf").write_bytes(b"x" * 1000)
    home = tmp_path / "home"
    monkeypatch.setattr(render, "STUDIO", studio_dir)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    stale = home / ".video-factory" / "remotion-public" / "old.png"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")

    dest = render.public_dir()

    assert dest == home / ".video-factory" / "remotion-public"
    assert (dest / "fonts" / "a.ttf").read_bytes() == b"x" * 1000
    assert not stale.exists()


@pytest.mark.skipif(os.name != "nt", reason="the mirror only exists on Windows")
def test_public_dir_outside_onedrive_is_used_directly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    studio_dir = tmp_path / "plain" / "studio"
    (studio_dir / "public").mkdir(parents=True)
    (studio_dir / "public" / "a.txt").write_text("a", encoding="utf-8")
    monkeypatch.setattr(render, "STUDIO", studio_dir)
    assert render.public_dir() == studio_dir / "public"
