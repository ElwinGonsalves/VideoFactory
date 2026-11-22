"""Schedule Builder: spread several finished projects over time, and show times the way people say them."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from batch.sheet import parse_interval

RENDER_LEAD_MIN = 20  # "auto-generate X min before upload" default; one render takes a few minutes


def first_time(value: str, now: datetime, tz: ZoneInfo) -> datetime:
    """'now', 'tonight' (11:00 PM today, or the next 11 PM if already past) or an ISO / datetime-local string."""
    value = (value or "now").strip().lower()
    if value == "now":
        return now
    if value == "tonight":
        t = datetime.combine(now.date(), time(23, 0), tzinfo=tz)
        return t if t > now else t + timedelta(days=1)
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)


def plan(
    slugs: list[str],
    *,
    first: str,
    spacing: str,
    mode: str,
    tz_name: str,
    lead_min: int = RENDER_LEAD_MIN,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """One entry per project: upload_at, generate_at (None = generate right away).

    mode "just_in_time": each video is generated `lead_min` before its own upload.
    mode "all_now": everything generates immediately (renders queue one at a time), uploads stay staggered.
    """
    if mode not in ("just_in_time", "all_now"):
        raise ValueError("mode must be just_in_time or all_now")
    tz = ZoneInfo(tz_name)
    now = (now or datetime.now(tz)).astimezone(tz)
    start = first_time(first, now, tz)
    step = parse_interval(spacing)
    out = []
    for i, slug in enumerate(slugs):
        upload = start + step * i
        gen = None
        if mode == "just_in_time":
            gen = max(now, upload - timedelta(minutes=lead_min))
        out.append({"slug": slug, "upload_at": upload, "generate_at": gen})
    return out


def human_time(value: str | datetime | None, tz_name: str, now: datetime | None = None) -> str:
    """'Today 11:45 PM', 'Tomorrow 8:00 AM', 'Mon 24 Nov 6:00 PM'. Empty for None."""
    if not value:
        return ""
    tz = ZoneInfo(tz_name)
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    dt = dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)
    today = (now or datetime.now(tz)).astimezone(tz).date()
    clock = dt.strftime("%I:%M %p").lstrip("0")
    delta = (dt.date() - today).days
    if delta == 0:
        return f"Today {clock}"
    if delta == 1:
        return f"Tomorrow {clock}"
    if delta == -1:
        return f"Yesterday {clock}"
    return f"{dt.strftime('%a')} {dt.day} {dt.strftime('%b')} {clock}"
