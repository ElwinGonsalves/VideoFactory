"""Shared post log + daily caps, stored in scheduler/state.sqlite.

Every successful upload from any path (UI button, publish.py CLI, scheduler) is recorded here,
so the per-platform daily caps (Instagram 1-2/day) hold no matter how a post was started.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from common import ROOT

STATE = ROOT / "scheduler" / "state.sqlite"
SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    at TEXT NOT NULL,
    local_day TEXT NOT NULL,
    platform TEXT NOT NULL,
    method TEXT NOT NULL,
    slug TEXT,
    visibility TEXT,
    url TEXT,
    job_id TEXT
);
"""
DEFAULT_CAPS = {"instagram": 2, "youtube": 5, "tiktok": 3}


class CapReached(RuntimeError):
    pass


def _connect(path: Path = STATE) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)  # shared with the scheduler and the UI
    conn.executescript(SCHEMA)
    return conn


def _schedule_defaults() -> dict[str, Any]:
    try:
        from scheduler.run_scheduler import load_schedule

        return load_schedule()["defaults"]
    except Exception:  # noqa: BLE001 - a broken schedule.yaml must not block a manual upload
        return {"timezone": "Asia/Kolkata"}


def today(tz_name: str | None = None) -> str:
    tz = ZoneInfo(tz_name or _schedule_defaults().get("timezone", "Asia/Kolkata"))
    return datetime.now(tz).date().isoformat()


def cap_for(platform: str) -> int:
    return int(_schedule_defaults().get(f"{platform}_daily_cap", DEFAULT_CAPS.get(platform, 99)))


def count_today(platform: str, day: str | None = None, path: Path = STATE) -> int:
    with closing(_connect(path)) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE platform=? AND local_day=?", (platform, day or today())
        ).fetchone()
        return int(row[0])


def check_cap(platform: str, path: Path = STATE) -> None:
    used, cap = count_today(platform, path=path), cap_for(platform)
    if used >= cap:
        raise CapReached(f"{platform} daily cap reached ({used}/{cap} today). Raise it in Schedule settings or wait.")


def record(
    platform: str,
    method: str,
    slug: str,
    visibility: str | None = None,
    url: str = "",
    job_id: str = "",
    path: Path = STATE,
) -> None:
    now = datetime.now(ZoneInfo("UTC")).isoformat()
    with closing(_connect(path)) as conn:
        conn.execute(
            "INSERT INTO posts VALUES (?,?,?,?,?,?,?,?)",
            (now, today(), platform, method, slug, visibility, url, job_id),
        )
        conn.commit()


def recent(limit: int = 50, path: Path = STATE) -> list[dict[str, Any]]:
    with closing(_connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM posts ORDER BY at DESC LIMIT ?", (limit,))]
