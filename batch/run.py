"""Run a validated batch, strictly one video at a time (6 GB VRAM).

    python batch/run.py <batch.json>

batch.json: {"rows": [{"data": {...validated row...}, "upload_at": "iso|null"}]}
Each row: write/split the script -> render -> (auto_publish) add an upload job to schedule.yaml.
A failing row is logged and skipped; the batch carries on with the next one.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import PROJECTS, db, notify, paths, read_json, settings, write_json  # noqa: E402
from common.slugs import title_slug  # noqa: E402
from llm.tasks import script_from_text, write_script  # noqa: E402
from llm.usage import SpendLimitReached  # noqa: E402
from prompts.script_templates import default_aspect_for  # noqa: E402


def build_script(d: dict[str, Any]) -> dict[str, Any]:
    cfg = settings.load()
    prefs = cfg["defaults"]
    voice = {"engine": prefs["voice_engine"], "voice": d.get("voice") or prefs["voice"], "rate": prefs["rate"]}
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
            duration_sec=int(prefs["target_duration_sec"]), voice=voice, language=prefs["language"],
            grounding=ground, on_status=say,
        )  # fmt: skip
        if d["title"]:
            script["title"] = d["title"]
    script["platforms"] = d["platforms"]
    return script


def process_row(d: dict[str, Any], upload_at: str | None, produce: Any) -> str:
    """Returns the project slug. Raises on failure."""
    script = build_script(d)
    slug = title_slug(script["title"])
    project = PROJECTS / slug
    write_json(project / "script.json", script)
    db.upsert_project(slug, script["title"], topic=d["content"][:200], style=d["style"], aspect_ratio=script["aspect_ratio"],
                      source="batch", status="writing")  # fmt: skip
    produce(project)
    db.upsert_project(slug, script["title"], status="rendered")
    if d["auto_publish"]:
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
    return slug


def main(argv: list[str] | None = None) -> int:
    from make_video import produce

    spec = read_json(Path((argv or sys.argv[1:])[0]))
    rows = spec["rows"]
    done, failed = [], []
    stopped = ""
    for k, row in enumerate(rows, 1):
        title = row["data"].get("title") or row["data"]["content"][:40]
        print(f"[batch {k}/{len(rows)}] {title}", flush=True)
        try:
            slug = process_row(row["data"], row.get("upload_at"), produce)
            done.append(slug)
            print(f"[batch {k}/{len(rows)}] DONE {slug}", flush=True)
        except SpendLimitReached as exc:  # stop cleanly: finished rows stay finished, the rest wait for you
            stopped = str(exc)
            failed.extend(r["data"].get("title") or r["data"]["content"][:40] for r in rows[k - 1 :])
            print(f"[batch {k}/{len(rows)}] PAUSED: {exc}", flush=True)
            break
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the others
            failed.append(title)
            print(f"[batch {k}/{len(rows)}] FAILED {title}: {exc}\n{traceback.format_exc(limit=2)}", flush=True)
    print(f"BATCH finished: {len(done)} rendered, {len(failed)} failed", flush=True)
    notify.send(
        "video-factory: batch paused (spend limit)" if stopped else "video-factory: batch finished",
        [
            f"{len(done)} rendered, {len(failed)} not rendered",
            *([stopped] if stopped else []),
            *[f"ok: {s}" for s in done[:10]],
        ],
        {"Library": f"{notify.UI_URL}/#library"},
    )
    return 3 if stopped else (0 if not failed else 1)


if __name__ == "__main__":
    raise SystemExit(main())
