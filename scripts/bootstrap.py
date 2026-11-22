"""Recreate everything that is gitignored, on a fresh clone. Safe to re-run.

    python scripts/bootstrap.py            # everything
    python scripts/bootstrap.py --studio   # just npm install in studio/
    flags: --python --gpu --studio --engines --publisher --music --skills --textures

Run it with the system Python; it creates .venv/ and installs into it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIN = os.name == "nt"
VENV_PY = ROOT / ".venv" / ("Scripts/python.exe" if WIN else "bin/python")

PY_PACKAGES = [
    "yt-dlp", "scenedetect", "opencv-python-headless", "faster-whisper", "edge-tts", "pydub", "requests",
    "pyyaml", "apscheduler", "tzdata", "soundfile", "numpy", "pillow", "ruff", "pytest",
]  # fmt: skip
PY_OPTIONAL = ["kokoro>=0.9", "handanim", "manim"]
# NVIDIA GPU: CUDA 12 runtime libs for faster-whisper (ctranslate2) + a CUDA torch build for Kokoro.
# The pip CUDA libs need only the NVIDIA driver, not a system CUDA Toolkit install.
GPU_LIBS = ["nvidia-cublas-cu12", "nvidia-cudnn-cu12"]
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
    sh([str(VENV_PY), "-m", "pip", "install", *PY_PACKAGES])
    if sh([str(VENV_PY), "-m", "pip", "install", *PY_OPTIONAL], check=False):
        print("! optional engines (kokoro/handanim/manim) failed to install; Remotion styles still work")


def do_gpu() -> None:
    if not shutil.which("nvidia-smi"):
        print("= no NVIDIA driver (nvidia-smi) found; skipping GPU libraries")
        return
    sh([str(VENV_PY), "-m", "pip", "install", *GPU_LIBS])
    torch_ver = subprocess.run(
        [str(VENV_PY), "-c", "import torch; print(torch.__version__.split('+')[0])"], capture_output=True, text=True
    ).stdout.strip()
    spec = f"torch=={torch_ver}" if torch_ver else "torch"
    # --no-deps keeps every other package as is; only the torch wheel is swapped for the CUDA build.
    if sh(
        [str(VENV_PY), "-m", "pip", "install", "--force-reinstall", "--no-deps", spec, "--index-url", TORCH_INDEX],
        check=False,
    ):
        print(f"! {spec} has no CUDA wheel at {TORCH_INDEX}; Kokoro stays on CPU")


def do_studio() -> None:
    sh(["npm.cmd" if WIN else "npm", "install", "--no-audit", "--no-fund"], cwd=ROOT / "studio")


def do_engines() -> None:
    for dest, url in ENGINES.items():
        clone(dest, url)


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


def main() -> int:
    steps = {
        "python": do_python,
        "gpu": do_gpu,
        "studio": do_studio,
        "engines": do_engines,
        "publisher": do_publisher,
        "music": lambda: sh([str(VENV_PY), "scripts/seed_music.py"]),
        "skills": lambda: sh([str(VENV_PY), "scripts/install_skills.py"]),
        "textures": lambda: sh([str(VENV_PY), "media_pipeline/fetch_free_media.py", "--make-textures"]),
    }
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in steps:
        p.add_argument(f"--{name}", action="store_true")
    a = p.parse_args()
    chosen = [n for n in steps if getattr(a, n)] or list(steps)
    for name in chosen:
        print(f"\n=== {name} ===")
        steps[name]()
    print("\nDone. Next: .venv python scripts/doctor.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
