"""Recreate everything that is gitignored, on a fresh clone. Safe to re-run.

    python scripts/bootstrap.py            # everything
    python scripts/bootstrap.py --studio   # just npm install in studio/
    flags: --python --gpu --studio --engines --publisher --music --skills --assets --mcp

Run it with the system Python; it creates .venv/ and installs into it.
`scripts/setup_repos.ps1` / `scripts/setup_repos.sh` are thin wrappers for --engines --publisher.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIN = os.name == "nt"
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if WIN else "bin/python")
NPM = "npm.cmd" if WIN else "npm"

# NVIDIA GPU: CUDA 12 runtime libs for faster-whisper (ctranslate2) + a CUDA torch build for Kokoro.
# The pip CUDA libs need only the NVIDIA driver, not a system CUDA Toolkit install.
TORCH_INDEX = "https://download.pytorch.org/whl/cu132"  # needs driver >= 580 (CUDA 13.x)
ENGINES = {
    "engines/openmontage": "https://github.com/OpenMontageInc/OpenMontage.git",
    "engines/explainroo": "https://github.com/vincentsch/explainroo.git",
    "engines/clipper": "https://github.com/AbdulSamad94/clipsmith.git",
}
PUBLISHER = ("publisher/social-auto-upload", "https://github.com/dreammis/social-auto-upload.git")


def sh(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> int:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check).returncode


def _rm_readonly(func, path, _exc):  # type: ignore[no-untyped-def]
    os.chmod(path, stat.S_IWRITE)
    func(path)


def clone(dest: str, url: str) -> None:
    target = ROOT / dest
    if target.exists() and any(target.iterdir()):
        print(f"= {dest} exists")
        return
    sh(["git", "clone", "--depth", "1", url, str(target)])
    shutil.rmtree(target / ".git", onerror=_rm_readonly)  # vendored copy, no nested repo


def do_python() -> None:
    if not VENV_PY.exists():
        sh([sys.executable, "-m", "venv", str(ROOT / ".venv")])
    sh([str(VENV_PY), "-m", "pip", "install", "-U", "pip"])
    sh([str(VENV_PY), "-m", "pip", "install", "-r", "requirements.txt"])
    if sh([str(VENV_PY), "-m", "pip", "install", "-r", "requirements-optional.txt"], check=False):
        print("! optional engines (kokoro/handanim/manim) failed to install; Remotion styles still work")


def do_gpu() -> None:
    if not shutil.which("nvidia-smi"):
        print("= no NVIDIA driver (nvidia-smi) found; skipping GPU libraries (CPU works)")
        return
    sh([str(VENV_PY), "-m", "pip", "install", "-r", "requirements-gpu.txt"])
    torch_ver = subprocess.run(
        [str(VENV_PY), "-c", "import torch; print(torch.__version__.split('+')[0])"], capture_output=True, text=True
    ).stdout.strip()
    if not torch_ver:
        print("= torch not installed (Kokoro optional); skipping the CUDA torch swap")
        return
    # --no-deps keeps every other package as is; only the torch wheel is swapped for the CUDA build.
    if sh(
        [
            str(VENV_PY),
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "--no-deps",
            f"torch=={torch_ver}",
            "--index-url",
            TORCH_INDEX,
        ],
        check=False,
    ):
        print(f"! torch=={torch_ver} has no CUDA wheel at {TORCH_INDEX}; Kokoro stays on CPU")


def do_studio() -> None:
    sh([NPM, "install", "--no-audit", "--no-fund"], cwd=ROOT / "studio")


def do_engines() -> None:
    for dest, url in ENGINES.items():
        clone(dest, url)
    # explainroo is a Node app; its voice runtime/model download on first render (~100 MB, user cache).
    if (ROOT / "engines" / "explainroo" / "package.json").exists():
        sh([NPM, "install", "--no-audit", "--no-fund"], cwd=ROOT / "engines" / "explainroo", check=False)


def do_publisher() -> None:
    dest, url = PUBLISHER
    clone(dest, url)
    sau = ROOT / dest
    if not (sau / "conf.py").exists():
        shutil.copy2(sau / "conf.example.py", sau / "conf.py")
    py = sau / ".venv" / ("Scripts/python.exe" if WIN else "bin/python")
    if not py.exists():
        sh([sys.executable, "-m", "venv", str(sau / ".venv")])
    sh([str(py), "-m", "pip", "install", "-r", "requirements.txt"], cwd=sau)
    # requirements.txt lags pyproject.toml upstream; install both.
    sh(
        [str(py), "-m", "pip", "install", "tinycss2>=1.4.0,<2", "patchright==1.58.2", "segno>=1.6.6", "qrcode==8.2"],
        cwd=sau,
    )
    sh([str(py), "-m", "playwright", "install", "chromium"], cwd=sau)
    sh([str(py), "-m", "patchright", "install", "chromium"], cwd=sau)


def do_assets() -> None:
    """Offline textures, the synthesized SFX library, and the map data (if missing)."""
    sh([str(VENV_PY), "media_pipeline/fetch_free_media.py", "--make-textures"])
    sh(
        [
            str(VENV_PY),
            "-c",
            "import sys; sys.path.insert(0, '.'); from audio_pipeline.sfx import ensure_library; print(len(ensure_library()), 'sfx')",
        ]
    )
    if not (ROOT / "studio" / "public" / "geo" / "countries.geojson").exists():
        sh([str(VENV_PY), "scripts/fetch_geo.py"])


def do_mcp() -> None:
    """Workspace MCP config for the handanim whiteboard server (absolute venv path, gitignored)."""
    cfg = {
        "mcpServers": {
            "handanim": {
                "command": str(VENV_PY.resolve()),
                "args": ["-m", "aianim.mcp_server"],
                "disabled": False,
                "autoApprove": [],
            }
        }
    }
    dest = ROOT / ".kiro" / "settings" / "mcp.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"= {dest} exists (left unchanged)")
        return
    dest.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"wrote {dest}")


def main() -> int:
    steps = {
        "python": do_python,
        "gpu": do_gpu,
        "studio": do_studio,
        "engines": do_engines,
        "publisher": do_publisher,
        "music": lambda: sh([str(VENV_PY), "scripts/seed_music.py"]),
        "skills": lambda: sh([str(VENV_PY), "scripts/install_skills.py"]),
        "assets": do_assets,
        "mcp": do_mcp,
    }
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in steps:
        p.add_argument(f"--{name}", action="store_true")
    a = p.parse_args()
    chosen = [n for n in steps if getattr(a, n)] or list(steps)
    for name in chosen:
        print(f"\n=== {name} ===")
        steps[name]()
    print(
        "\nDone. Next: .venv\\Scripts\\python scripts\\doctor.py"
        if WIN
        else "\nDone. Next: .venv/bin/python scripts/doctor.py"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
