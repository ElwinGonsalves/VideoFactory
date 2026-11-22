"""Batch spreadsheets: parse, validate and preview .xlsx / .csv / public Google Sheets.

Columns (header row, any order, case-insensitive):
    input_mode, title, content, style, aspect_ratio, music_mood, voice, auto_publish, platforms, schedule_at
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import requests

from common import settings
from pipeline.router import ROUTES

COLUMNS = [
    "input_mode",
    "title",
    "content",
    "style",
    "aspect_ratio",
    "music_mood",
    "voice",
    "auto_publish",
    "platforms",
    "schedule_at",
]
MOODS = ("chill", "documentary", "upbeat", "dramatic")
ASPECTS = ("9:16", "16:9", "1:1")
PLATFORMS = ("youtube", "instagram", "tiktok")
MAX_ROWS = 100
INTERVALS = {"30m": 30, "45m": 45, "1h": 60, "2h": 120, "4h": 240}
SAMPLE = [
    ["idea", "Why Costco sells $1.50 hot dogs", "Explain the loss-leader strategy behind the Costco hot dog", "concept_explainer",
     "9:16", "documentary", "", "no", "youtube", ""],
    ["script", "The honest world", "What if nobody could ever lie? Honesty sounds great.\n\nNow picture a world where every sentence is true.",
     "whiteboard", "9:16", "chill", "", "yes", "youtube,instagram", "2026-12-01 20:00"],
]  # fmt: skip


def sheets_csv_url(url: str) -> str:
    """https://docs.google.com/spreadsheets/d/<id>/edit#gid=<n> -> .../export?format=csv&gid=<n>."""
    m = re.match(r"https://docs\.google\.com/spreadsheets/d/([\w-]+)", url.strip())
    if not m:
        raise ValueError("not a Google Sheets link (expected https://docs.google.com/spreadsheets/d/...)")
    gid = re.search(r"[#&?]gid=(\d+)", url)
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv" + (
        f"&gid={gid.group(1)}" if gid else ""
    )


def fetch_google_sheet(url: str) -> list[dict[str, str]]:
    res = requests.get(sheets_csv_url(url), timeout=30)
    if res.status_code in (401, 403) or "accounts.google.com" in res.url:
        raise ValueError("the sheet is private: share it as 'Anyone with the link can view'")
    if not res.ok:
        raise ValueError(f"Google Sheets answered HTTP {res.status_code}")
    return read_csv(res.content)


