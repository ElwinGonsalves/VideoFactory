"""Generation + upload scheduler.

schedule.yaml declares jobs. state.sqlite keeps what has happened (status, attempts,
retry times, daily upload counts), so a restart picks up exactly where it stopped.
The daemon is an APScheduler BlockingScheduler that runs `tick()` every minute;
each tick syncs schedule.yaml into state.sqlite and runs whatever is due.

Rules:
  - Generation runs at `generate_at`; upload runs at `upload_at` (after generation succeeded).
  - Transient failures retry with exponential backoff: 5, 10, 20, 40, 80 minutes, then `failed`.
  - Per-platform daily caps (defaults.<platform>_daily_cap) count successful uploads per local
    day in `defaults.timezone`. A capped upload moves to the next day, same time.
  - YouTube visibility defaults to `defaults.youtube_visibility` (unlisted).

CLI:
    python scheduler/run_scheduler.py add --id concept-002 --script projects/x/script.json \
        --generate-at 2026-11-24T08:00:00+05:30 --upload-at 2026-11-24T18:00:00+05:30 --platforms youtube
    python scheduler/run_scheduler.py list
    python scheduler/run_scheduler.py status
    python scheduler/run_scheduler.py run-now concept-001 [--generate-only|--upload-only]
    python scheduler/run_scheduler.py retry concept-001
    python scheduler/run_scheduler.py daemon
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import traceback
from collections.abc import Callable
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from common import ROOT  # noqa: E402
from publisher.post_log import SCHEMA as POSTS_SCHEMA  # noqa: E402

HERE = Path(__file__).resolve().parent
SCHEDULE = HERE / "schedule.yaml"
STATE = HERE / "state.sqlite"
LOGS = HERE / "logs"
MAX_ATTEMPTS = 5
BACKOFF_MIN = 5
JOB_TYPES = ("generate_only", "upload_only", "generate_and_upload")
DEFAULTS = {
    "timezone": "Asia/Kolkata",
    "youtube_visibility": "unlisted",
    "instagram_daily_cap": 2,
    "youtube_daily_cap": 5,
    "tiktok_daily_cap": 3,
    "account": "main",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    spec TEXT NOT NULL,
    gen_status TEXT NOT NULL DEFAULT 'pending',
    gen_attempts INTEGER NOT NULL DEFAULT 0,
    gen_next_at TEXT,
    meta_path TEXT,
    last_error TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS uploads (
    job_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_at TEXT,
    done_at TEXT,
    local_day TEXT,
    last_error TEXT,
    PRIMARY KEY (job_id, platform)
);
CREATE TABLE IF NOT EXISTS events (
    at TEXT NOT NULL,
    job_id TEXT,
    kind TEXT NOT NULL,
    detail TEXT
);
"""

log = logging.getLogger("scheduler")


# ---------------------------------------------------------------- state helpers
def connect(path: Path = STATE) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA + POSTS_SCHEMA)  # posts: shared with publisher/post_log.py
    return conn


def now_utc() -> datetime:
    return datetime.now(ZoneInfo("UTC"))


def parse_time(value: Any, tz: ZoneInfo) -> datetime | None:
    if value in (None, ""):
        return None
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)


def event(conn: sqlite3.Connection, job_id: str | None, kind: str, detail: str = "") -> None:
    conn.execute("INSERT INTO events VALUES (?,?,?,?)", (now_utc().isoformat(), job_id, kind, detail[:4000]))
    log.info(json.dumps({"job": job_id, "event": kind, "detail": detail[:500]}))


def load_schedule(path: Path = SCHEDULE) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    data = data or {}
    data["defaults"] = {**DEFAULTS, **(data.get("defaults") or {})}
    data["jobs"] = data.get("jobs") or []
    return data


