"""Ideas: no repeats from data/projects.db, brainstorm runs, card edits, analytics matching."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from analyzer import analyze_reference as ar
from analyzer import sync_analytics as sa
from common import db, read_json
from llm import tasks as T
from tests.test_llm import FakeProvider


@pytest.fixture(autouse=True)
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "data" / "projects.db")
    return tmp_path


def idea(title: str, case: str = "case") -> dict[str, Any]:
    return {"title": title, "hook": "h", "hook_visual": "v", "angle": "a", "case_study": case, "style": "case_study",
            "aspect_ratio": "16:9", "duration_sec": 70, "music_mood": "chill", "why_it_works": "w"}  # fmt: skip


def test_repeats_are_detected_by_title_or_case_study() -> None:
    hist = [
        {"title": "How Netflix survived Blockbuster", "case_study": "Netflix DVD mail versus Blockbuster late fees"}
    ]
    assert T.is_repeat("How Netflix Survived Blockbuster?", "x", hist)
    assert T.is_repeat("Totally new", "Netflix DVD mail versus Blockbuster late fees", hist)
    assert not T.is_repeat("Why Costco sells hot dogs", "Costco 1.50 hot dog", hist)


def test_generate_ideas_drops_repeats_and_fills_card_fields() -> None:
    db.upsert_project("netflix", "How Netflix survived Blockbuster", case_study="DVD mail", hook="h")
    reply = {"ideas": [idea("How Netflix survived Blockbuster", "DVD mail"), idea("Costco hot dogs", "Costco"),
                       idea("Lego near bankruptcy", "Lego 2003"), idea("Apple 1997 rescue", "Apple Microsoft deal")]}  # fmt: skip
    fake = FakeProvider(reply)
    ideas = T.generate_ideas(blueprint=None, provider=fake, history=db.known_topics(), top_performers=[])
    assert [i["title"] for i in ideas] == ["Costco hot dogs", "Lego near bankruptcy", "Apple 1997 rescue"]
    assert ideas[0]["aspect_ratio"] == "16:9" and ideas[0]["duration_sec"] == 70 and ideas[0]["hook_visual"] == "v"
    assert "Already made" in fake.prompts[0] and "How Netflix survived Blockbuster" in fake.prompts[0]


def test_top_performers_reach_the_prompt() -> None:
    db.upsert_project("a", "Alpha", hook="Stop doing this", style="vox_documentary")
    db.set_stats("a", 9000, 10)
    top = db.top_performers(3)
    fake = FakeProvider({"ideas": [idea("One"), idea("Two", "c2"), idea("Three", "c3")]})
    T.generate_ideas(blueprint=None, provider=fake, history=[], top_performers=top)
    assert "9000 views" in fake.prompts[0] and "Stop doing this" in fake.prompts[0]


def test_brainstorm_run_then_edit_and_approve(tmp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ar, "WORK", tmp_db / "work")
    monkeypatch.setattr(ar, "PROJECTS", tmp_db / "projects")
    fake = FakeProvider({"ideas": [idea("Alpha story"), idea("Beta story", "c2"), idea("Gamma story", "c3")]})
    monkeypatch.setattr(T, "get_provider", lambda *a, **k: fake)
    run = ar.start_brainstorm("founders", "", "")
    approval = read_json(run / "approval.json")
    assert approval["mode"] == "brainstorm" and approval["blueprint"] == ""
    assert len(read_json(run / "ideas.json")) == 3
    ar.edit_idea(run, 2, {"title": "Beta, reworded", "dismissed": True})
    assert read_json(run / "ideas.json")[1]["dismissed"] is True
    created = ar.approve_ideas(run, [1], write_scripts=False)
    script = read_json(ar.ROOT / created[0] / "script.json") if (ar.ROOT / created[0]).exists() else None
    assert script is None or script["title"] == "Alpha story"
    projects = db.list_projects()
    assert projects and projects[0]["title"] == "Alpha story" and projects[0]["status"] == "approved"
    assert "Alpha story" in [k["title"] for k in db.known_topics()]


def test_channel_entries_match_projects_by_title() -> None:
    entries = [
        {"title": "How Netflix survived Blockbuster | Shorts", "url": "https://y/1"},
        {"title": "Other", "url": "https://y/2"},
    ]
    projects = [
        {"id": "netflix", "title": "How Netflix survived Blockbuster"},
        {"id": "none", "title": "Missing video"},
    ]
    assert sa.match_by_title(entries, projects) == {"netflix": entries[0]}


def test_usage_summary_and_blueprint_listing(tmp_db: Path) -> None:
    db.log_usage("gemini", "m", "script", 1000, 500, 0.0054)
    s = db.usage_summary()
    assert s["input_tokens"] == 1000 and s["output_tokens"] == 500 and s["calls"] == 1
    assert any(b["name"] == "concept_case_study_short" for b in ar.list_blueprints())
