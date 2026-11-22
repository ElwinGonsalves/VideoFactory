"""data/projects.db: the library index, idea history, published URLs, analytics and LLM usage.

Files stay in output/<project_id>/; this database is only the index. It lives in data/ (gitignored,
and best kept outside OneDrive: see docs/DEBUGGING.md).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import ROOT

DB_PATH = ROOT / "data" / "projects.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    topic TEXT,
    case_study TEXT,
    hook TEXT,
    style TEXT,
    aspect_ratio TEXT,
    duration_sec REAL,
    source TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS published (
    project_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    url TEXT NOT NULL,
    PRIMARY KEY (project_id, platform)
);
CREATE TABLE IF NOT EXISTS analytics (
    project_id TEXT PRIMARY KEY,
    views INTEGER,
    likes INTEGER,
    fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS llm_usage (
    at TEXT NOT NULL,
    day TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    task TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = path or DB_PATH  # resolved at call time so tests can relocate DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=30)) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()


def upsert_project(project_id: str, title: str, **fields: Any) -> None:
    cols = {"topic", "case_study", "hook", "style", "aspect_ratio", "duration_sec", "source", "status"}
    data = {k: v for k, v in fields.items() if k in cols and v is not None}
    with connect() as conn:
        row = conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
        if row is None:
            keys = ["id", "title", "created_at", "updated_at", *data]
            conn.execute(
                f"INSERT INTO projects ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})",
                [project_id, title, now(), now(), *data.values()],
            )
        else:
            sets = ", ".join(f"{k}=?" for k in ["title", "updated_at", *data])
            conn.execute(f"UPDATE projects SET {sets} WHERE id=?", [title, now(), *data.values(), project_id])


def list_projects() -> list[dict[str, Any]]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM projects ORDER BY updated_at DESC")]


def known_topics(limit: int = 200) -> list[dict[str, str]]:
    """Titles and case studies already made, so new ideas never repeat them."""
    with connect() as conn:
        rows = conn.execute("SELECT title, topic, case_study FROM projects ORDER BY created_at DESC LIMIT ?", (limit,))
        return [{k: (r[k] or "") for k in ("title", "topic", "case_study")} for r in rows]


def set_published(project_id: str, platform: str, url: str) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO published VALUES (?,?,?)", (project_id, platform, url))


def set_stats(project_id: str, views: int | None, likes: int | None) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO analytics VALUES (?,?,?,?)", (project_id, views, likes, now()))


def top_performers(n: int = 3) -> list[dict[str, Any]]:
    """Best projects by views with the hook/style that produced them."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT p.id, p.title, p.hook, p.style, a.views, a.likes FROM analytics a JOIN projects p ON p.id=a.project_id "
            "WHERE a.views IS NOT NULL ORDER BY a.views DESC LIMIT ?",
            (n,),
        )
        return [dict(r) for r in rows]


def log_usage(provider: str, model: str, task: str, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
    ts = now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO llm_usage VALUES (?,?,?,?,?,?,?,?)",
            (ts, ts[:10], provider, model, task, input_tokens, output_tokens, cost_usd),
        )


def usage_summary(since_day: str | None = None) -> dict[str, Any]:
    with connect() as conn:
        q = "SELECT COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(output_tokens),0) o, COALESCE(SUM(cost_usd),0) c, COUNT(*) n FROM llm_usage"
        row = conn.execute(q + (" WHERE day>=?" if since_day else ""), (since_day,) if since_day else ()).fetchone()
        return {"input_tokens": row["i"], "output_tokens": row["o"], "cost_usd": row["c"], "calls": row["n"]}
