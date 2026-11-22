"""Schedule v2: keep-awake flags, safe-publish gate, session checks that pause a platform, builder times."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from common import write_json
from scheduler import builder, guard
from scheduler import run_scheduler as rs
from ui import server

UTC = ZoneInfo("UTC")
IST = ZoneInfo("Asia/Kolkata")


def schedule(jobs: list[dict]) -> dict:
    return {"defaults": {**rs.DEFAULTS}, "jobs": jobs}


def job(i: str, **kw: object) -> dict:
    return {
        "id": i,
        "type": "generate_and_upload",
        "script_or_prompt": f"projects/{i}/script.json",
        "platforms": ["youtube"],
        **kw,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return rs.connect(tmp_path / "state.sqlite")


def test_keep_awake_sets_and_releases_windows_flags() -> None:
    calls: list[int] = []
    awake = guard.KeepAwake(setter=calls.append)
    awake.want(True)
    deadline = time.time() + 2
    while 0x80000001 not in calls and time.time() < deadline:
        time.sleep(0.02)
    assert 0x80000001 in calls and awake.active  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    awake.want(False)
    deadline = time.time() + 2
    while 0x80000000 not in calls and time.time() < deadline:
        time.sleep(0.02)
    assert calls[-1] == 0x80000000 and not awake.active  # released with ES_CONTINUOUS alone
    awake.close()


def test_work_pending_counts_only_waiting_or_running(conn: sqlite3.Connection) -> None:
    assert guard.work_pending(conn) is False
    rs.tick(
        conn,
        schedule([job("a", generate_at=(datetime.now(UTC) + timedelta(hours=3)).isoformat())]),
        lambda s: "m",
        lambda *a: None,
    )
    assert guard.work_pending(conn) is True
    conn.execute("UPDATE jobs SET gen_status='done'")
    conn.execute("UPDATE uploads SET status='needs_review'")
    assert guard.work_pending(conn) is False


def _meta(tmp_path: Path, claims: list[dict], monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(guard, "PROJECTS", tmp_path / "projects")
    write_json(tmp_path / "projects" / "vid" / "script.json", {"claims": claims})
    write_json(tmp_path / "vid.meta.json", {"slug": "vid"})
    return str(tmp_path / "vid.meta.json")


def test_gate_holds_unverified_then_releases_after_approval(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta = _meta(
        tmp_path, [{"text": "Sales hit 5M", "verified": False}, {"text": "ok 1", "verified": True}], monkeypatch
    )
    sent: list[tuple] = []
    stats = rs.tick(conn, schedule([job("a")]), lambda s: meta, lambda *a: sent.append(a), safe_publish=True)
    assert stats["generated"] == 1 and stats["held"] == 1 and sent == []  # rendered, but not uploaded
    assert conn.execute("SELECT status FROM uploads").fetchone()[0] == "needs_review"
    assert any(e["kind"] == "upload_held" for e in conn.execute("SELECT * FROM events"))
    rs.tick(conn, schedule([job("a")]), lambda s: meta, lambda *a: sent.append(a), safe_publish=True)
    assert sent == []  # still held on later ticks
    conn.execute("UPDATE uploads SET status='pending' WHERE status='needs_review'")
    rs.event(conn, "a", "review_approved", "ok")
    assert (
        rs.tick(conn, schedule([job("a")]), lambda s: meta, lambda *a: sent.append(a), safe_publish=True)["uploaded"]
        == 1
    )


def test_gate_passes_verified_and_can_be_switched_off(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    meta = _meta(tmp_path, [{"text": "fact", "verified": True}], monkeypatch)
    assert rs.tick(conn, schedule([job("a")]), lambda s: meta, lambda *a: None, safe_publish=True)["uploaded"] == 1
    meta2 = _meta(tmp_path, [{"text": "fact", "verified": False}], monkeypatch)
    assert rs.tick(conn, schedule([job("b")]), lambda s: meta2, lambda *a: None, safe_publish=False)["uploaded"] == 1


def test_expired_session_pauses_platform_once_without_retry_storm(conn: sqlite3.Connection) -> None:
    checks: list[str] = []

    def expired(platform: str, account: str) -> tuple[bool, str]:
        checks.append(platform)
        return False, "cookie expired"

    sent: list[tuple] = []
    soon = (datetime.now(UTC) + timedelta(minutes=6)).isoformat()  # inside the 5-10 min pre-check window
    sch = schedule([job("a", upload_at=soon)])
    for _ in range(4):
        rs.tick(
            conn,
            sch,
            lambda s: "m",
            lambda *a: sent.append(a),
            auth_check=expired,
            safe_publish=False,
            pre_check_minutes=10,
        )
    assert sent == [] and checks == ["youtube"]  # one check, no repeated attempts
    assert [e["kind"] for e in conn.execute("SELECT kind FROM events")].count("platform_paused") == 1
    assert guard.auth_overview(conn)["youtube"]["paused"] is True
    guard.record_auth(conn, "youtube", True, "re-login worked")  # Check Session / Connect succeeded
    assert guard.is_paused(conn, "youtube") is False


def test_valid_session_is_checked_early_but_upload_waits_for_its_time(conn: sqlite3.Connection) -> None:
    later = (datetime.now(UTC) + timedelta(minutes=8)).isoformat()
    sent: list[tuple] = []
    stats = rs.tick(conn, schedule([job("a", upload_at=later)]), lambda s: "m", lambda *a: sent.append(a),
                    auth_check=lambda p, a: (True, "fine"), safe_publish=False, pre_check_minutes=10)  # fmt: skip
    assert stats["uploaded"] == 0 and sent == [] and guard.auth_overview(conn)["youtube"]["ok"] is True
    far = (datetime.now(UTC) + timedelta(hours=5)).isoformat()
    called: list[str] = []
    rs.tick(conn, schedule([job("b", upload_at=far)]), lambda s: "m", lambda *a: None,
            auth_check=lambda p, a: called.append(p) or (True, ""), safe_publish=False, pre_check_minutes=10)  # fmt: skip
    assert called == []  # not due soon: no browser launched


def test_builder_times_and_modes() -> None:
    now = datetime(2026, 11, 23, 21, 30, tzinfo=IST)
    jit = builder.plan(
        ["a", "b", "c"],
        first="tonight",
        spacing="45m",
        mode="just_in_time",
        tz_name="Asia/Kolkata",
        lead_min=20,
        now=now,
    )
    assert [e["upload_at"].strftime("%H:%M") for e in jit] == ["23:00", "23:45", "00:30"]
    assert jit[0]["generate_at"].strftime("%H:%M") == "22:40"
    allnow = builder.plan(["a", "b"], first="now", spacing="2h", mode="all_now", tz_name="Asia/Kolkata", now=now)
    assert allnow[0]["generate_at"] is None and allnow[1]["upload_at"] == now + timedelta(hours=2)
    late = datetime(2026, 11, 23, 23, 30, tzinfo=IST)
    assert builder.first_time("tonight", late, IST).day == 24  # 11 PM already passed
    custom = builder.plan(
        ["a"], first="2026-12-01T09:15", spacing="90m", mode="all_now", tz_name="Asia/Kolkata", now=now
    )
    assert custom[0]["upload_at"].isoformat() == "2026-12-01T09:15:00+05:30"
    with pytest.raises(ValueError):
        builder.plan(["a"], first="now", spacing="1h", mode="sometime", tz_name="Asia/Kolkata")


def test_human_times() -> None:
    now = datetime(2026, 11, 23, 10, 0, tzinfo=IST)
    assert builder.human_time("2026-11-23T23:45:00+05:30", "Asia/Kolkata", now) == "Today 11:45 PM"
    assert builder.human_time("2026-11-24T08:00:00", "Asia/Kolkata", now) == "Tomorrow 8:00 AM"
    assert builder.human_time("2026-11-30T18:00:00+05:30", "Asia/Kolkata", now) == "Mon 30 Nov 6:00 PM"
    assert builder.human_time(None, "Asia/Kolkata") == ""


def test_queue_card_steps() -> None:
    assert server._job_step({}, {"gen_status": "pending"}, []) == 0
    assert server._job_step({}, {"gen_status": "running"}, []) == 1
    assert server._job_step({}, {"gen_status": "done"}, [{"status": "pending"}]) == 2
    assert server._job_step({}, {"gen_status": "done"}, [{"status": "running"}]) == 2
    assert server._job_step({}, {"gen_status": "done"}, [{"status": "done"}, {"status": "done"}]) == 3
