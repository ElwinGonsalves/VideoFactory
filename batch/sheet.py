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

from common import settings, voices
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
    "language",
    "length",
]
MOODS = ("chill", "documentary", "upbeat", "dramatic")
# Friendly spellings people type into sheets, mapped to the real values (so a row is never lost to wording).
STYLE_ALIASES = {
    "concept": "concept_explainer", "explainer": "concept_explainer", "case": "case_study", "casestudy": "case_study",
    "kinetic": "kinetic_type", "kinetic_typography": "kinetic_type", "vox": "vox_documentary", "documentary": "vox_documentary",
    "map": "editorial_map", "maps": "editorial_map", "news": "news_breakdown", "notebook": "hand_drawn", "handdrawn": "hand_drawn",
    "graphite": "sketch", "pencil": "sketch", "stick_man": "stickman", "stick_figure": "stickman", "longform": "long_form",
    "long": "long_form", "youtube": "long_form", "math": "math_science", "manim": "math_science", "blueprint": "reference_blueprint",
}  # fmt: skip
ASPECT_ALIASES = {"9x16": "9:16", "916": "9:16", "vertical": "9:16", "portrait": "9:16", "short": "9:16", "shorts": "9:16",
                  "reel": "9:16", "16x9": "16:9", "169": "16:9", "landscape": "16:9", "wide": "16:9", "horizontal": "16:9",
                  "1x1": "1:1", "11": "1:1", "square": "1:1"}  # fmt: skip
PLATFORM_ALIASES = {
    "yt": "youtube",
    "ig": "instagram",
    "insta": "instagram",
    "reels": "instagram",
    "tt": "tiktok",
    "tik_tok": "tiktok",
}


def _key(v: str) -> str:
    return re.sub(r"[\s\-]+", "_", v.strip().lower())


ASPECTS = ("9:16", "16:9", "1:1")
PLATFORMS = ("youtube", "instagram", "tiktok")
MAX_ROWS = 100
MAX_CELL = 20_000  # characters; a long script is ~1,500
MAX_BYTES = 5 * 1024 * 1024
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
    res = requests.get(sheets_csv_url(url), timeout=30, stream=True)
    try:
        if res.status_code in (401, 403) or "accounts.google.com" in res.url:
            raise ValueError("the sheet is private: share it as 'Anyone with the link can view'")
        if not res.ok:
            raise ValueError(f"Google Sheets answered HTTP {res.status_code}")
        body = bytearray()
        for chunk in res.iter_content(64 * 1024):  # stop reading at the limit instead of buffering it all
            body += chunk
            if len(body) > MAX_BYTES:
                raise ValueError("the sheet is larger than 5 MB")
    finally:
        close = getattr(res, "close", None)
        if close:
            close()
    return read_csv(bytes(body))


def read_csv(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig", errors="replace")
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        # csv.DictReader puts surplus cells under a None key as a list; str() keeps them harmless.
        out.append({(k or "").strip().lower(): _cell(str(v or "")) for k, v in row.items() if k})
        if len(out) > MAX_ROWS:
            break
    return out


def read_xlsx(raw: bytes) -> list[dict[str, str]]:
    from openpyxl import load_workbook

    ws = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active
    # Stream the rows and stop early: a small .xlsx can claim millions of rows or huge cells.
    it = ws.iter_rows(values_only=True, max_col=len(COLUMNS) + 10)
    first = next(it, None)
    if first is None:
        return []
    head = [str(h or "").strip().lower() for h in first]
    out = []
    for r in it:
        if not any(c not in (None, "") for c in r):
            continue
        out.append(
            {
                h: _cell("" if c is None else (c.strftime("%Y-%m-%d %H:%M") if isinstance(c, datetime) else str(c)))
                for h, c in zip(head, r, strict=False)
                if h
            }
        )
        if len(out) > MAX_ROWS:  # one extra row so validate_rows can say "only the first 100 rows are used"
            break
    return out


def _cell(value: str) -> str:
    return value.strip()[:MAX_CELL]


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
    for col, width in zip("ABCDEFGHIJKL", (11, 32, 60, 20, 13, 14, 22, 13, 20, 18, 12, 9), strict=True):
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
        ("language", "optional: english, hinglish (Roman script) or hindi (Devanagari); empty = your Settings default"),
        ("length", "optional, idea rows: 45, 45s or 3m (15 s to 30 min); empty = your Settings default"),
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
        style = _key(raw.get("style") or d["style"])
        style = STYLE_ALIASES.get(style.replace("_", ""), STYLE_ALIASES.get(style, style))
        if style not in ROUTES:
            errors.append(
                f"unknown style '{raw.get('style')}' (try concept_explainer, case_study, whiteboard, stickman...)"
            )
        aspect = (raw.get("aspect_ratio") or d["aspect_ratio"]).strip().lower()
        aspect = ASPECT_ALIASES.get(aspect.replace(" ", ""), aspect)
        if aspect not in ASPECTS:
            errors.append(f"aspect_ratio must be one of {', '.join(ASPECTS)}")
        mood = (raw.get("music_mood") or d["music_mood"]).strip().lower()
        if mood not in MOODS:
            errors.append(f"music_mood must be one of {', '.join(MOODS)}")
        platforms = [p.strip().lower() for p in re.split(r"[,;\s/]+", raw.get("platforms", "")) if p.strip()] or [
            "youtube"
        ]
        platforms = list(dict.fromkeys(PLATFORM_ALIASES.get(p, p) for p in platforms))
        language = (raw.get("language") or "").strip().lower()
        if language and voices.language_key(language) != language and language not in ("en", "hi", "हिन्दी"):
            errors.append("language must be english, hinglish or hindi")
        language = voices.language_key(language) if language else ""
        length = 0
        if (raw.get("length") or "").strip():
            m = re.fullmatch(
                r"(\d+(?:\.\d+)?)\s*(s|sec|secs|seconds|m|min|mins|minutes)?", raw["length"].strip().lower()
            )
            if not m:
                errors.append("length must look like 45, 45s or 3m")
            else:
                length = round(float(m.group(1)) * (60 if (m.group(2) or "s").startswith("m") else 1))
                if not 15 <= length <= 1800:
                    errors.append("length must be between 15 seconds and 30 minutes")
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
                    "language": language,
                    "length": length,
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
