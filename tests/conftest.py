"""Keep tests away from the owner's real data/projects.db."""

from __future__ import annotations

from pathlib import Path

import pytest

from common import db


@pytest.fixture(autouse=True)
def _isolated_projects_db(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path_factory.mktemp("db") / "projects.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    return path
