"""Where a project's rendered files live: output/<project_id>/<project_id>.{mp4,thumb.jpg,meta.json}.

Before v2 files sat flat in output/ (`output/<slug>.mp4`). The `find_*` helpers fall back to that
layout, and `scripts/migrate_output.py` moves old files into per-project folders.
"""

from __future__ import annotations

from pathlib import Path

from common import OUTPUT


def out_dir(slug: str) -> Path:
    return OUTPUT / slug


def video_path(slug: str) -> Path:
    return out_dir(slug) / f"{slug}.mp4"


def thumb_path(slug: str) -> Path:
    return out_dir(slug) / f"{slug}.thumb.jpg"


def meta_path(slug: str) -> Path:
    return out_dir(slug) / f"{slug}.meta.json"


def _legacy(slug: str, suffix: str) -> Path:
    return OUTPUT / f"{slug}{suffix}"


def find(slug: str, kind: str) -> Path | None:
    """kind: mp4 | thumb | meta. New layout first, then the old flat one."""
    new = {"mp4": video_path, "thumb": thumb_path, "meta": meta_path}[kind](slug)
    old = _legacy(slug, {"mp4": ".mp4", "thumb": ".thumb.jpg", "meta": ".meta.json"}[kind])
    for p in (new, old):
        if p.exists():
            return p
    return None


def project_ids() -> list[str]:
    """Every project with a meta.json, newest first (both layouts)."""
    found: dict[str, float] = {}
    if OUTPUT.exists():
        for p in OUTPUT.glob("*/*.meta.json"):
            found[p.parent.name] = max(found.get(p.parent.name, 0), p.stat().st_mtime)
        for p in OUTPUT.glob("*.meta.json"):
            found.setdefault(p.name.removesuffix(".meta.json"), p.stat().st_mtime)
    return [k for k, _ in sorted(found.items(), key=lambda kv: kv[1], reverse=True)]
