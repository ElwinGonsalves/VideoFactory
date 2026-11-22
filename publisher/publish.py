"""Zero-API uploader: wraps dreammis/social-auto-upload (Playwright + saved browser cookies).

- YouTube defaults to `--visibility unlisted` until you switch a video (or schedule.yaml) to public.
- Instagram is capped at 1-2 posts/day by the scheduler to avoid account challenges.
- Cookies live in publisher/social-auto-upload/cookies/ (gitignored). Never commit them.

social-auto-upload runs in its own venv (publisher/social-auto-upload/.venv) because it pins
older dependency versions than the main pipeline.

Usage:
    python publisher/publish.py login youtube --account main          # one-time, opens a browser
    python publisher/publish.py check youtube --account main
    python publisher/publish.py upload output/demo.meta.json --platform youtube --account main
    python publisher/publish.py upload output/demo.meta.json --platform youtube --visibility public
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import ROOT, read_json  # noqa: E402

SAU = ROOT / "publisher" / "social-auto-upload"
PLATFORMS = ("youtube", "instagram", "tiktok")


def sau_python() -> str:
    exe = SAU / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not exe.exists():
        raise FileNotFoundError("Publisher venv missing. Run `python scripts/bootstrap.py --publisher`.")
    return str(exe)


def _sau(args: list[str]) -> int:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    return subprocess.run([sau_python(), "sau_cli.py", *args], cwd=SAU, env=env).returncode


def _tiktok(action: str, account: str, meta: dict[str, Any] | None = None) -> int:
    """TikTok is not in sau_cli yet; drive its uploader module directly."""
    code = (
        "import asyncio,sys,json\n"
        "from uploader.tk_uploader.main_chrome import tiktok_setup, TiktokVideo\n"
        f"acc='cookies/tiktok_{account}.json'\n"
        f"action={action!r}\n"
        "if action=='upload':\n"
        "    m=json.loads(sys.argv[1])\n"
        "    ok=asyncio.run(tiktok_setup(acc, handle=False))\n"
        "    if not ok: sys.exit('TikTok cookie missing/expired: run login first')\n"
        "    asyncio.run(TiktokVideo(m['title'], m['file'], m.get('tags',[]), 0, acc).main())\n"
        "else:\n"
        "    ok=asyncio.run(tiktok_setup(acc, handle=action=='login'))\n"
        "    print('valid' if ok else 'invalid'); sys.exit(0 if ok else 1)\n"
    )
    extra = [json.dumps(meta)] if meta else []
    return subprocess.run([sau_python(), "-c", code, *extra], cwd=SAU).returncode


def login(platform: str, account: str) -> int:
    if platform == "tiktok":
        return _tiktok("login", account)
    return _sau([platform, "login", "--account", account, "--headed"])


def check(platform: str, account: str) -> int:
    if platform == "tiktok":
        return _tiktok("check", account)
    return _sau([platform, "check", "--account", account])


def upload(meta_path: Path, platform: str, account: str, visibility: str | None = None, headed: bool = False) -> int:
    meta = read_json(meta_path)
    video = Path(meta["file"])
    if not video.is_absolute():
        video = ROOT / video
    if not video.exists():
        raise FileNotFoundError(video)
    tags = ",".join(t.lstrip("#") for t in meta.get("tags", []))
    desc = f"{meta.get('description', '')}\n\n{meta.get('music_attribution', '')}".strip()
    runtime = ["--headed"] if headed else ["--headless"]
    if platform == "youtube":
        vis = visibility or meta.get("visibility") or "unlisted"
        return _sau(["youtube", "upload-video", "--account", account, "--file", str(video), "--title", meta["title"][:100],
                     "--desc", desc, "--tags", tags, "--visibility", vis, *runtime])  # fmt: skip
    if platform == "instagram":
        return _sau(["instagram", "upload-video", "--account", account, "--file", str(video),
                     "--title", meta["title"], "--desc", desc, "--tags", tags, "--headed"])  # fmt: skip
    if platform == "tiktok":
        return _tiktok("upload", account, {"title": meta["title"], "file": str(video), "tags": meta.get("tags", [])})
    raise ValueError(f"Unsupported platform {platform}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("login", "check"):
        s = sub.add_parser(name)
        s.add_argument("platform", choices=PLATFORMS)
        s.add_argument("--account", default="main")
    u = sub.add_parser("upload")
    u.add_argument("meta", type=Path, help="output/<slug>.meta.json")
    u.add_argument("--platform", choices=PLATFORMS, default="youtube")
    u.add_argument("--account", default="main")
    u.add_argument("--visibility", choices=["unlisted", "private", "public"])
    u.add_argument("--headed", action="store_true", help="Show the browser while uploading")
    a = p.parse_args(argv)
    if a.cmd == "login":
        return login(a.platform, a.account)
    if a.cmd == "check":
        return check(a.platform, a.account)
    return upload(a.meta, a.platform, a.account, a.visibility, a.headed)


if __name__ == "__main__":
    raise SystemExit(main())
