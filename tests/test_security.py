"""Regression tests for the security review fixes. None of these write user settings or the schedule:
each request is rejected before anything is saved."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from analyzer import sync_analytics
from batch import sheet
from ui import server

H = {"X-VF-Token": server.TOKEN}


@pytest.fixture
def client() -> TestClient:
    return TestClient(server.app, base_url="http://127.0.0.1:8765", raise_server_exceptions=False)


# ------------------------------------------------------------------ origin, framing, token
@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:9999", "https://evil.example"])
def test_cross_origin_requests_are_refused(client: TestClient, origin: str) -> None:
    # another app on this machine must not be able to read "/" (it embeds the session token)
    assert client.get("/", headers={"Origin": origin}).status_code == 403
    assert client.get("/api/studio", headers={**H, "Origin": origin}).status_code == 403


def test_same_origin_requests_still_work(client: TestClient) -> None:
    res = client.get("/api/onboarding", headers={**H, "Origin": "http://127.0.0.1:8765"})
    assert res.status_code == 200


def test_pages_cannot_be_framed(client: TestClient) -> None:
    res = client.get("/")
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]


def test_non_ascii_token_is_401_not_500(client: TestClient) -> None:
    assert client.get("/api/studio?t=%C3%A9t%C3%A9").status_code == 401


# ------------------------------------------------------------------ argument injection / file exfiltration
def test_analyze_refuses_non_video_local_files(client: TestClient) -> None:
    env = str(server.ROOT / ".env.example")
    res = client.post("/api/analyze", headers=H, json={"urls": [env]})
    assert res.status_code == 400 and "video file" in res.json()["detail"]


def test_channel_url_must_be_a_web_url(client: TestClient) -> None:
    res = client.put("/api/settings/prefs", headers=H, json={"analytics": {"channel_url": "--exec calc.exe"}})
    assert res.status_code == 400


def test_yt_dlp_never_receives_an_option_as_url() -> None:
    with pytest.raises(ValueError):
        sync_analytics._web_url("--exec calc.exe")
    assert sync_analytics._web_url(" https://youtube.com/@x ") == "https://youtube.com/@x"


@pytest.mark.parametrize(
    "body",
    [
        {"id": "sec-test-a", "type": "upload_only", "meta": "../.env.meta.json"},
        {"id": "sec-test-b", "type": "upload_only", "meta": "config/x.json"},
        {"id": "sec-test-c", "script_or_prompt": "../../Windows/win.ini/script.json"},
        {"id": "sec-test-d", "type": "rm -rf"},
        {"id": "sec-test-e", "project": "../x"},
    ],
)
def test_schedule_jobs_stay_inside_the_project(client: TestClient, body: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    def never(_data: dict) -> None:
        raise AssertionError("must be rejected before scheduler/schedule.yaml is written")

    monkeypatch.setattr(server, "_write_schedule", never)
    assert client.post("/api/schedule/jobs", headers=H, json=body).status_code == 400


# ------------------------------------------------------------------ spreadsheet limits
def test_xlsx_reading_stops_after_max_rows() -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(sheet.COLUMNS)
    for i in range(sheet.MAX_ROWS + 50):
        ws.append(["idea", f"t{i}", "content"])
    buf = io.BytesIO()
    wb.save(buf)
    rows = sheet.read_xlsx(buf.getvalue())
    assert len(rows) == sheet.MAX_ROWS + 1  # one extra, so validation can warn


def test_csv_cells_are_capped() -> None:
    raw = ("input_mode,title,content\nidea,t," + "x" * (sheet.MAX_CELL + 500) + "\n").encode()
    rows = sheet.read_csv(raw)
    assert len(rows[0]["content"]) == sheet.MAX_CELL


def test_google_sheet_download_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    class Big:
        status_code, url, ok = 200, "https://docs.google.com/x", True

        def iter_content(self, n: int):  # noqa: ANN201
            while True:
                yield b"a" * n

    monkeypatch.setattr(sheet.requests, "get", lambda *a, **k: Big())
    with pytest.raises(ValueError, match="larger than 5 MB"):
        sheet.fetch_google_sheet("https://docs.google.com/spreadsheets/d/abc/edit")
