"""Library: HTTP 206 streaming, paginated search, output layout migration."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from common import db, paths, read_json, write_json
from scripts import migrate_output as mig
from ui import server
from ui.streaming import parse_range

BODY = bytes(range(256)) * 40  # 10240 bytes


@pytest.fixture
def lib(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    out, proj = tmp_path / "output", tmp_path / "projects"
    for mod, name, val in ((paths, "OUTPUT", out), (server, "ROOT", tmp_path), (server, "PROJECTS", proj),
                           (db, "DB_PATH", tmp_path / "data" / "projects.db")):  # fmt: skip
        monkeypatch.setattr(mod, name, val)
    for i in range(15):
        slug = f"video-{i:02d}"
        d = out / slug
        d.mkdir(parents=True)
        (d / f"{slug}.mp4").write_bytes(BODY)
        write_json(
            d / f"{slug}.meta.json",
            {
                "slug": slug,
                "title": f"Title {'cats' if i % 5 == 0 else 'dogs'} {i}",
                "aspect_ratio": "16:9" if i % 2 else "9:16",
            },
        )
        write_json(
            proj / slug / "script.json",
            {
                "style": "whiteboard" if i < 3 else "vox_documentary",
                "claims": [{"text": "x 5", "verified": False}] if i == 1 else [],
            },
        )
    return TestClient(server.app, base_url="http://127.0.0.1:8765")


H = {"X-VF-Token": server.TOKEN}


def test_parse_range_cases() -> None:
    assert parse_range(None, 100) is None
    assert parse_range("bytes=0-9", 100) == (0, 9)
    assert parse_range("bytes=90-", 100) == (90, 99)
    assert parse_range("bytes=-10", 100) == (90, 99)
    assert parse_range("bytes=50-500", 100) == (50, 99)
    for bad in ("bytes=100-", "bytes=9-3", "items=0-1", "bytes=-"):
        with pytest.raises(ValueError):
            parse_range(bad, 100)


def test_stream_returns_206_with_content_range(lib: TestClient) -> None:
    r = lib.get("/api/projects/video-00/stream", headers={**H, "Range": "bytes=100-199"})
    assert r.status_code == 206 and r.content == BODY[100:200]
    assert r.headers["content-range"] == f"bytes 100-199/{len(BODY)}" and r.headers["accept-ranges"] == "bytes"
    tail = lib.get("/api/projects/video-00/stream", headers={**H, "Range": "bytes=-16"})
    assert tail.status_code == 206 and tail.content == BODY[-16:]
    full = lib.get("/api/projects/video-00/stream", headers=H)
    assert full.status_code == 200 and full.content == BODY and full.headers["accept-ranges"] == "bytes"
    assert lib.get("/api/projects/video-00/stream", headers={**H, "Range": "bytes=99999-"}).status_code == 416
    assert lib.get("/api/projects/nope/stream", headers=H).status_code == 404


def test_stream_accepts_token_in_query_for_video_tag(lib: TestClient) -> None:
    r = lib.get("/api/projects/video-00/stream", params={"t": server.TOKEN}, headers={"Range": "bytes=0-3"})
    assert r.status_code == 206 and r.content == BODY[:4]


def test_download_is_an_attachment(lib: TestClient) -> None:
    r = lib.get("/api/projects/video-03/download", headers=H)
    assert r.status_code == 200 and r.headers["content-disposition"] == 'attachment; filename="video-03.mp4"'
    assert r.content == BODY


def test_list_is_paginated_searchable_and_filterable(lib: TestClient) -> None:
    first = lib.get("/api/library", headers=H, params={"per_page": 6}).json()
    assert first["total"] == 15 and first["pages"] == 3 and len(first["items"]) == 6
    assert all("meta" not in i for i in first["items"])  # list rows are light: no per-item video/thumbnail payload
    last = lib.get("/api/library", headers=H, params={"per_page": 6, "page": 3}).json()
    assert len(last["items"]) == 3
    cats = lib.get("/api/library", headers=H, params={"q": "CATS"}).json()
    assert cats["total"] == 3 and all("cats" in i["title"] for i in cats["items"])
    wide = lib.get("/api/library", headers=H, params={"aspect": "16:9"}).json()
    assert wide["total"] == 7
    assert lib.get("/api/library", headers=H, params={"style": "whiteboard"}).json()["total"] == 3


def test_detail_has_stream_url_and_fact_banner_data(lib: TestClient) -> None:
    d = lib.get("/api/library/video-01", headers=H).json()
    assert d["stream"] == "/api/projects/video-01/stream" and d["unverified"] == 1
    assert d["claims"][0]["verified"] is False
    assert lib.get("/api/library/missing", headers=H).status_code == 404


def test_migration_moves_files_rewrites_meta_and_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "output"
    out.mkdir()
    for mod, name, val in ((mig, "OUTPUT", out), (mig, "ROOT", tmp_path), (mig, "PROJECTS", tmp_path / "projects"),
                           (db, "DB_PATH", tmp_path / "data" / "projects.db")):  # fmt: skip
        monkeypatch.setattr(mod, name, val)
    (out / "old-video.mp4").write_bytes(b"mp4")
    (out / "old-video.thumb.jpg").write_bytes(b"jpg")
    write_json(
        out / "old-video.meta.json",
        {
            "title": "Old video",
            "file": "output/old-video.mp4",
            "thumbnail": "output/old-video.thumb.jpg",
            "aspect_ratio": "9:16",
        },
    )
    state = tmp_path / "scheduler" / "state.sqlite"
    state.parent.mkdir()
    with closing(sqlite3.connect(state)) as conn:
        conn.execute("CREATE TABLE jobs (id TEXT, meta_path TEXT)")
        conn.execute("INSERT INTO jobs VALUES ('j1', 'output\\old-video.meta.json')")
        conn.commit()
    (tmp_path / "scheduler" / "schedule.yaml").write_text(
        "jobs:\n- id: j2\n  meta: output/old-video.meta.json\n", encoding="utf-8"
    )

    for line in mig.migrate_one("old-video", dry=True):
        assert line.startswith("  move")
    assert (out / "old-video.mp4").exists()  # dry run changes nothing

    mig.migrate_one("old-video", dry=False)
    mig.repoint_state(dry=False)
    assert (out / "old-video" / "old-video.mp4").read_bytes() == b"mp4" and not (out / "old-video.mp4").exists()
    meta = read_json(out / "old-video" / "old-video.meta.json")
    assert (
        meta["file"] == "output/old-video/old-video.mp4" and meta["thumbnail"] == "output/old-video/old-video.thumb.jpg"
    )
    with closing(sqlite3.connect(state)) as conn:
        assert conn.execute("SELECT meta_path FROM jobs").fetchone()[0] == "output/old-video/old-video.meta.json"
    assert "output/old-video/old-video.meta.json" in (tmp_path / "scheduler" / "schedule.yaml").read_text(
        encoding="utf-8"
    )
    assert db.list_projects()[0]["id"] == "old-video"
    assert mig.migrate_one("old-video", dry=False) == []  # second run is a no-op
