"""Health check: binaries, Python packages, Node/Remotion, music library, skills, engines, Playwright.

Usage: python scripts/doctor.py        (exit 0 when every REQUIRED check passes)
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common import MUSIC_LIBRARY, STUDIO, read_json  # noqa: E402

results: list[tuple[str, str, bool, str]] = []  # (level, name, ok, detail)


def check(name: str, ok: bool, detail: str = "", required: bool = True, hint: str = "") -> None:
    """`detail` is always shown; `hint` (how to fix) only when the check fails."""
    shown = detail if ok or not hint else f"{detail} -> {hint}".strip(" ->")
    results.append(("REQUIRED" if required else "optional", name, ok, shown))


def version(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except (OSError, IndexError, subprocess.TimeoutExpired):
        return ""


def check_binaries() -> None:
    py = sys.version_info
    check("python >= 3.10", py >= (3, 10), f"{py.major}.{py.minor}.{py.micro}")
    for b in ("ffmpeg", "ffprobe", "git"):
        path = shutil.which(b)
        check(
            b,
            bool(path),
            version([b, "-version"] if b.startswith("ff") else [b, "--version"]) if path else "not on PATH",
        )
    node = version(["node", "--version"]) if shutil.which("node") else ""
    m = re.match(r"v(\d+)", node)
    check("node >= 22", bool(m and int(m.group(1)) >= 22), node or "not on PATH")
    check("npx", bool(shutil.which("npx")), "")
    enc = (
        subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
        if shutil.which("ffmpeg")
        else ""
    )
    check("ffmpeg libx264 + aac", "libx264" in enc and " aac " in enc, "")
    filt = (
        subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        if shutil.which("ffmpeg")
        else ""
    )
    check("ffmpeg sidechaincompress + loudnorm", "sidechaincompress" in filt and "loudnorm" in filt, "")
    bundled = importlib.util.find_spec("espeakng_loader") is not None  # ships espeak-ng.dll with Kokoro's deps
    system = bool(shutil.which("espeak-ng"))
    detail = "system install" if system else "bundled via espeakng-loader" if bundled else ""
    check("espeak-ng (Kokoro non-English voices)", system or bundled, detail, required=False,
          hint="pip install kokoro (bundles it) or winget install eSpeak-NG.eSpeak-NG")  # fmt: skip
    check("gh CLI (repo create/push)", bool(shutil.which("gh")), required=False, hint="winget install GitHub.cli")


def check_python_packages() -> None:
    required = ["edge_tts", "faster_whisper", "scenedetect", "cv2", "yaml", "apscheduler", "requests",
                "soundfile", "numpy", "yt_dlp", "PIL"]  # fmt: skip
    for mod in required:
        check(f"py: {mod}", importlib.util.find_spec(mod) is not None)
    for mod in ("fastapi", "uvicorn", "multipart"):
        check(f"py: {mod} (web UI)", importlib.util.find_spec(mod) is not None, hint="pip install -r requirements.txt")
    for mod in ("kokoro", "manim", "handanim", "googleapiclient", "google_auth_oauthlib", "pytest", "ruff"):
        check(f"py: {mod}", importlib.util.find_spec(mod) is not None, required=False)


def check_llm() -> None:
    from common import settings

    cfg = settings.load()["llm"]
    provider = cfg["provider"]
    key = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    if key:
        ok = bool(settings.env(key))
        check(
            f"LLM: {provider} key",
            ok,
            cfg.get(f"{provider}_model", ""),
            required=False,
            hint=f"add {key} in the UI Settings tab",
        )
    else:
        import requests

        host = settings.env("OLLAMA_HOST", "http://127.0.0.1:11434")
        try:
            tags = requests.get(f"{host}/api/tags", timeout=3).json().get("models", [])
            names = [m["name"] for m in tags]
            check(
                "LLM: ollama",
                cfg["ollama_model"] in names,
                f"{len(names)} model(s) at {host}",
                required=False,
                hint=f"ollama pull {cfg['ollama_model']}",
            )
        except Exception:  # noqa: BLE001
            check("LLM: ollama", False, host, required=False, hint="install Ollama and start it")


def check_gpu() -> None:
    """Real checks: load a tiny Whisper model on CUDA, and run a torch op on CUDA."""
    import common  # noqa: F401 - registers pip-installed CUDA DLL folders

    try:
        import ctranslate2

        n = ctranslate2.get_cuda_device_count()
    except Exception:  # noqa: BLE001
        n = 0
    whisper_ok, whisper_detail = False, f"{n} CUDA device(s)"
    if n:
        try:
            import numpy as np
            from faster_whisper import WhisperModel

            model = WhisperModel("tiny.en", device="cuda", compute_type="float16")
            list(model.transcribe(np.zeros(16000, dtype=np.float32))[0])
            whisper_ok, whisper_detail = True, f"{n} CUDA device(s), float16"
        except Exception as exc:  # noqa: BLE001
            whisper_detail = f"{n} CUDA device(s) but load failed: {str(exc)[:70]}"
    check("GPU: faster-whisper", whisper_ok, whisper_detail, required=False,
          hint="pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 (CPU fallback works)")  # fmt: skip
    try:
        import torch

        ok = torch.cuda.is_available()
        detail = f"torch {torch.__version__}" + (f", {torch.cuda.get_device_name(0)}" if ok else "")
    except Exception as exc:  # noqa: BLE001
        ok, detail = False, str(exc)[:70]
    check("GPU: torch (Kokoro)", ok, detail, required=False,
          hint="python scripts/bootstrap.py --gpu (CPU works, slower)")  # fmt: skip


def check_studio() -> None:
    nm = STUDIO / "node_modules"
    check("studio/node_modules", nm.exists(), hint="cd studio; npm install")
    pkg = nm / "remotion" / "package.json"
    check("remotion installed", pkg.exists(), read_json(pkg)["version"] if pkg.exists() else "")
    check("typescript installed", (nm / "typescript").exists())
    for comp in ("ConceptExplainer", "VoxEditorial", "WhiteboardDraw", "UniversalCustom"):
        check(f"composition {comp}", (STUDIO / "src" / "compositions" / f"{comp}.tsx").exists())


def check_music() -> None:
    manifest = MUSIC_LIBRARY / "manifest.json"
    if not manifest.exists():
        check("music manifest", False, hint="python scripts/seed_music.py")
        return
    tracks = read_json(manifest).get("tracks", [])
    present = [t for t in tracks if (MUSIC_LIBRARY / t["file"]).exists()]
    moods = sorted({t["mood"] for t in present})
    check(
        "music library",
        len(present) > 0 and len(present) == len(tracks),
        f"{len(present)}/{len(tracks)} tracks, moods: {', '.join(moods)}",
    )


def check_assets() -> None:
    skills = list((ROOT / ".agent" / "skills").rglob("SKILL.md"))
    check("agent skills (.agent/skills)", len(skills) > 0, f"{len(skills)} SKILL.md files", required=False)
    check("steering file", (ROOT / ".kiro" / "steering" / "video-factory.md").exists())
    check(
        "map data (geo/countries.geojson)",
        (STUDIO / "public" / "geo" / "countries.geojson").exists(),
        hint="python scripts/fetch_geo.py",
    )
    check(
        "textures (studio/public/textures)",
        (STUDIO / "public" / "textures" / "paper_grain.png").exists(),
        required=False,
        hint="python scripts/bootstrap.py --assets (made automatically on first render)",
    )
    sfx = list((MUSIC_LIBRARY.parent / "sfx_library").glob("*.wav"))
    check(
        "sfx library",
        len(sfx) >= 8,
        f"{len(sfx)} sounds",
        required=False,
        hint="python scripts/bootstrap.py --assets (made automatically on first render)",
    )
    check(
        "handanim MCP config",
        (ROOT / ".kiro" / "settings" / "mcp.json").exists(),
        required=False,
        hint="python scripts/bootstrap.py --mcp",
    )
    check(
        "explainroo node_modules",
        (ROOT / "engines" / "explainroo" / "node_modules").exists(),
        required=False,
        hint="python scripts/bootstrap.py --engines",
    )
    for eng in ("openmontage", "explainroo", "clipper"):
        check(
            f"engine {eng}",
            (ROOT / "engines" / eng).exists(),
            required=False,
            hint="python scripts/bootstrap.py --engines",
        )


def check_publisher() -> None:
    sau = ROOT / "publisher" / "social-auto-upload"
    check(
        "social-auto-upload",
        (sau / "sau_cli.py").exists(),
        required=False,
        hint="python scripts/bootstrap.py --publisher",
    )
    venv_py = sau / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    check("publisher venv", venv_py.exists(), required=False, hint="python scripts/bootstrap.py --publisher")
    pw_root = (
        Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""))
        if os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        else (
            Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
            if os.name == "nt"
            else Path.home() / ".cache" / "ms-playwright"
        )
    )
    chromium = list(pw_root.glob("chromium*")) if pw_root.exists() else []
    check("playwright chromium", bool(chromium), str(pw_root), required=False)
    cookies = list((sau / "cookies").glob("*.json")) if (sau / "cookies").exists() else []
    check(
        "upload cookies",
        bool(cookies),
        f"{len(cookies)} account(s)",
        required=False,
        hint="python publisher/publish.py login youtube",
    )


def main() -> int:
    check_binaries()
    check_python_packages()
    check_llm()
    check_gpu()
    check_studio()
    check_music()
    check_assets()
    check_publisher()
    width = max(len(r[1]) for r in results)
    failed_required = 0
    for level, name, ok, detail in results:
        mark = "PASS" if ok else ("FAIL" if level == "REQUIRED" else "skip")
        failed_required += (not ok) and level == "REQUIRED"
        print(f"[{mark}] {name:<{width}}  {detail}")
    print()
    if failed_required:
        print(f"{failed_required} required check(s) failed. See docs/DEBUGGING.md.")
        return 1
    print("All required checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