def sync(conn: sqlite3.Connection, schedule: dict[str, Any]) -> int:
    """Insert new jobs; refresh the spec of jobs that have not started. Never resets progress."""
    added = 0
    for job in schedule["jobs"]:
        if job.get("enabled", True) is False:
            continue  # paused/example jobs stay in the YAML but never run
        if job.get("type", "generate_and_upload") not in JOB_TYPES:
            raise ValueError(f"job {job.get('id')}: bad type {job.get('type')}")
        spec = json.dumps(job, default=str)
        row = conn.execute("SELECT gen_status FROM jobs WHERE id=?", (job["id"],)).fetchone()
        if row is None:
            gen_status = "skipped" if job.get("type") == "upload_only" else "pending"
            conn.execute(
                "INSERT INTO jobs (id, type, spec, gen_status, updated_at) VALUES (?,?,?,?,?)",
                (job["id"], job.get("type", "generate_and_upload"), spec, gen_status, now_utc().isoformat()),
            )
            added += 1
        elif row["gen_status"] == "pending":
            conn.execute(
                "UPDATE jobs SET spec=?, type=? WHERE id=?", (spec, job.get("type", "generate_and_upload"), job["id"])
            )
        if job.get("type", "generate_and_upload") != "generate_only":
            for platform in job.get("platforms", ["youtube"]):
                conn.execute("INSERT OR IGNORE INTO uploads (job_id, platform) VALUES (?,?)", (job["id"], platform))
    conn.commit()
    return added


def backoff(attempts: int) -> timedelta:
    return timedelta(minutes=BACKOFF_MIN * 2 ** max(0, attempts - 1))


def uploads_today(conn: sqlite3.Connection, platform: str, day: str) -> int:
    row = conn.execute("SELECT COUNT(*) FROM posts WHERE platform=? AND local_day=?", (platform, day)).fetchone()
    return int(row[0])


def project_of(spec: dict[str, Any]) -> Path:
    target = Path(spec.get("script_or_prompt") or spec.get("project", ""))
    target = target if target.is_absolute() else ROOT / target
    return target.parent if target.suffix == ".json" else target


# ---------------------------------------------------------------- actions (overridable in tests)
def default_generate(spec: dict[str, Any]) -> str:
    from make_video import produce

    project = project_of(spec)
    if not (project / "script.json").exists():
        prompt = spec.get("script_or_prompt", "")
        project.mkdir(parents=True, exist_ok=True)
        (project / "prompt.txt").write_text(str(prompt), encoding="utf-8")
        raise RuntimeError(f"{project}/script.json missing; the agent must write it from prompt.txt first")
    result = produce(project, style=spec.get("style"), aspect=spec.get("aspect_ratio"), mood=spec.get("music_mood"))
    return str(Path(result["mp4"]).with_suffix(".meta.json"))


def default_upload(meta_path: str, platform: str, account: str, visibility: str | None) -> None:
    from publisher.publish import upload

    # The scheduler already checked the cap and records the post itself (see run_upload).
    code = upload(Path(meta_path), platform, account, visibility, force=True, record=False)
    if code != 0:
        raise RuntimeError(f"{platform} upload exited with {code}")


Generate = Callable[[dict[str, Any]], str]
Upload = Callable[[str, str, str, "str | None"], None]


# ---------------------------------------------------------------- core loop
def run_generation(conn: sqlite3.Connection, row: sqlite3.Row, generate: Generate) -> bool:
    spec = json.loads(row["spec"])
    attempts = row["gen_attempts"] + 1
    conn.execute(
        "UPDATE jobs SET gen_status='running', gen_attempts=?, updated_at=? WHERE id=?",
        (attempts, now_utc().isoformat(), row["id"]),
    )
    conn.commit()
    event(conn, row["id"], "generate_start", f"attempt {attempts}")
    try:
        meta = generate(spec)
    except Exception as exc:  # noqa: BLE001 - every failure is recorded and retried
        err = f"{exc}\n{traceback.format_exc(limit=3)}"
        if attempts >= MAX_ATTEMPTS:
            conn.execute("UPDATE jobs SET gen_status='failed', last_error=? WHERE id=?", (err, row["id"]))
            event(conn, row["id"], "generate_failed", err)
        else:
            nxt = now_utc() + backoff(attempts)
            conn.execute(
                "UPDATE jobs SET gen_status='pending', gen_next_at=?, last_error=? WHERE id=?",
                (nxt.isoformat(), err, row["id"]),
            )
            event(conn, row["id"], "generate_retry", f"next at {nxt.isoformat()}: {exc}")
        conn.commit()
        return False
    conn.execute("UPDATE jobs SET gen_status='done', meta_path=?, last_error=NULL WHERE id=?", (meta, row["id"]))
    event(conn, row["id"], "generate_done", meta)
    conn.commit()
    return True


