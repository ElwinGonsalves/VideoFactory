"""Move v1 flat outputs (output/<slug>.mp4 ...) into output/<slug>/ and index them in data/projects.db.

    python scripts/migrate_output.py --dry-run     # show what would move
    python scripts/migrate_output.py               # back up first (see docs/DEBUGGING.md), then run
    python scripts/migrate_output.py --root <repo> [--dry-run]   # migrate another checkout's output/

What it does, per project: moves <slug>.mp4, <slug>.thumb.jpg, <slug>.meta.json into output/<slug>/,
rewrites the `file` and `thumbnail` paths inside meta.json, repoints scheduler/state.sqlite `meta_path`
values and `meta:` entries in scheduler/schedule.yaml, and upserts the project in data/projects.db.
Safe to run twice. Nothing is deleted; existing files in a target folder are never overwritten.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import OUTPUT, PROJECTS, ROOT, db, read_json, write_json  # noqa: E402

SUFFIXES = (".mp4", ".thumb.jpg", ".meta.json")


def set_root(root: Path) -> None:
    """Point every path this script touches (output/, projects/, scheduler/, data/projects.db) at `root`."""
    global ROOT, OUTPUT, PROJECTS
    ROOT, OUTPUT, PROJECTS = root, root / "output", root / "projects"
    db.DB_PATH = root / "data" / "projects.db"


def flat_slugs() -> list[str]:
    return sorted(p.name.removesuffix(".meta.json") for p in OUTPUT.glob("*.meta.json"))


def migrate_one(slug: str, dry: bool) -> list[str]:
    log: list[str] = []
    dest = OUTPUT / slug
    for suffix in SUFFIXES:
        src = OUTPUT / f"{slug}{suffix}"
        if not src.exists():
            continue
        target = dest / src.name
        if target.exists():
            log.append(f"  skip {src.name}: already in {dest.name}/")
            continue
        log.append(f"  move {src.name} -> {dest.name}/")
        if not dry:
            dest.mkdir(exist_ok=True)
            shutil.move(str(src), str(target))
    meta_path = dest / f"{slug}.meta.json"
    if not dry and meta_path.exists():
        meta = read_json(meta_path)
        meta["file"] = f"output/{slug}/{slug}.mp4"
        if meta.get("thumbnail"):
            meta["thumbnail"] = f"output/{slug}/{slug}.thumb.jpg"
        write_json(meta_path, meta)
        script = PROJECTS / slug / "script.json"
        s = read_json(script) if script.exists() else {}
        db.upsert_project(
            slug,
            meta.get("title") or s.get("title") or slug,
            style=s.get("style"),
            aspect_ratio=meta.get("aspect_ratio"),
            source="migrated",
            status="rendered",
        )
    return log


def repoint_state(dry: bool) -> list[str]:
    """scheduler/state.sqlite jobs.meta_path and schedule.yaml `meta:` values."""
    log: list[str] = []
    pattern = re.compile(r"output/([^/\\\s]+)\.meta\.json")

    def fix(value: str) -> str:
        return pattern.sub(lambda m: f"output/{m.group(1)}/{m.group(1)}.meta.json", value.replace("\\", "/"))

    state = ROOT / "scheduler" / "state.sqlite"
    if state.exists():
        with closing(sqlite3.connect(state, timeout=30)) as conn:
            for job_id, value in conn.execute("SELECT id, meta_path FROM jobs WHERE meta_path IS NOT NULL").fetchall():
                new = fix(value)
                if new != value.replace("\\", "/") or "\\" in value:
                    log.append(f"  state.sqlite job {job_id}: {value} -> {new}")
                    if not dry:
                        conn.execute("UPDATE jobs SET meta_path=? WHERE id=?", (new, job_id))
            conn.commit()
    sched = ROOT / "scheduler" / "schedule.yaml"
    if sched.exists():
        text = sched.read_text(encoding="utf-8")
        new_text = re.sub(
            r"(meta:\s*)(['\"]?)([^\n'\"]*output/[^/\n'\"]+\.meta\.json)",
            lambda m: f"{m.group(1)}{m.group(2)}{fix(m.group(3))}",
            text,
        )
        if new_text != text:
            log.append("  schedule.yaml: meta paths repointed")
            if not dry:
                sched.write_text(new_text, encoding="utf-8", newline="")
    return log


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--root", type=Path, default=ROOT, help="repo root to migrate (default: this checkout)")
    a = p.parse_args()
    root = a.root.expanduser().resolve()
    if not (root / "output").is_dir():
        print(f"no output/ folder in {root}", file=sys.stderr)
        return 2
    set_root(root)
    print(f"migrating {root}")
    slugs = flat_slugs()
    print(f"{len(slugs)} flat project(s) to migrate" + (" (dry run)" if a.dry_run else ""))
    for slug in slugs:
        print(slug)
        for line in migrate_one(slug, a.dry_run):
            print(line)
    for line in repoint_state(a.dry_run):
        print(line)
    print("done" if not a.dry_run else "dry run only: nothing changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
