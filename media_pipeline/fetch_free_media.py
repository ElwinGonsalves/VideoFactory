"""Keyless visual asset fetcher (no Pexels, no API keys).

Tier 1, code-drawn primitives, lives in the Remotion components (charts, stat cards, SVG
draw-ons, paper cards). This module covers tiers 2 and 3:

  2. Open archives: Wikimedia Commons, Archive.org, NASA Image Library.
     Every download is cached by URL hash in media_pipeline/cache/ and recorded in
     <out>/attribution.json (source, title, author, license, url, page_url).
  3. Local textures: `--make-textures` writes paper grain, grid and chalkboard PNGs
     into media_pipeline/textures_cache/.

For more keyless sources (Openverse, Library of Congress), the installed skill
.agent/skills/web-media-getter-skill/webmedia.py supports `--source nokey`.

Usage:
    python media_pipeline/fetch_free_media.py "apollo 11 launch" --out projects/demo/assets/media
    python media_pipeline/fetch_free_media.py "1930s factory" --source archive --type video
    python media_pipeline/fetch_free_media.py --make-textures
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from common import ROOT, read_json, safe_replace, sha256_text, write_json  # noqa: E402

CACHE = ROOT / "media_pipeline" / "cache"
TEXTURES = ROOT / "media_pipeline" / "textures_cache"
HEADERS = {"User-Agent": "video-factory/1.0 (https://github.com/; local zero-API video tool)"}
TIMEOUT = 30
Record = dict[str, Any]


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def search_wikimedia(query: str, count: int, media_type: str) -> list[Record]:
    filetype = "bitmap|drawing" if media_type == "image" else "video"
    res = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": 6,
            "gsrsearch": f"{query} filetype:{filetype}",
            "gsrlimit": count * 2,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|mime",
            "iiurlwidth": 1920,
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    out = []
    for page in (res.json().get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        url = info.get("thumburl") if media_type == "image" else info.get("url")
        if not url:
            continue
        out.append(
            {
                "source": "wikimedia",
                "title": page.get("title", "").removeprefix("File:"),
                "author": _strip_html(meta.get("Artist", {}).get("value", "")),
                "license": meta.get("LicenseShortName", {}).get("value", "see page"),
                "url": url,
                "page_url": info.get("descriptionurl", ""),
                "type": media_type,
            }
        )
    return out[:count]


def search_archive(query: str, count: int, media_type: str) -> list[Record]:
    mediatype = "image" if media_type == "image" else "movies"
    res = requests.get(
        "https://archive.org/advancedsearch.php",
        params={
            "q": f"({query}) AND mediatype:{mediatype} AND (licenseurl:* OR rights:*public*)",
            "fl[]": ["identifier", "title", "creator", "licenseurl"],
            "rows": count,
            "output": "json",
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    exts = (".jpg", ".jpeg", ".png") if media_type == "image" else (".mp4",)
    out = []
    for doc in res.json().get("response", {}).get("docs", []):
        ident = doc["identifier"]
        meta = requests.get(f"https://archive.org/metadata/{ident}", headers=HEADERS, timeout=TIMEOUT).json()
        files = [f for f in meta.get("files", []) if f.get("name", "").lower().endswith(exts)]
        if not files:
            continue
        files.sort(key=lambda f: int(f.get("size", 0) or 0))
        pick = files[len(files) // 2] if media_type == "image" else files[0]
        creator = doc.get("creator", "")
        out.append(
            {
                "source": "internetarchive",
                "title": str(doc.get("title", ident)),
                "author": ", ".join(creator) if isinstance(creator, list) else str(creator),
                "license": str(doc.get("licenseurl", "public domain (per item rights)")),
                "url": f"https://archive.org/download/{ident}/{pick['name']}",
                "page_url": f"https://archive.org/details/{ident}",
                "type": media_type,
            }
        )
    return out


def search_nasa(query: str, count: int, media_type: str) -> list[Record]:
    res = requests.get(
        "https://images-api.nasa.gov/search",
        params={"q": query, "media_type": media_type, "page_size": count},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    out = []
    for item in res.json().get("collection", {}).get("items", [])[:count]:
        data = (item.get("data") or [{}])[0]
        nasa_id = data.get("nasa_id", "")
        assets = requests.get(item["href"], headers=HEADERS, timeout=TIMEOUT).json()
        want = ("~large.jpg", "~medium.jpg", "~orig.jpg") if media_type == "image" else ("~mobile.mp4", "~medium.mp4")
        url = next((a for suffix in want for a in assets if a.endswith(suffix)), None)
        if not url:
            continue
        out.append(
            {
                "source": "nasa",
                "title": data.get("title", nasa_id),
                "author": data.get("photographer") or data.get("center") or "NASA",
                "license": "NASA media (generally public domain; see guidelines)",
                "url": url.replace("http://", "https://"),
                "page_url": f"https://images.nasa.gov/details/{nasa_id}",
                "type": media_type,
            }
        )
    return out


SOURCES: dict[str, Callable[[str, int, str], list[Record]]] = {
    "wikimedia": search_wikimedia,
    "archive": search_archive,
    "nasa": search_nasa,
}


def download_cached(url: str) -> Path:
    """Download once; later calls reuse the file keyed by the URL's SHA-256."""
    CACHE.mkdir(parents=True, exist_ok=True)
    ext = Path(url.split("?")[0]).suffix.lower() or ".bin"
    dest = CACHE / f"{sha256_text(url)[:32]}{ext}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, headers=HEADERS, timeout=120, stream=True) as r:
        r.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in r.iter_content(1 << 16):
                fh.write(chunk)
    return safe_replace(tmp, dest)


