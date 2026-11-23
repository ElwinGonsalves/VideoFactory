"""Shared helpers used by every video-factory module."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Tool output (Remotion progress glyphs, non-English captions) must never crash a run on a
# cp1252 Windows console or a redirected log file.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="replace")
# Windows without Developer Mode cannot symlink; the HF cache still works, so silence the warning.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def register_cuda_dlls() -> list[str]:
    """Expose pip-installed CUDA 12 libraries (nvidia-cublas-cu12, nvidia-cudnn-cu12) to ctranslate2.

    faster-whisper's GPU path loads cublas64_12.dll / cudnn64_9.dll by name, so their
    folders must be on PATH (and the DLL search path) before the first model loads.
    """
    if os.name != "nt":
        return []
    nvidia = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    dirs = [str(p) for p in sorted(nvidia.glob("*/bin")) if p.is_dir()] if nvidia.exists() else []
    for d in dirs:
        if d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        os.add_dll_directory(d)
    return dirs


CUDA_DLL_DIRS = register_cuda_dlls()
STUDIO = ROOT / "studio"
ASSETS = STUDIO / "public" / "assets"
OUTPUT = ROOT / "output"
PROJECTS = ROOT / "projects"
MUSIC_LIBRARY = ROOT / "audio_pipeline" / "music_library"


def ensure_root_on_path() -> None:
    """Allow `python some/script.py` to import the `common` package."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))


def sha256_text(*parts: str) -> str:
    """Stable content hash used as cache key."""
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_replace(src: Path, dest: Path, attempts: int = 20) -> Path:
    """os.replace with retries: OneDrive/antivirus briefly lock new files on Windows."""
    for i in range(attempts):
        try:
            src.replace(dest)
            return dest
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.25 * (i + 1))
    return dest


def which(binary: str) -> str:
    """Find a tool, preferring this venv's Scripts/bin (yt-dlp, ruff) over older global copies."""
    venv_bin = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")
    found = shutil.which(binary, path=str(venv_bin)) or shutil.which(binary)
    if not found:
        raise FileNotFoundError(f"`{binary}` not found on PATH. See docs/DEBUGGING.md.")
    return found


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a command, capturing text output. Raises with stderr on failure."""
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and res.returncode != 0:
        tail = (res.stderr or res.stdout)[-2000:]
        raise RuntimeError(f"Command failed ({res.returncode}): {' '.join(cmd)}\n{tail}")
    return res


def run_stream(cmd: list[str], cwd: Path | None = None, quiet: bool = False, env: dict[str, str] | None = None) -> None:
    """Run a command and echo its output live (\\r progress lines included) for the UI log viewer.

    `quiet` echoes only every 10th progress-style line. Raises with the output tail on failure.
    """
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env={**os.environ, **env} if env else None
    )
    assert proc.stdout is not None
    tail: list[str] = []
    buf = b""
    n = 0

    def emit(raw: bytes) -> None:
        nonlocal n
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            return
        tail.append(line)
        del tail[:-40]
        n += 1
        if not quiet or n % 10 == 0 or "error" in line.lower():
            print(line, flush=True)

    while True:
        chunk = proc.stdout.read1(4096)  # type: ignore[attr-defined]
        if not chunk:
            break
        buf += chunk
        *lines, buf = buf.replace(b"\r", b"\n").split(b"\n")
        for raw in lines:
            emit(raw)
    emit(buf)
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"Command failed ({code}): {' '.join(cmd)}\n" + "\n".join(tail[-20:]))


def ffprobe_json(path: Path) -> dict[str, Any]:
    out = run(
        [
            which("ffprobe"),
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
    ).stdout
    return json.loads(out)


def media_duration(path: Path) -> float:
    return float(ffprobe_json(path)["format"]["duration"])
