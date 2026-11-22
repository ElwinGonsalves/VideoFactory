"""Batch sheets: parsing, validation, relative upload times, and the one-at-a-time runner."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

import make_video
from batch import run as batch_run
from batch import sheet
from common import db, paths, write_json
from scheduler import jobs as sched_jobs
from ui import server

TZ = ZoneInfo("Asia/Kolkata")


def test_sample_excel_round_trips_and_validates() -> None:
    rows = sheet.read_upload("sample.xlsx", sheet.sample_xlsx())
    assert list(rows[0]) == sheet.COLUMNS and len(rows) == 2
    results = sheet.validate_rows(rows)
    assert all(r["ok"] for r in results), [r["errors"] for r in results]
    assert results[1]["data"]["auto_publish"] is True and results[1]["data"]["platforms"] == ["youtube", "instagram"]
    assert results[1]["data"]["schedule_at"].startswith("2026-12-01T20:00")


def test_validation_reports_each_problem() -> None:
    rows = [{"input_mode": "poem", "content": "", "style": "nope", "aspect_ratio": "4:3", "music_mood": "loud",
             "platforms": "myspace", "schedule_at": "tomorrow-ish"}]  # fmt: skip
    errors = " | ".join(sheet.validate_rows(rows)[0]["errors"])
    for needle in (
        "input_mode",
        "content is empty",
        "unknown style",
        "aspect_ratio",
        "music_mood",
        "platform",
        "schedule_at",
    ):
        assert needle in errors
    short = sheet.validate_rows([{"input_mode": "script", "content": "too short"}])[0]
    assert not short["ok"] and "too short" in short["errors"][0]
    assert (
        sheet.validate_rows([{"content": "x idea", "style": "long_form", "aspect_ratio": "9:16"}])[0]["data"][
            "aspect_ratio"
        ]
        == "16:9"
    )


def test_csv_and_google_sheet_links() -> None:
    raw = b"\xef\xbb\xbfInput_Mode,Title,Content\nidea,T,Explain tides\n"
    assert sheet.read_csv(raw) == [{"input_mode": "idea", "title": "T", "content": "Explain tides"}]
    url = "https://docs.google.com/spreadsheets/d/AbC-123_x/edit?usp=sharing#gid=77"
    assert sheet.sheets_csv_url(url) == "https://docs.google.com/spreadsheets/d/AbC-123_x/export?format=csv&gid=77"
    assert sheet.sheets_csv_url("https://docs.google.com/spreadsheets/d/AbC/edit").endswith("/AbC/export?format=csv")
    with pytest.raises(ValueError):
        sheet.sheets_csv_url("https://example.com/sheet")
    with pytest.raises(ValueError):
        sheet.read_upload("x.txt", b"")


def test_private_sheet_message(monkeypatch: pytest.MonkeyPatch) -> None:
    class R:
        status_code, url, ok, content = 403, "https://docs.google.com/x", False, b""

    monkeypatch.setattr(sheet.requests, "get", lambda *a, **k: R())
    with pytest.raises(ValueError, match="Anyone with the link"):
        sheet.fetch_google_sheet("https://docs.google.com/spreadsheets/d/abc/edit")


def test_intervals_and_upload_times() -> None:
    from datetime import timedelta

    assert sheet.parse_interval("45m") == timedelta(minutes=45) and sheet.parse_interval("4h") == timedelta(hours=4)
    assert sheet.parse_interval("1.5h") == timedelta(minutes=90) and sheet.parse_interval("90 min") == timedelta(
        minutes=90
    )
    for bad in ("soon", "0m", "-5m"):
        with pytest.raises(ValueError):
            sheet.parse_interval(bad)
    rows = [{"data": {"auto_publish": True}}, {"data": {"auto_publish": False}},
            {"data": {"auto_publish": True, "schedule_at": "2026-12-01T20:00:00+05:30"}}, {"data": {"auto_publish": True}}]  # fmt: skip
    start = datetime(2026, 11, 30, 22, 0, tzinfo=TZ)
    times = sheet.upload_times(rows, start, timedelta(hours=2))
    assert times[0] == start and times[1] is None
    assert times[2].isoformat() == "2026-12-01T20:00:00+05:30"
    assert times[3] == start + timedelta(hours=2)  # the explicit row does not consume a slot


def test_batch_endpoints() -> None:
    c = TestClient(server.app, base_url="http://127.0.0.1:8765")
    h = {"X-VF-Token": server.TOKEN}
    sample = c.get("/api/batch/sample", headers=h)
    assert sample.status_code == 200 and "attachment" in sample.headers["content-disposition"]
    prev = c.post("/api/batch/preview-file", headers=h, files={"file": ("a.xlsx", sheet.sample_xlsx())})
    assert prev.status_code == 200 and all(r["ok"] for r in prev.json()["results"])
    assert c.post("/api/batch/preview-file", headers=h, files={"file": ("a.txt", b"hi")}).status_code == 400
    bad = c.post("/api/batch/run", headers=h, json={"raw": [{"content": ""}], "interval": "1h"})
    assert bad.status_code == 400
    assert (
        c.post("/api/batch/run", headers=h, json={"raw": prev.json()["raw"], "interval": "whenever"}).status_code == 400
    )


def test_runner_renders_one_at_a_time_and_survives_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "projects.db")
    monkeypatch.setattr(batch_run, "PROJECTS", tmp_path / "projects")
    monkeypatch.setattr(sched_jobs, "SCHEDULE", tmp_path / "schedule.yaml")
    monkeypatch.setattr("common.slugs.PROJECTS", tmp_path / "projects")
    monkeypatch.setattr("common.slugs.OUTPUT", tmp_path / "output")
    monkeypatch.setattr(paths, "OUTPUT", tmp_path / "output")
    active = {"n": 0, "max": 0}
    order: list[str] = []

    def fake_script(d: dict[str, Any]) -> dict[str, Any]:
        if d["content"] == "boom":
            raise RuntimeError("model down")
        return {"title": f"Video about {d['content']}", "aspect_ratio": "9:16", "scenes": [{"narration": "n"}]}

    def fake_produce(project: Path) -> dict[str, Any]:
        active["n"] += 1
        active["max"] = max(active["max"], active["n"])
        order.append(project.name)
        meta = paths.meta_path(project.name)
        write_json(meta, {"slug": project.name})
        active["n"] -= 1
        return {}

    monkeypatch.setattr(batch_run, "build_script", fake_script)
    monkeypatch.setattr(make_video, "produce", fake_produce)
    row = {"input_mode": "idea", "title": "", "style": "concept_explainer", "aspect_ratio": "9:16", "music_mood": "chill",
           "voice": "", "platforms": ["youtube"], "schedule_at": ""}  # fmt: skip
    spec = {"rows": [{"data": {**row, "content": "tides", "auto_publish": True}, "upload_at": "2026-12-01T20:00:00+05:30"},
                     {"data": {**row, "content": "boom", "auto_publish": False}, "upload_at": None},
                     {"data": {**row, "content": "moons", "auto_publish": False}, "upload_at": None}]}  # fmt: skip
    write_json(tmp_path / "batch.json", spec)
    assert batch_run.main([str(tmp_path / "batch.json")]) == 1  # one row failed
    assert order == ["video-about-tides", "video-about-moons"] and active["max"] == 1
    job = sched_jobs.read()["jobs"][0]
    assert (
        job["type"] == "upload_only"
        and job["upload_at"] == "2026-12-01T20:00:00+05:30"
        and job["platforms"] == ["youtube"]
    )
    assert {p["id"] for p in db.list_projects()} == {"video-about-tides", "video-about-moons"}
