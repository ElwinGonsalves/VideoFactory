"""Edit schedule.yaml safely (shared by the UI, the batch runner and the CLI)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from common import ROOT

SCHEDULE = ROOT / "scheduler" / "schedule.yaml"


def read(path: Path | None = None) -> dict[str, Any]:
    path = path or SCHEDULE
    return (yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None) or {}


def write(data: dict[str, Any], path: Path | None = None) -> None:
    """Atomic write: a crash mid-save can never leave a half-written schedule."""
    path = path or SCHEDULE
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)
    os.replace(tmp, path)


def add_job(job: dict[str, Any], path: Path | None = None) -> None:
    data = read(path)
    data.setdefault("jobs", [])
    if any(j["id"] == job["id"] for j in data["jobs"]):
        raise ValueError(f"a job with id {job['id']} already exists")
    data["jobs"].append({k: v for k, v in job.items() if v is not None})
    write(data, path)
