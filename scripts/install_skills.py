"""Install agent SKILL.md packs into .agent/skills/ by shallow-cloning their repos.

Only data is copied (directories that contain a SKILL.md). No third-party install
scripts are executed. Re-running refreshes every pack.

Usage: python scripts/install_skills.py
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / ".agent" / "skills"

# Packs from BUILD_SPEC.md section 3. Paid-API packs (vox-director, vox-explainer-skill,
# vox-ai-motion-graphics-generator) are deliberately excluded.
# iart-ai/motion-skills is only an index; its packs live in separate repos (listed below).
# kaomei/stickman-video-director is skipped: its default branch has no files.
REPOS = [
    "remotion-dev/skills",
    "iart-ai/explainer-video-skills",
    "iart-ai/tiktok-video-skills",
    "iart-ai/map-animation-skills",
    "iart-ai/kinetic-typography-skills",
    "iart-ai/data-animation-skills",
    "iart-ai/youtube-video-skills",
    "codepawl/creator-generalist",
    "charlie947/motion-graphics-skills",
    "connerkward/web-media-getter-skill",
    "charlesdove977/watchvideo",
    "lemomo-ai/lemo-opuscar",
]


def _rmtree(path: Path) -> None:
    def onerror(func, p, _exc):  # type: ignore[no-untyped-def]
        os.chmod(p, stat.S_IWRITE)
        func(p)

    shutil.rmtree(path, onerror=onerror)


def install(repo: str) -> int:
    name = repo.split("/")[1]
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        clone = Path(tmp) / name
        res = subprocess.run(
            ["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", str(clone)],
            capture_output=True,
            text=True,
            env=env,
        )
        if res.returncode != 0:
            print(f"SKIP {repo}: {res.stderr.strip().splitlines()[-1] if res.stderr else 'clone failed'}")
            return 0
        skill_files = [p for p in clone.rglob("SKILL.md") if ".git" not in p.parts]
        target = DEST / name
        if target.exists():
            _rmtree(target)
        for sk in skill_files:
            rel = sk.parent.relative_to(clone)
            out = target / rel
            shutil.copytree(sk.parent, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
        # keep license + readme for attribution
        for extra in ("LICENSE", "LICENSE.md", "README.md"):
            if (clone / extra).exists():
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(clone / extra, target / extra)
        _rmtree(clone)
    print(f"OK   {repo}: {len(skill_files)} skill(s)")
    return len(skill_files)


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    total = sum(install(r) for r in REPOS)
    print(f"installed {total} skills into {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
