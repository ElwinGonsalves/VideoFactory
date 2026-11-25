"""The Horde (batch): every row is considered, scripts-only mode, friendly spellings, per-row progress lines."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from batch import run as batch_run
from batch import sheet
from common import write_json
from prompts.script_templates import REGISTRY


def _row(**kw: str) -> dict[str, str]:
    return {"input_mode": "idea", "title": "", "content": "why prices end in 99", **kw}


@pytest.mark.parametrize(
    ("raw", "style", "aspect", "platforms"),
    [
        (
            {"style": "Case Study", "aspect_ratio": "vertical", "platforms": "yt, insta"},
            "case_study",
            "9:16",
            ["youtube", "instagram"],
        ),
        ({"style": "notebook", "aspect_ratio": "square"}, "hand_drawn", "1:1", ["youtube"]),
        (
            {"style": "kinetic", "aspect_ratio": "16x9", "platforms": "IG/TT"},
            "kinetic_type",
            "16:9",
            ["instagram", "tiktok"],
        ),
        ({"style": "long-form"}, "long_form", "16:9", ["youtube"]),
    ],
)
def test_friendly_spellings_are_understood(raw: dict, style: str, aspect: str, platforms: list[str]) -> None:
    r = sheet.validate_rows([_row(**raw)])[0]
    assert r["ok"], r["errors"]
    assert (r["data"]["style"], r["data"]["aspect_ratio"], r["data"]["platforms"]) == (style, aspect, platforms)


def test_language_and_length_columns() -> None:
    ok = sheet.validate_rows([_row(language="Hinglish", length="3m"), _row(language="", length="45s")])
    assert [r["data"]["language"] for r in ok] == ["hinglish", ""] and [r["data"]["length"] for r in ok] == [180, 45]
    bad = sheet.validate_rows([_row(language="klingon"), _row(length="forever"), _row(length="5")])
    assert all(not r["ok"] for r in bad)


def test_scripts_mode_writes_every_row_and_renders_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    written: list[str] = []
    monkeypatch.setattr(batch_run, "write_row", lambda d: written.append(d["content"]) or d["content"])
    monkeypatch.setattr(batch_run, "render_row", lambda *a: pytest.fail("scripts mode must not render"))
    monkeypatch.setattr(batch_run.notify, "send", lambda *a, **k: {})
    rows = [
        {"row": i + 2, "data": {"content": c, "title": c}, "upload_at": None} for i, c in enumerate(["a", "b", "c"])
    ]
    write_json(tmp_path / "b.json", {"mode": "scripts", "rows": rows})
    assert batch_run.main([str(tmp_path / "b.json")]) == 0
    assert written == ["a", "b", "c"]


def test_render_mode_writes_everything_first_and_reports_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:  # type: ignore[no-untyped-def]
    order: list[str] = []

    def write(d: dict[str, Any]) -> str:
        order.append(f"write:{d['content']}")
        if d["content"] == "bad":
            raise RuntimeError("model down")
        return d["content"]

    monkeypatch.setattr(batch_run, "write_row", write)
    monkeypatch.setattr(batch_run, "render_row", lambda slug, *a: order.append(f"render:{slug}"))
    monkeypatch.setattr(batch_run.notify, "send", lambda *a, **k: {})
    rows = [
        {"row": r, "data": {"content": c, "title": c}, "upload_at": None} for r, c in [(2, "x"), (3, "bad"), (4, "y")]
    ]
    write_json(tmp_path / "b.json", {"mode": "render", "rows": rows})
    assert batch_run.main([str(tmp_path / "b.json")]) == 1
    assert order == ["write:x", "write:bad", "write:y", "render:x", "render:y"]
    out = capsys.readouterr().out
    assert "ROW 3 FAILED model down" in out and "ROW 2 SCRIPT x" in out and "ROW 4 DONE y" in out


def test_shared_compositions_get_their_own_beats() -> None:
    beats = {
        s: REGISTRY.for_style(s).beat_ids
        for s in (
            "concept_explainer",
            "case_study",
            "kinetic_type",
            "vox_documentary",
            "editorial_map",
            "news_breakdown",
        )
    }
    assert len({tuple(b) for b in beats.values()}) == len(beats)  # all different
    assert REGISTRY.for_style("case_study").family == "concept"  # still a 9:16 explainer
    assert {t.label for t in REGISTRY.families()} >= {"Concept / Case Study", "Vox Documentary"}