def read_csv(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig", errors="replace")
    return [
        {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        for row in csv.DictReader(io.StringIO(text))
    ]


def read_xlsx(raw: bytes) -> list[dict[str, str]]:
    from openpyxl import load_workbook

    ws = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    head = [str(h or "").strip().lower() for h in rows[0]]
    out = []
    for r in rows[1:]:
        if not any(c not in (None, "") for c in r):
            continue
        out.append(
            {
                h: ("" if c is None else (c.strftime("%Y-%m-%d %H:%M") if isinstance(c, datetime) else str(c).strip()))
                for h, c in zip(head, r, strict=False)
                if h
            }
        )
    return out


def read_upload(name: str, raw: bytes) -> list[dict[str, str]]:
    low = name.lower()
    if low.endswith(".xlsx"):
        return read_xlsx(raw)
    if low.endswith(".csv"):
        return read_csv(raw)
    raise ValueError("upload an .xlsx or .csv file")


def sample_xlsx() -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "videos"
    ws.append(COLUMNS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in SAMPLE:
        ws.append(row)
    for col, width in zip("ABCDEFGHIJ", (11, 32, 60, 20, 13, 14, 22, 13, 20, 18), strict=True):
        ws.column_dimensions[col].width = width
    notes = wb.create_sheet("README")
    notes.append(["column", "meaning"])
    for line in (
        ("input_mode", "idea = the AI writes the script from `content`; script = `content` is kept word for word"),
        ("title", "video title; the project folder name is made from it"),
        ("style", "e.g. concept_explainer, case_study, vox_documentary, whiteboard, hand_drawn, stickman, long_form"),
        ("aspect_ratio", "9:16, 16:9 or 1:1 (long_form is always 16:9)"),
        ("music_mood", "chill, documentary, upbeat or dramatic"),
        ("voice", "empty = your Settings default, e.g. en-US-AndrewNeural"),
        ("auto_publish", "yes/no: upload after rendering"),
        ("platforms", "youtube,instagram,tiktok (comma separated)"),
        ("schedule_at", "optional local time like 2026-12-01 20:00; empty = use the relative interval"),
    ):
        notes.append(list(line))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _truthy(v: str) -> bool:
    return v.strip().lower() in ("1", "yes", "y", "true", "on", "x")


def parse_time(value: str, tz: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("/", "-"))
    except ValueError:
        raise ValueError(f"schedule_at '{value}' is not a date/time like 2026-12-01 20:00") from None
    return dt if dt.tzinfo else dt.replace(tzinfo=ZoneInfo(tz))


def validate_rows(rows: list[dict[str, str]], tz: str = "Asia/Kolkata") -> list[dict[str, Any]]:
    """Per-row result: {row, ok, errors, warnings, data}. Never raises on bad content."""
    d = settings.load()["defaults"]
    out = []
    for i, raw in enumerate(rows[:MAX_ROWS], start=2):  # row 1 is the header
        errors: list[str] = []
        mode = (raw.get("input_mode") or "idea").lower()
        if mode not in ("idea", "script"):
            errors.append("input_mode must be idea or script")
        content = raw.get("content", "")
        if not content:
            errors.append("content is empty")
        elif mode == "script" and len(content.split()) < 8:
            errors.append("script content is too short (min 8 words)")
        style = raw.get("style") or d["style"]
        if style not in ROUTES:
            errors.append(f"unknown style '{style}'")
        aspect = raw.get("aspect_ratio") or d["aspect_ratio"]
        if aspect not in ASPECTS:
            errors.append(f"aspect_ratio must be one of {', '.join(ASPECTS)}")
        mood = (raw.get("music_mood") or d["music_mood"]).lower()
        if mood not in MOODS:
            errors.append(f"music_mood must be one of {', '.join(MOODS)}")
        platforms = [p.strip().lower() for p in re.split(r"[,;\s]+", raw.get("platforms", "")) if p.strip()] or [
            "youtube"
        ]
        bad = [p for p in platforms if p not in PLATFORMS]
        if bad:
            errors.append(f"unknown platform(s): {', '.join(bad)}")
        schedule_at = None
        try:
            schedule_at = parse_time(raw.get("schedule_at", ""), tz)
        except ValueError as exc:
            errors.append(str(exc))
        out.append(
            {
                "row": i,
                "ok": not errors,
                "errors": errors,
                "data": {
                    "input_mode": mode,
                    "title": raw.get("title", "")[:100],
                    "content": content,
                    "style": style,
                    "aspect_ratio": "16:9" if style == "long_form" else aspect,
                    "music_mood": mood,
                    "voice": raw.get("voice", ""),
                    "auto_publish": _truthy(raw.get("auto_publish", "")),
                    "platforms": platforms,
                    "schedule_at": schedule_at.isoformat() if schedule_at else "",
                },
            }
        )
    if len(rows) > MAX_ROWS:
        out.append(
            {"row": MAX_ROWS + 2, "ok": False, "errors": [f"only the first {MAX_ROWS} rows are used"], "data": {}}
        )
    return out


def parse_interval(value: str) -> timedelta:
    """'30m', '45m', '1h', '2h', '4h' or custom like '90m', '1.5h', '3 hr'."""
    v = value.strip().lower().replace(" ", "")
    if v in INTERVALS:
        return timedelta(minutes=INTERVALS[v])
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(m|min|h|hr)", v)
    if not m or float(m.group(1)) <= 0:
        raise ValueError(f"interval '{value}' must look like 30m, 90m or 1.5h")
    n = float(m.group(1))
    return timedelta(minutes=n if m.group(2) in ("m", "min") else n * 60)


def upload_times(rows: list[dict[str, Any]], start: datetime, interval: timedelta) -> list[datetime | None]:
    """Upload time per row: its own schedule_at, else start + k * interval counted over auto_publish rows."""
    times: list[datetime | None] = []
    k = 0
    for r in rows:
        d = r["data"]
        if not d.get("auto_publish"):
            times.append(None)
        elif d.get("schedule_at"):
            times.append(datetime.fromisoformat(d["schedule_at"]))
        else:
            times.append(start + interval * k)
            k += 1
    return times