def run_upload(
    conn: sqlite3.Connection,
    job: sqlite3.Row,
    up: sqlite3.Row,
    defaults: dict[str, Any],
    upload: Upload,
    tz: ZoneInfo,
    force: bool = False,
) -> bool:
    spec = json.loads(job["spec"])
    platform = up["platform"]
    meta = job["meta_path"] or spec.get("meta")
    if not meta:
        event(conn, job["id"], "upload_blocked", f"{platform}: no meta.json yet")
        return False
    local_now = now_utc().astimezone(tz)
    day = local_now.date().isoformat()
    cap = int(defaults.get(f"{platform}_daily_cap", 99))
    if not force and uploads_today(conn, platform, day) >= cap:
        nxt = (local_now + timedelta(days=1)).astimezone(ZoneInfo("UTC"))
        conn.execute(
            "UPDATE uploads SET next_at=? WHERE job_id=? AND platform=?", (nxt.isoformat(), job["id"], platform)
        )
        event(conn, job["id"], "upload_capped", f"{platform} cap {cap}/day reached; moved to {nxt.isoformat()}")
        conn.commit()
        return False
    visibility = spec.get("visibility") or (defaults["youtube_visibility"] if platform == "youtube" else None)
    attempts = up["attempts"] + 1
    conn.execute(
        "UPDATE uploads SET status='running', attempts=? WHERE job_id=? AND platform=?", (attempts, job["id"], platform)
    )
    conn.commit()
    try:
        upload(meta, platform, spec.get("account", defaults["account"]), visibility)
    except Exception as exc:  # noqa: BLE001
        status, nxt = ("failed", None) if attempts >= MAX_ATTEMPTS else ("pending", now_utc() + backoff(attempts))
        conn.execute(
            "UPDATE uploads SET status=?, next_at=?, last_error=? WHERE job_id=? AND platform=?",
            (status, nxt.isoformat() if nxt else None, str(exc), job["id"], platform),
        )
        event(conn, job["id"], f"upload_{'failed' if status == 'failed' else 'retry'}", f"{platform}: {exc}")
        conn.commit()
        return False
    conn.execute(
        "UPDATE uploads SET status='done', done_at=?, local_day=?, last_error=NULL WHERE job_id=? AND platform=?",
        (now_utc().isoformat(), day, job["id"], platform),
    )
    conn.execute(
        "INSERT INTO posts VALUES (?,?,?,?,?,?,?,?)",
        (
            now_utc().isoformat(),
            day,
            platform,
            "scheduler",
            Path(meta).stem.removesuffix(".meta"),
            visibility,
            "",
            job["id"],
        ),
    )
    event(conn, job["id"], "upload_done", f"{platform} ({visibility or 'default'})")
    conn.commit()
    return True


