"""Pre-flight safety for unattended uploads.

- KeepAwake: stops Windows sleeping while jobs are pending or running.
- Safe-Publish Gate: a video with unverified facts is rendered but held as `needs_review`.
- Session checks: 5-10 minutes before an upload the cookie session / API token is checked. When it has
  expired the platform's queue is paused (one event, no retry storms) until you reconnect.
"""

from __future__ import annotations

import ctypes
import os
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from common import PROJECTS, ROOT, read_json

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

GUARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS auth (
    platform TEXT PRIMARY KEY,
    ok INTEGER NOT NULL,
    checked_at TEXT NOT NULL,
    detail TEXT
);
CREATE TABLE IF NOT EXISTS platform_pause (
    platform TEXT PRIMARY KEY,
    reason TEXT,
    since TEXT NOT NULL
);
"""

AuthCheck = Callable[[str, str], tuple[bool, str]]


def _utc() -> datetime:
    return datetime.now(ZoneInfo("UTC"))


# ------------------------------------------------------------------ keep awake
def _win_set(flags: int) -> None:
    ctypes.windll.kernel32.SetThreadExecutionState(flags)  # type: ignore[attr-defined]


class KeepAwake:
    """Holds SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) from ONE long-lived thread.

    The flag belongs to the thread that set it, so the daemon's short-lived tick threads cannot be used.
    `want(True)` sets 0x80000001; `want(False)` releases with 0x80000000. No-op off Windows.
    """

    def __init__(self, setter: Callable[[int], None] | None = None) -> None:
        self._set = setter or (_win_set if os.name == "nt" else (lambda _f: None))
        self._want = threading.Event()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self.active = False
        self._thread = threading.Thread(target=self._loop, daemon=True, name="keep-awake")
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            wanted = self._want.is_set()
            if wanted:
                self._set(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)  # re-asserted every cycle
                self.active = True
            elif self.active:
                self._set(ES_CONTINUOUS)
                self.active = False
            self._wake.wait(30)
            self._wake.clear()
        if self.active:
            self._set(ES_CONTINUOUS)
            self.active = False

    def want(self, on: bool) -> None:
        (self._want.set if on else self._want.clear)()
        self._wake.set()

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=2)


def work_pending(conn: sqlite3.Connection) -> bool:
    """True while any generation or upload is waiting or running (held `needs_review` jobs do not count)."""
    gen = conn.execute("SELECT 1 FROM jobs WHERE gen_status IN ('pending','running') LIMIT 1").fetchone()
    up = conn.execute("SELECT 1 FROM uploads WHERE status IN ('pending','running') LIMIT 1").fetchone()
    return bool(gen or up)


# ------------------------------------------------------------------ safe-publish gate
def unverified_claims(meta_path: str | Path) -> list[str]:
    """Unverified fact claims of the video behind a meta.json ([] when unknown or all verified)."""
    path = Path(meta_path)
    path = path if path.is_absolute() else ROOT / path
    if not path.exists():
        return []
    meta = read_json(path)
    slug = meta.get("slug", "")
    script_file = PROJECTS / slug / "script.json"
    script = read_json(script_file) if slug and script_file.exists() else {}
    claims = script.get("claims")
    if claims:
        return [c["text"] for c in claims if not c.get("verified")]
    return list(meta.get("facts_to_verify") or script.get("facts_to_verify") or [])


def review_approved(conn: sqlite3.Connection, job_id: str) -> bool:
    return bool(
        conn.execute("SELECT 1 FROM events WHERE job_id=? AND kind='review_approved' LIMIT 1", (job_id,)).fetchone()
    )


# ------------------------------------------------------------------ session checks
def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(GUARD_SCHEMA)


def default_auth_check(platform: str, account: str) -> tuple[bool, str]:
    """Cookie session via social-auto-upload, or presence of API credentials, depending on Settings."""
    from common import settings
    from publisher import official_apis, publish

    cfg = settings.load()["publish"][platform]
    if cfg.get("method") == "api":
        ok = official_apis.configured(platform)
        return ok, "API credentials present" if ok else "API credentials missing: open Settings"
    try:
        code = publish.check(platform, account)
    except Exception as exc:  # noqa: BLE001 - a missing publisher venv is an auth problem for the user to fix
        return False, str(exc)[:160]
    return code == 0, "cookie session valid" if code == 0 else "cookie session expired: Connect / Refresh Login"


def record_auth(conn: sqlite3.Connection, platform: str, ok: bool, detail: str) -> None:
    ensure_schema(conn)
    conn.execute("INSERT OR REPLACE INTO auth VALUES (?,?,?,?)", (platform, int(ok), _utc().isoformat(), detail[:200]))
    if ok:
        conn.execute("DELETE FROM platform_pause WHERE platform=?", (platform,))
    conn.commit()


def is_paused(conn: sqlite3.Connection, platform: str) -> bool:
    ensure_schema(conn)
    return bool(conn.execute("SELECT 1 FROM platform_pause WHERE platform=?", (platform,)).fetchone())


def pause_platform(conn: sqlite3.Connection, platform: str, reason: str) -> bool:
    """Pause a platform's queue. Returns True the first time (so the caller logs exactly one event)."""
    ensure_schema(conn)
    if is_paused(conn, platform):
        return False
    conn.execute("INSERT INTO platform_pause VALUES (?,?,?)", (platform, reason[:200], _utc().isoformat()))
    conn.commit()
    return True


def due_soon(upload_at: datetime | None, now: datetime, window_min: int) -> bool:
    """Within `window_min` minutes before the upload (or already due)."""
    return upload_at is None or upload_at - now <= timedelta(minutes=window_min)


def check_if_stale(
    conn: sqlite3.Connection, platform: str, account: str, check: AuthCheck, now: datetime, max_age_min: int = 5
) -> bool:
    """Run a session check unless one ran in the last `max_age_min` minutes. Returns the latest result."""
    ensure_schema(conn)
    row = conn.execute("SELECT ok, checked_at FROM auth WHERE platform=?", (platform,)).fetchone()
    if row and now - datetime.fromisoformat(row["checked_at"]) < timedelta(minutes=max_age_min):
        return bool(row["ok"])
    ok, detail = check(platform, account)
    record_auth(conn, platform, ok, detail)
    return ok


def auth_overview(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    ensure_schema(conn)
    out: dict[str, dict[str, Any]] = {
        p: {"ok": None, "checked_at": None, "detail": "", "paused": False} for p in ("youtube", "instagram", "tiktok")
    }
    for r in conn.execute("SELECT * FROM auth"):
        out[r["platform"]].update({"ok": bool(r["ok"]), "checked_at": r["checked_at"], "detail": r["detail"]})
    for r in conn.execute("SELECT * FROM platform_pause"):
        out[r["platform"]].update({"paused": True, "pause_reason": r["reason"]})
    return out