def fetch(
    query: str,
    out_dir: Path,
    count: int = 3,
    media_type: str = "image",
    sources: list[str] | None = None,
) -> list[Record]:
    """Search keyless sources in order, download up to `count`, append to attribution.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    got: list[Record] = []
    for name in sources or list(SOURCES):
        if len(got) >= count:
            break
        try:
            results = SOURCES[name](query, count - len(got), media_type)
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"  {name}: skipped ({exc})", file=sys.stderr)
            continue
        for rec in results:
            try:
                cached = download_cached(rec["url"])
            except requests.RequestException as exc:
                print(f"  download failed {rec['url']}: {exc}", file=sys.stderr)
                continue
            dest = out_dir / cached.name
            if not dest.exists():
                shutil.copy2(cached, dest)
            got.append({**rec, "file": str(dest.relative_to(out_dir)), "query": query})
            if len(got) >= count:
                break
    attr_path = out_dir / "attribution.json"
    existing = read_json(attr_path) if attr_path.exists() else []
    known = {e["url"] for e in existing}
    write_json(attr_path, existing + [g for g in got if g["url"] not in known])
    return got


def make_textures(size: int = 1080) -> list[Path]:
    """Offline reusable backgrounds: paper grain, grid, chalkboard."""
    import numpy as np
    from PIL import Image

    TEXTURES.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 1, (size, size))
    paper = np.clip(np.stack([241 + noise * 6, 233 + noise * 6, 214 + noise * 6], -1), 0, 255)
    chalk = np.clip(np.stack([38 + noise * 5, 52 + noise * 5, 45 + noise * 5], -1), 0, 255)
    grid = np.full((size, size, 3), 251, dtype=np.float64)
    grid[::60, :, :] = 225
    grid[:, ::60, :] = 225
    out = []
    for name, arr in (("paper_grain.png", paper), ("chalkboard.png", chalk), ("grid.png", grid)):
        path = TEXTURES / name
        Image.fromarray(arr.astype("uint8")).save(path)
        out.append(path)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query", nargs="?")
    p.add_argument("--out", type=Path, default=ROOT / "media_pipeline" / "downloads")
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--type", dest="media_type", choices=["image", "video"], default="image")
    p.add_argument("--source", default="nokey", help="nokey (all keyless) or comma list: wikimedia,archive,nasa")
    p.add_argument("--make-textures", action="store_true")
    a = p.parse_args(argv)
    if a.make_textures:
        for path in make_textures():
            print(f"texture: {path}")
        if not a.query:
            return 0
    if not a.query:
        p.error("query is required unless --make-textures is given")
    sources = None if a.source in ("nokey", "all") else [s.strip() for s in a.source.split(",")]
    got = fetch(a.query, a.out, a.count, a.media_type, sources)
    for g in got:
        print(f"{g['source']:16} {g['file']}  ({g['license']})")
    print(f"{len(got)} file(s) -> {a.out} (attribution.json updated)")
    return 0 if got else 1


if __name__ == "__main__":
    raise SystemExit(main())