def tick(
    conn: sqlite3.Connection,
    schedule: dict[str, Any],
    generate: Generate = default_generate,
    upload: Upload = default_upload,
    at: datetime | None = None,
) -> dict[str, int]:
    """One scheduler pass. Returns counts of actions taken."""
    sync(conn, schedule)
    defaults = schedule["defaults"]
    tz = ZoneInfo(defaults["timezone"])
    current = at or now_utc()
    stats = {"generated": 0, "uploaded": 0}
    for job in conn.execute("SELECT * FROM jobs WHERE gen_status='pending'").fetchall():
        spec = json.loads(job["spec"])
        due = parse_time(spec.get("generate_at"), tz) or current
        retry_at = parse_time(job["gen_next_at"], tz)
        if due <= current and (retry_at is None or retry_at <= current):
            stats["generated"] += run_generation(conn, job, generate)
    rows = conn.execute(
        "SELECT u.*, j.gen_status FROM uploads u JOIN jobs j ON j.id=u.job_id WHERE u.status='pending'"
    ).fetchall()
    for up in rows:
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (up["job_id"],)).fetchone()
        if job["gen_status"] not in ("done", "skipped"):
            continue
        spec = json.loads(job["spec"])
        due = parse_time(spec.get("upload_at"), tz) or current
        retry_at = parse_time(up["next_at"], tz)
        if due <= current and (retry_at is None or retry_at <= current):
            stats["uploaded"] += run_upload(conn, job, up, defaults, upload, tz)
    return stats


# ---------------------------------------------------------------- CLI
def setup_logging() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOGS / "scheduler.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.addHandler(logging.StreamHandler(sys.stdout))
    log.setLevel(logging.INFO)


def cmd_add(a: argparse.Namespace) -> int:
    schedule = yaml.safe_load(SCHEDULE.read_text(encoding="utf-8")) if SCHEDULE.exists() else {}
    schedule = schedule or {"defaults": dict(DEFAULTS), "jobs": []}
    schedule.setdefault("jobs", [])
    if any(j["id"] == a.id for j in schedule["jobs"]):
        print(f"job {a.id} already exists in {SCHEDULE}")
        return 1
    job = {
        "id": a.id,
        "type": a.type,
        "script_or_prompt": a.script,
        "style": a.style,
        "aspect_ratio": a.aspect,
        "music_mood": a.mood,
        "generate_at": a.generate_at,
        "upload_at": a.upload_at,
        "platforms": [p.strip() for p in a.platforms.split(",") if p.strip()],
    }
    if a.visibility:
        job["visibility"] = a.visibility
    schedule["jobs"].append({k: v for k, v in job.items() if v is not None})
    SCHEDULE.write_text(yaml.safe_dump(schedule, sort_keys=False, allow_unicode=True), encoding="utf-8")
    with closing(connect()) as conn:
        sync(conn, load_schedule())
    print(f"added {a.id}")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    with closing(connect()) as conn:
        sync(conn, load_schedule())
        print(f"{'job':24} {'type':20} {'generate_at':26} {'gen':9} uploads")
        for job in conn.execute("SELECT * FROM jobs ORDER BY id"):
            spec = json.loads(job["spec"])
            ups = conn.execute("SELECT platform, status FROM uploads WHERE job_id=?", (job["id"],)).fetchall()
            up_txt = ", ".join(f"{u['platform']}={u['status']}" for u in ups) or "-"
            print(
                f"{job['id']:24} {job['type']:20} {str(spec.get('generate_at', 'now')):26} {job['gen_status']:9} {up_txt}"
            )
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    schedule = load_schedule()
    tz = ZoneInfo(schedule["defaults"]["timezone"])
    day = now_utc().astimezone(tz).date().isoformat()
    with closing(connect()) as conn:
        sync(conn, schedule)
        for platform in ("youtube", "instagram", "tiktok"):
            cap = schedule["defaults"].get(f"{platform}_daily_cap", "-")
            print(f"{platform:10} uploads today ({day}): {uploads_today(conn, platform, day)}/{cap}")
        print("\nrecent events:")
        for ev in conn.execute("SELECT * FROM events ORDER BY at DESC LIMIT 15"):
            print(f"  {ev['at'][:19]}  {ev['job_id'] or '-':20} {ev['kind']:16} {(ev['detail'] or '')[:80]}")
        for job in conn.execute("SELECT id, last_error FROM jobs WHERE last_error IS NOT NULL"):
            print(f"\nlast error for {job['id']}:\n{job['last_error'][:800]}")
    return 0


