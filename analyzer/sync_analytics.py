"""Pull views/likes for published videos with yt-dlp and store them in data/projects.db.

    python analyzer/sync_analytics.py                       # every project with a saved URL
    python analyzer/sync_analytics.py --channel https://www.youtube.com/@me/shorts

The cookie uploader does not return the published URL, so you paste one per project (Library) or set a
channel URL; channel entries are matched to projects by title. The top 3 hooks/styles by views feed
the next idea prompts (llm.tasks.generate_ideas).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import db, run, settings, which  # noqa: E402


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def match_by_title(entries: list[dict[str, Any]], projects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Project id -> channel entry whose normalized title equals or contains the project's title."""
    out: dict[str, dict[str, Any]] = {}
    for p in projects:
        want = _norm(p["title"])
        if not want:
            continue
        for e in entries:
            have = _norm(str(e.get("title", "")))
            if have and (have == want or want in have or have in want):
                out[p["id"]] = e
                break
    return out


def _web_url(url: str) -> str:
    """Only http(s) URLs reach yt-dlp, and always after `--`, so a value like `--exec ...` is never an option."""
    url = str(url).strip()
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"not a web URL: {url[:80]!r}")
    return url


def fetch_video(url: str) -> dict[str, Any]:
    res = run([which("yt-dlp"), "--dump-json", "--skip-download", "--no-warnings", "--", _web_url(url)])
    return json.loads(res.stdout.strip().splitlines()[-1])


def fetch_channel(url: str) -> list[dict[str, Any]]:
    res = run([which("yt-dlp"), "--flat-playlist", "-J", "--no-warnings", "--", _web_url(url)])
    return list(json.loads(res.stdout).get("entries") or [])


def sync(channel: str = "") -> list[str]:
    log: list[str] = []
    projects = db.list_projects()
    with db.connect() as conn:
        urls = {r["project_id"]: r["url"] for r in conn.execute("SELECT project_id, url FROM published")}
    for pid, url in urls.items():
        try:
            info = fetch_video(url)
            db.set_stats(pid, info.get("view_count"), info.get("like_count"))
            log.append(f"{pid}: {info.get('view_count')} views, {info.get('like_count')} likes")
        except Exception as exc:  # noqa: BLE001 - one dead link must not stop the sync
            log.append(f"{pid}: failed ({str(exc)[-120:]})")
    channel = channel or settings.load().get("analytics", {}).get("channel_url", "")
    if channel:
        try:
            entries = fetch_channel(channel)
            for pid, e in match_by_title(entries, [p for p in projects if p["id"] not in urls]).items():
                if e.get("url"):
                    db.set_published(pid, "youtube", e["url"])
                    info = fetch_video(e["url"])
                    db.set_stats(pid, info.get("view_count"), info.get("like_count"))
                    log.append(f"{pid}: matched on channel, {info.get('view_count')} views")
        except Exception as exc:  # noqa: BLE001
            log.append(f"channel: failed ({str(exc)[-160:]})")
    if not urls and not channel:
        log.append("nothing to sync: paste a published URL per project or set a channel URL in Settings")
    return log


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--channel", default="")
    for line in sync(p.parse_args().channel):
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
