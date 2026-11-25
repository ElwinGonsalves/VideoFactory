"""Run a validated batch. Every row is considered, and rendering is strictly one video at a time (6 GB VRAM).

    python batch/run.py <batch.json>

batch.json: {"mode": "render" | "scripts", "rows": [{"row": 2, "data": {...validated row...}, "upload_at": "iso|null"}]}

Two phases, so every idea is safe before the slow part starts:
  1. write: every row becomes projects/<slug>/script.json (the Operating Table shows them all);
  2. render (mode "render" only): each written script renders in turn; auto_publish rows join the schedule.
A failing row is logged and skipped; the batch carries on. Hitting the spend limit stops writing new scripts,
and the scripts already written still render (rendering costs nothing).

Progress lines the Horde page reads (one per state change):
  [batch k/n] ROW <row> WRITING|SCRIPT <slug>|RENDERING <slug>|DONE <slug>|FAILED <reason>|PAUSED <reason>
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import PROJECTS, db, notify, paths, read_json, settings, voices, write_json  # noqa: E402
from common.slugs import title_slug  # noqa: E402
from llm.tasks import script_from_text, write_script  # noqa: E402
from llm.usage import SpendLimitReached  # noqa: E402
from prompts.script_templates import default_aspect_for  # noqa: E402


def build_script(d: dict[str, Any]) -> dict[str, Any]:
    cfg = settings.load()
    prefs = cfg["defaults"]
    language = voices.language_key(d.get("language") or prefs.get("language"))
    voice = {**voices.voice_for(d["style"], language, d.get("voice") or None), "rate": prefs["rate"]}
    aspect = default_aspect_for(d["style"]) or d["aspect_ratio"]
    ground = cfg["llm"].get("grounding", True)
    say = lambda m: print(f"    {m}", flush=True)  # noqa: E731
    if d["input_mode"] == "script":
        script = script_from_text(
            d["content"], title=d["title"], style=d["style"], aspect=aspect, mood=d["music_mood"], voice=voice,
            grounding=ground, on_status=say,
        )  # fmt: skip
    else:
        script = write_script(
            brief=d["content"], style=d["style"], aspect=aspect, mood=d["music_mood"],
            duration_sec=int(d.get("length") or prefs["target_duration_sec"]), voice=voice,
            language=voices.LANGUAGES[language]["prompt"], grounding=ground, on_status=say,
        )  # fmt: skip
        if d["title"]:
            script["title"] = d["title"]
    script["platforms"] = d["platforms"]
    script["language"] = language
    return script


def write_row(d: dict[str, Any]) -> str:
    """Write one row's script.json and return its project slug. Raises on failure."""
    script = build_script(d)
    slug = title_slug(script["title"])  # unique: a repeated title gets -2, -3 instead of overwriting
    write_json(PROJECTS / slug / "script.json", script)
    db.upsert_project(slug, script["title"], topic=d["content"][:200], style=d["style"], aspect_ratio=script["aspect_ratio"],
                      source="batch", status="written")  # fmt: skip
    return slug


def render_row(slug: str, d: dict[str, Any], upload_at: str | None, produce: Any) -> None:
    produce(PROJECTS / slug)
    db.upsert_project(slug, d.get("title") or slug, status="rendered")
    if d.get("auto_publish"):
        from scheduler import jobs

        meta = paths.find(slug, "meta")
        jobs.add_job(
            {
                "id": f"{slug}-batch",
                "type": "upload_only",
                "meta": meta.relative_to(paths.OUTPUT.parent).as_posix() if meta else str(paths.meta_path(slug)),
                "upload_at": upload_at,
                "platforms": d["platforms"],
            }
        )


def process_row(d: dict[str, Any], upload_at: str | None, produce: Any) -> str:
    """Write and render one row (kept for callers that handle a single row)."""
    slug = write_row(d)
    render_row(slug, d, upload_at, produce)
    return slug


def _say(k: int, n: int, row: Any, state: str, detail: str = "") -> None:
    print(f"[batch {k}/{n}] ROW {row} {state}{' ' + detail if detail else ''}", flush=True)


def main(argv: list[str] | None = None) -> int:
    spec = read_json(Path((argv or sys.argv[1:])[0]))
    rows = spec["rows"]
    mode = spec.get("mode", "render")
    n = len(rows)
    label = lambda r: r["data"].get("title") or r["data"]["content"][:40]  # noqa: E731
    written: list[tuple[int, dict[str, Any], str]] = []  # (index, row, slug)
    failed: list[str] = []
    stopped = ""

    # phase 1: every idea becomes a script on the slab
    for k, row in enumerate(rows, 1):
        rid = row.get("row", k)
        _say(k, n, rid, "WRITING", label(row))
        try:
            slug = write_row(row["data"])
            written.append((k, row, slug))
            _say(k, n, rid, "SCRIPT", slug)
        except SpendLimitReached as exc:  # stop writing; what is written still renders
            stopped = str(exc)
            for j, rest in enumerate(rows[k - 1 :], k):
                _say(j, n, rest.get("row", j), "PAUSED", stopped[:160])
                failed.append(label(rest))
            break
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the others
            failed.append(label(row))
            _say(k, n, rid, "FAILED", str(exc).splitlines()[0][:200] if str(exc) else type(exc).__name__)
            print(traceback.format_exc(limit=2), flush=True)

    # phase 2: bring them to life, one at a time
    rendered: list[str] = []
    if mode == "render" and written:
        from make_video import produce

        for k, row, slug in written:
            rid = row.get("row", k)
            _say(k, n, rid, "RENDERING", slug)
            try:
                render_row(slug, row["data"], row.get("upload_at"), produce)
                rendered.append(slug)
                _say(k, n, rid, "DONE", slug)
            except Exception as exc:  # noqa: BLE001
                failed.append(label(row))
                _say(
                    k, n, rid, "FAILED", f"render: {str(exc).splitlines()[0][:180] if str(exc) else type(exc).__name__}"
                )
                print(traceback.format_exc(limit=2), flush=True)

    summary = (
        f"BATCH finished: {len(written)} written, {len(rendered)} rendered, {len(failed)} failed"
        if mode == "render"
        else f"BATCH finished: {len(written)} scripts written (render them on the Operating Table), {len(failed)} failed"
    )
    print(summary, flush=True)
    notify.send(
        "video-factory: batch paused (spend limit)" if stopped else "video-factory: batch finished",
        [
            summary.removeprefix("BATCH finished: "),
            *([stopped] if stopped else []),
            *[f"ok: {s}" for s in (rendered or [s for _, _, s in written])[:10]],
        ],
        {"Vault": f"{notify.UI_URL}/#/library", "Operating Table": f"{notify.UI_URL}/#/render"},
    )
    return 3 if stopped else (0 if not failed else 1)


if __name__ == "__main__":
    raise SystemExit(main())
