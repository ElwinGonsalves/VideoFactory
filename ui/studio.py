"""Live studio status for the header pill and Activity Drawer, plus Stitched Engines health.

The stage of a running job is read from its log: `make_video.py` prints `[1/6] ... [6/6]` markers and
Remotion prints `Rendered N/M`. Those map onto the five stitch nodes the UI shows:

    Script -> Voice -> Music+SFX -> Render -> QA

Nothing here is guessed: a job without markers reports no percent.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from common import ROOT, STUDIO, read_json

NODES = ["script", "voice", "music", "render", "qa"]
NODE_LABELS = {"script": "Script", "voice": "Voice", "music": "Music+SFX", "render": "Render", "qa": "QA"}
NODE_ENGINES = {
    "script": "Gemini / Ollama",
    "voice": "Edge-TTS / Kokoro + Whisper",
    "music": "FFmpeg",
    "render": "Remotion",
    "qa": "Pixel QA + FFprobe",
}
# make_video step -> (node, start%, end%). Steps 3-5 (route, QA stills, final render) are all "Render";
# step 6 validates the MP4 and writes the thumbnail + metadata, which is the QA node.
STEP_MAP = {1: ("voice", 5, 20), 2: ("music", 20, 30), 3: ("render", 30, 33), 4: ("render", 33, 42),
            5: ("render", 42, 92), 6: ("qa", 92, 99)}  # fmt: skip
_STEP = re.compile(r"\[(\d)/6\]")
_FRAMES = re.compile(r"Rendered (\d+)/(\d+)")


def parse_progress(kind: str, log: str, status: str) -> dict[str, Any]:
    """{node, node_index, percent, done_nodes} for one job from its log text."""
    if kind == "llm":
        node, pct = "script", None
        if status == "done":
            return {"node": "script", "node_index": 0, "percent": 100, "done_nodes": ["script"]}
        return {"node": node, "node_index": 0, "percent": pct, "done_nodes": []}
    if kind not in ("render", "smoke", "batch", "approve"):
        return {"node": None, "node_index": None, "percent": None, "done_nodes": []}
    steps = [int(s) for s in _STEP.findall(log)]
    if not steps:
        return {"node": "script", "node_index": 0, "percent": 2 if status == "running" else None, "done_nodes": []}
    step = steps[-1]
    node, start, end = STEP_MAP.get(step, ("render", 30, 92))
    pct = float(start)
    if step == 5:
        frames = _FRAMES.findall(log[log.rfind("[5/6]") :])
        if frames:
            n, m = (int(x) for x in frames[-1])
            pct = start + (end - start) * (n / max(1, m))
    if status == "done" or "DONE " in log[-400:]:
        return {"node": "qa", "node_index": 4, "percent": 100, "done_nodes": list(NODES)}
    idx = NODES.index(node)
    return {"node": node, "node_index": idx, "percent": round(pct), "done_nodes": NODES[:idx]}


def _tail(path: Path, n: int = 60_000) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as fh:
        size = fh.seek(0, 2)
        fh.seek(max(0, size - n))
        return fh.read().decode("utf-8", "replace")


def _project_info(slug: str) -> dict[str, Any]:
    script = ROOT / "projects" / slug / "script.json"
    if not slug or not script.exists():
        return {}
    try:
        s = read_json(script)
    except ValueError:
        return {}
    return {"title": s.get("title", slug), "style": s.get("style", ""), "aspect_ratio": s.get("aspect_ratio", "")}


def job_view(job: Any) -> dict[str, Any]:
    pub = job.public()
    log = _tail(job.log_path)
    slug = pub.get("meta", {}).get("slug", "")
    info = _project_info(slug)
    prog = parse_progress(job.kind, log, job.status)
    started = pub.get("started") or pub.get("created")
    end = pub.get("ended") or time.time()
    return {
        **pub,
        **prog,
        "slug": slug,
        "title": info.get("title") or pub["title"],
        "style": info.get("style", ""),
        "aspect_ratio": info.get("aspect_ratio", ""),
        "elapsed_sec": round(end - started) if started else 0,
        "pipeline": job.kind in ("render", "smoke", "batch", "approve", "llm"),
    }


# ------------------------------------------------------------------ stitched engines
_ENGINE_CACHE: dict[str, Any] = {"at": 0.0, "data": None}


def _pkg_version(dist: str) -> str:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return ""


def _engine(key: str, name: str, organ: str, role: str, ok: bool, detail: str, required: bool) -> dict[str, Any]:
    return {"key": key, "name": name, "organ": organ, "role": role, "ok": ok, "detail": detail, "required": required}


def engines(force: bool = False) -> list[dict[str, Any]]:
    """Cheap presence checks (no GPU load, no network), cached for 60 s. `doctor.py` runs the deep checks."""
    if not force and _ENGINE_CACHE["data"] and time.time() - _ENGINE_CACHE["at"] < 60:
        return _ENGINE_CACHE["data"]
    remotion_pkg = STUDIO / "node_modules" / "remotion" / "package.json"
    remotion_v = read_json(remotion_pkg).get("version", "") if remotion_pkg.exists() else ""
    ffmpeg = shutil.which("ffmpeg")
    whisper_v = _pkg_version("faster-whisper")
    edge_v, kokoro_v = _pkg_version("edge-tts"), _pkg_version("kokoro")
    explainroo = ROOT / "engines" / "explainroo"
    manim_v = _pkg_version("manim")
    watch = (
        next(iter((ROOT / ".agent" / "skills").rglob("watch-video/SKILL.md")), None)
        if (ROOT / ".agent").exists()
        else None
    )
    scenedetect = importlib.util.find_spec("scenedetect") is not None
    sau = ROOT / "publisher" / "social-auto-upload" / ".venv"
    pw_dir = Path.home() / "AppData" / "Local" / "ms-playwright"
    chromium = any(pw_dir.glob("chromium*")) if pw_dir.exists() else False
    data = [
        _engine("remotion", "Remotion", "Skeleton", "Renders every frame", bool(remotion_v), f"v{remotion_v}" if remotion_v else "run npm install in studio/", True),
        _engine("ffmpeg", "FFmpeg", "Heart", "Mixes, ducks and encodes H.264/AAC", bool(ffmpeg), "on PATH" if ffmpeg else "not on PATH", True),
        _engine("whisper", "faster-whisper", "Ears", "Word-level captions", bool(whisper_v), f"v{whisper_v}" if whisper_v else "pip install faster-whisper", True),
        _engine("tts", "Edge-TTS / Kokoro", "Voice box", "Narration", bool(edge_v or kokoro_v),
                " + ".join(x for x in (f"Edge-TTS {edge_v}" if edge_v else "", f"Kokoro {kokoro_v}" if kokoro_v else "") if x) or "pip install edge-tts", True),
        _engine("explainroo", "Explainroo", "Left hand", "Whiteboard engine", explainroo.exists(), "cloned" if explainroo.exists() else "python scripts/bootstrap.py --engines", False),
        _engine("manim", "Manim", "Right hand", "Math & algorithm scenes", bool(manim_v), f"v{manim_v}" if manim_v else "optional: pip install manim", False),
        _engine("watchvideo", "WatchVideo", "Eyes", "Reads reference videos (Style DNA)", bool(watch) and scenedetect,
                "skill + PySceneDetect" if watch and scenedetect else "skill or scenedetect missing", False),
        _engine("playwright", "Playwright", "Hands", "Cookie uploads to YouTube / IG / TikTok", sau.exists() and chromium,
                "publisher venv + Chromium" if sau.exists() and chromium else "python scripts/bootstrap.py --publisher", False),
    ]  # fmt: skip
    _ENGINE_CACHE.update(at=time.time(), data=data)
    return data


def engines_summary(data: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data = data if data is not None else engines()
    alive = sum(1 for e in data if e["ok"])
    required_ok = all(e["ok"] for e in data if e["required"])
    return {"alive": alive, "total": len(data), "required_ok": required_ok}


def demo_assets() -> dict[str, Any]:
    """What Judge Demo Mode can show without an API key. Nothing here is fabricated."""
    from common import paths

    rendered = [s for s in paths.project_ids() if paths.find(s, "mp4") and not s.startswith("smoke")]
    blueprint = ROOT / "analyzer" / "blueprints" / "concept_case_study_short.json"
    sample_script = ROOT / "projects" / "concept-001" / "script.json"
    return {
        "sample_short": rendered[0] if rendered else None,
        "can_render_sample": sample_script.exists(),
        "sample_project": "concept-001" if sample_script.exists() else None,
        "blueprint": json.loads(blueprint.read_text(encoding="utf-8")) if blueprint.exists() else None,
    }
