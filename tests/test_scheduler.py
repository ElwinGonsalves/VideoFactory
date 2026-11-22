"""Scheduler logic with fake generate/upload actions (no rendering, no browser)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scheduler import run_scheduler as rs

UTC = ZoneInfo("UTC")


def schedule(jobs: list[dict], **defaults: object) -> dict:
    return {"defaults": {**rs.DEFAULTS, **defaults}, "jobs": jobs}


def job(i: str, **kw: object) -> dict:
    base = {
        "id": i,
        "type": "generate_and_upload",
        "script_or_prompt": f"projects/{i}/script.json",
        "platforms": ["youtube"],
    }
    return {**base, **kw}


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return rs.connect(tmp_path / "state.sqlite")


def test_generate_then_upload_with_unlisted_default(conn: sqlite3.Connection) -> None:
    calls: list[tuple] = []
    stats = rs.tick(conn, schedule([job("a")]), lambda s: "out/a.meta.json", lambda *a: calls.append(a))
    assert {k: stats[k] for k in ("generated", "uploaded")} == {"generated": 1, "uploaded": 1}
    assert calls == [("out/a.meta.json", "youtube", "main", "unlisted")]


def test_future_jobs_wait(conn: sqlite3.Connection) -> None:
    later = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    stats = rs.tick(conn, schedule([job("a", generate_at=later)]), lambda s: "m", lambda *a: None)
    assert {k: stats[k] for k in ("generated", "uploaded")} == {"generated": 0, "uploaded": 0}


def test_upload_waits_for_upload_at(conn: sqlite3.Connection) -> None:
    later = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    stats = rs.tick(conn, schedule([job("a", upload_at=later)]), lambda s: "m", lambda *a: None)
    assert {k: stats[k] for k in ("generated", "uploaded")} == {"generated": 1, "uploaded": 0}


def test_retry_with_backoff_then_fail(conn: sqlite3.Connection) -> None:
    def boom(spec: dict) -> str:
        raise RuntimeError("tts down")

    sch = schedule([job("a")])
    rs.tick(conn, sch, boom, lambda *a: None)
    row = conn.execute("SELECT * FROM jobs").fetchone()
    assert row["gen_status"] == "pending" and row["gen_attempts"] == 1 and row["gen_next_at"]
    # Not retried before the backoff expires.
    assert rs.tick(conn, sch, boom, lambda *a: None)["generated"] == 0
    for n in range(2, rs.MAX_ATTEMPTS + 1):
        rs.tick(conn, sch, boom, lambda *a: None, at=datetime.now(UTC) + timedelta(days=n))
    row = conn.execute("SELECT * FROM jobs").fetchone()
    assert row["gen_status"] == "failed" and row["gen_attempts"] == rs.MAX_ATTEMPTS


def test_instagram_daily_cap(conn: sqlite3.Connection) -> None:
    jobs = [job(f"j{i}", platforms=["instagram"]) for i in range(4)]
    uploaded: list[str] = []
    stats = rs.tick(conn, schedule(jobs, instagram_daily_cap=2), lambda s: f"{s['id']}.meta.json",
                    lambda m, *a: uploaded.append(m))  # fmt: skip
    assert stats["uploaded"] == 2 and len(uploaded) == 2
    capped = conn.execute("SELECT COUNT(*) FROM uploads WHERE status='pending' AND next_at IS NOT NULL").fetchone()[0]
    assert capped == 2


def test_sync_does_not_reset_progress(conn: sqlite3.Connection) -> None:
    sch = schedule([job("a")])
    rs.tick(conn, sch, lambda s: "m", lambda *a: None)
    rs.sync(conn, sch)
    assert conn.execute("SELECT gen_status FROM jobs").fetchone()[0] == "done"
    assert conn.execute("SELECT status FROM uploads").fetchone()[0] == "done"


def test_state_not_locked_during_generation(tmp_path: Path) -> None:
    """Regression: an uncommitted event kept state.sqlite write-locked for a whole render,
    so the UI's Schedule tab failed with 'database is locked'."""
    db = tmp_path / "state.sqlite"
    conn = rs.connect(db)

    def generate(spec: dict) -> str:
        other = sqlite3.connect(db, timeout=0.5)  # what the UI does while a render runs
        other.execute("INSERT INTO events VALUES ('t', NULL, 'probe', '')")
        other.commit()
        other.close()
        return "m"

    stats = rs.tick(conn, schedule([job("a", type="generate_only")]), generate, lambda *a: None)
    assert stats["generated"] == 1


def test_upload_only_skips_generation(conn: sqlite3.Connection) -> None:
    calls: list[tuple] = []
    sch = schedule([job("a", type="upload_only", meta="output/a.meta.json")])
    stats = rs.tick(conn, sch, lambda s: pytest.fail("should not generate"), lambda *a: calls.append(a))
    assert {k: stats[k] for k in ("generated", "uploaded")} == {"generated": 0, "uploaded": 1} and calls[0][
        0
    ] == "output/a.meta.json"