def cmd_run_now(a: argparse.Namespace) -> int:
    schedule = load_schedule()
    tz = ZoneInfo(schedule["defaults"]["timezone"])
    with closing(connect()) as conn:
        sync(conn, schedule)
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (a.job_id,)).fetchone()
        if job is None:
            print(f"unknown job {a.job_id}")
            return 1
        ok = True
        if not a.upload_only and job["type"] != "upload_only":
            ok = run_generation(conn, job, default_generate)
            job = conn.execute("SELECT * FROM jobs WHERE id=?", (a.job_id,)).fetchone()
        if ok and not a.generate_only:
            for up in conn.execute("SELECT * FROM uploads WHERE job_id=? AND status!='done'", (a.job_id,)).fetchall():
                ok = run_upload(conn, job, up, schedule["defaults"], default_upload, tz, force=False) and ok
        return 0 if ok else 1


def cmd_retry(a: argparse.Namespace) -> int:
    with closing(connect()) as conn:
        conn.execute(
            "UPDATE jobs SET gen_status='pending', gen_attempts=0, gen_next_at=NULL WHERE id=? AND gen_status='failed'",
            (a.job_id,),
        )
        conn.execute(
            "UPDATE uploads SET status='pending', attempts=0, next_at=NULL WHERE job_id=? AND status='failed'",
            (a.job_id,),
        )
        conn.commit()
    print(f"reset failed parts of {a.job_id}")
    return 0


def cmd_daemon(a: argparse.Namespace) -> int:
    from apscheduler.schedulers.blocking import BlockingScheduler

    schedule = load_schedule()

    def _tick() -> None:
        with closing(connect()) as conn:
            try:
                stats = tick(conn, load_schedule())
                if any(stats.values()):
                    log.info(json.dumps({"tick": stats}))
            except Exception:  # noqa: BLE001 - keep the daemon alive
                log.exception("tick failed")

    sched = BlockingScheduler(timezone=schedule["defaults"]["timezone"])
    sched.add_job(
        _tick,
        "interval",
        seconds=a.interval,
        id="tick",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(ZoneInfo(schedule["defaults"]["timezone"])),
    )
    log.info(f"scheduler daemon started (every {a.interval}s, state {STATE})")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler daemon stopped")
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add", help="Add a job to schedule.yaml")
    s.add_argument("--id", required=True)
    s.add_argument("--type", choices=JOB_TYPES, default="generate_and_upload")
    s.add_argument("--script", required=True, help="projects/<slug>/script.json (or a prompt string)")
    s.add_argument("--style")
    s.add_argument("--aspect", choices=["9:16", "16:9", "1:1"])
    s.add_argument("--mood")
    s.add_argument("--generate-at", help="ISO time, e.g. 2026-11-24T08:00:00+05:30 (default: now)")
    s.add_argument("--upload-at", help="ISO time (default: right after generation)")
    s.add_argument("--platforms", default="youtube")
    s.add_argument("--visibility", choices=["unlisted", "private", "public"])
    s.set_defaults(func=cmd_add)
    sub.add_parser("list", help="Show jobs and their state").set_defaults(func=cmd_list)
    sub.add_parser("status", help="Daily caps, recent events, last errors").set_defaults(func=cmd_status)
    r = sub.add_parser("run-now", help="Run one job immediately")
    r.add_argument("job_id")
    g = r.add_mutually_exclusive_group()
    g.add_argument("--generate-only", action="store_true")
    g.add_argument("--upload-only", action="store_true")
    r.set_defaults(func=cmd_run_now)
    t = sub.add_parser("retry", help="Reset a failed job so it runs again")
    t.add_argument("job_id")
    t.set_defaults(func=cmd_retry)
    d = sub.add_parser("daemon", help="Run continuously")
    d.add_argument("--interval", type=int, default=60)
    d.set_defaults(func=cmd_daemon)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
