"""Local web UI: Create, Ideas, Library, Schedule, Settings.

    python ui/server.py                 # http://127.0.0.1:8765 (localhost only)
    python ui/server.py --host 0.0.0.0  # phone preview on your Wi-Fi (prints an access link)

Security: binds to 127.0.0.1 by default. Every /api call and media file needs the per-launch
session token (embedded in the page, or `?t=` for <video> tags), which blocks other websites
and other devices from driving your uploads. Secrets are written to .env and never sent back
unmasked.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import sqlite3
import subprocess
import sys
import webbrowser
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402
import yaml  # noqa: E402
from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response  # noqa: E402

from common import OUTPUT, PROJECTS, ROOT, paths, read_json, settings, write_json  # noqa: E402
from llm.tasks import VISUAL_TYPES  # noqa: E402
from pipeline.router import ROUTES  # noqa: E402
from prompts.script_templates import REGISTRY  # noqa: E402
from scheduler import builder, guard  # noqa: E402
from ui.jobs import JobManager  # noqa: E402
from ui.streaming import download_file, stream_file  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"  # legacy vanilla UI, served at /classic
DIST = ROOT / "frontend" / "dist"  # the React studio app (npm run build in frontend/)
TOKEN = secrets.token_urlsafe(24)
FILE_ROOTS = [OUTPUT, PROJECTS, ROOT / "analyzer" / "work", ROOT / "studio" / "public" / "assets"]
SCHEDULE = ROOT / "scheduler" / "schedule.yaml"


def _quiet_disconnects(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    """Windows' Proactor loop logs a traceback whenever a browser drops a connection early
    (seeking a video, closing a tab). That's normal; log everything else as usual."""
    if isinstance(context.get("exception"), (ConnectionResetError, ConnectionAbortedError)):
        return
    loop.default_exception_handler(context)


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    asyncio.get_running_loop().set_exception_handler(_quiet_disconnects)
    yield


app = FastAPI(title="video-factory", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
jobs = JobManager()
daemon: dict[str, subprocess.Popen[bytes] | None] = {"proc": None}


# ------------------------------------------------------------------ structured errors + CORS
HINTS = {
    400: "Check the highlighted field and try again.",
    401: "The session token is stale. Reload the page (the server restarted or the tab is old).",
    404: "That item no longer exists. Refresh the list.",
    409: "Another action is already using this. Wait for it to finish, then retry.",
    413: "The file is too large.",
    422: "Some input has the wrong shape. Check required fields.",
    429: "Too many requests. Wait a moment and retry.",
    503: "A local database is busy. Retry in a few seconds.",
}


def error_body(status: int, detail: Any, hint: str | None = None) -> dict[str, Any]:
    """Every API failure has this shape; the page shows `detail` and, below it, `hint`."""
    text = detail if isinstance(detail, str) else json.dumps(detail, default=str)[:400]
    default = "See the log panel or the server console for the full traceback." if status >= 500 else ""
    return {"detail": text, "hint": hint or HINTS.get(status, default)}


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(error_body(exc.status_code, exc.detail), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    parts = []
    for e in exc.errors()[:4]:
        where = ".".join(str(p) for p in e["loc"][1:]) or "body"
        parts.append(f"{where}: {e['msg']}")
    fields = "; ".join(parts)
    return JSONResponse(error_body(422, f"invalid request ({fields})"), status_code=422)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    import traceback

    traceback.print_exception(exc)
    return JSONResponse(
        error_body(
            500,
            f"{type(exc).__name__}: {str(exc)[:300]}",
            f"Unexpected server error on {request.url.path}. "
            "The full traceback is in the console running ui/server.py.",
        ),
        status_code=500,
    )


LOCAL_ORIGIN = r"^http://(127\.0\.0\.1|localhost):\d+$"  # this machine only; the session token still gates every call


@app.middleware("http")
async def require_token(request: Request, call_next):  # type: ignore[no-untyped-def]
    path = request.url.path
    host = request.headers.get("host", "").split(":")[0]
    if not LAN["enabled"] and host not in ("127.0.0.1", "localhost"):
        # DNS-rebinding guard: a hostile domain resolving to 127.0.0.1 still sends its own Host header.
        return JSONResponse(
            error_body(400, "bad host", "Open the UI at http://127.0.0.1:<port>/ or http://localhost:<port>/."),
            status_code=400,
        )
    origin = request.headers.get("origin")
    if origin and origin != f"http://{request.headers.get('host', '')}":
        # Cross-origin browser request (another site, or another app on a different localhost port). Rejected
        # before CORS so such a page cannot read "/" and lift the session token out of the HTML.
        return JSONResponse(
            error_body(403, "cross-origin request blocked", "Open the UI from its own address."), status_code=403
        )
    if path.startswith("/api/") or path.startswith("/files/"):
        supplied = request.headers.get("x-vf-token") or request.query_params.get("t")
        if not token_ok(supplied):
            return JSONResponse(error_body(401, "missing or wrong session token"), status_code=401)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"  # no clickjacking of Publish / Delete in a hidden iframe
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
    return response


def token_ok(supplied: str | None) -> bool:
    """Timing-safe token check that returns False (not a 500) for non-ASCII input."""
    return bool(supplied) and secrets.compare_digest(str(supplied).encode(), TOKEN.encode())


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=LOCAL_ORIGIN,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-VF-Token", "Content-Type", "Range"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Disposition"],
)


# ------------------------------------------------------------------ page + files
LAN = {"enabled": False}  # set by --host 0.0.0.0


@app.get("/", response_class=HTMLResponse)
def index(t: str = "") -> HTMLResponse:
    # On localhost the page carries the token (other sites cannot read it: same-origin policy).
    # On the LAN, the page itself needs the token link printed in the console.
    if LAN["enabled"] and not token_ok(t):
        return HTMLResponse(
            "<h3>video-factory: open the link printed in the console (it contains the access token).</h3>", 401
        )
    page = DIST / "index.html" if (DIST / "index.html").exists() else STATIC / "index.html"
    return HTMLResponse(page.read_text(encoding="utf-8").replace("__VF_TOKEN__", TOKEN))


@app.get("/classic", response_class=HTMLResponse)
def classic(t: str = "") -> HTMLResponse:
    """The pre-v3 vanilla UI, kept as a fallback (owner decision)."""
    if LAN["enabled"] and not token_ok(t):
        return HTMLResponse("<h3>video-factory: open the link printed in the console.</h3>", 401)
    return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8").replace("__VF_TOKEN__", TOKEN))


@app.get("/assets/{name:path}")
def dist_assets(name: str) -> FileResponse:
    root = (DIST / "assets").resolve()
    p = (root / name).resolve()
    if not p.is_relative_to(root) or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/styles/{name}")
def dist_style_card(name: str) -> FileResponse:
    """Style Picker images (real Remotion frames, scripts/render_style_cards.py)."""
    root = (DIST / "styles").resolve()
    p = (root / name).resolve()
    if p.parent != root or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/favicon.svg")
def favicon_svg() -> Response:
    p = DIST / "favicon.svg"
    return FileResponse(p) if p.exists() else HTMLResponse(FAVICON, media_type="image/svg+xml")


FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#ea580c"/>'
    '<path d="M12 9v14l11-7z" fill="#fff"/></svg>'
)


@app.get("/favicon.ico")
def favicon() -> HTMLResponse:
    return HTMLResponse(FAVICON, media_type="image/svg+xml")


@app.get("/static/{name}")
def static(name: str) -> FileResponse:
    p = (STATIC / name).resolve()
    if p.parent != STATIC.resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/files/{rel:path}")
def files(rel: str) -> FileResponse:
    p = (ROOT / rel).resolve()
    if not any(p.is_relative_to(r.resolve()) for r in FILE_ROOTS) or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, headers={"Cache-Control": "no-store"})


def rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


# ------------------------------------------------------------------ jobs
@app.get("/api/jobs")
def list_jobs() -> list[dict[str, Any]]:
    return jobs.list()


@app.get("/api/jobs/{job_id}/log")
def job_log(job_id: str, offset: int = 0) -> dict[str, Any]:
    job = jobs.jobs.get(job_id)
    if not job:
        raise HTTPException(404)
    text, new_offset = jobs.read_log(job_id, offset)
    return {"text": text, "offset": new_offset, "status": job.status, "job": job.public()}


# ------------------------------------------------------------------ studio status (pill + drawer)
def _upcoming(limit: int = 6) -> tuple[list[dict[str, Any]], int]:
    """Future generation/upload slots from schedule.yaml + state.sqlite, soonest first."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from scheduler import run_scheduler as rs

    sch = rs.load_schedule()
    tz = ZoneInfo(sch["defaults"]["timezone"])
    try:
        with closing(rs.connect()) as conn:
            gen = {r["id"]: r["gen_status"] for r in conn.execute("SELECT id, gen_status FROM jobs")}
            ups: dict[str, list[str]] = {}
            for r in conn.execute("SELECT job_id, status FROM uploads"):
                ups.setdefault(r["job_id"], []).append(r["status"])
    except sqlite3.OperationalError:
        gen, ups = {}, {}
    now = datetime.now(tz)
    slots: list[dict[str, Any]] = []
    scheduled = 0
    for j in sch["jobs"]:
        if j.get("enabled", True) is False:
            continue
        state = gen.get(j["id"], "pending")
        statuses = ups.get(j["id"], [])
        if statuses and all(s == "done" for s in statuses):
            continue
        scheduled += 1
        project = Path(str(j.get("meta") or j.get("script_or_prompt") or "")).stem.removesuffix(".meta")
        if not j.get("meta"):
            project = Path(str(j.get("script_or_prompt") or "")).parent.name
        base = {"job_id": j["id"], "title": _title_of(project) or j["id"], "platforms": j.get("platforms", ["youtube"])}
        if j.get("generate_at") and state == "pending" and j.get("type") != "upload_only":
            at = rs.parse_time(j["generate_at"], tz)
            if at:
                slots.append(
                    {**base, "kind": "generate", "at": at.isoformat(), "in_sec": int((at - now).total_seconds())}
                )
        if j.get("upload_at") and j.get("type") != "generate_only":
            at = rs.parse_time(j["upload_at"], tz)
            if at:
                held = "needs_review" in statuses
                slots.append(
                    {
                        **base,
                        "kind": "upload",
                        "at": at.isoformat(),
                        "in_sec": int((at - now).total_seconds()),
                        "held": held,
                    }
                )
    slots.sort(key=lambda s: s["at"])
    return slots[:limit], scheduled


@app.get("/api/studio")
def studio_status() -> dict[str, Any]:
    """One poll for the header pill and the Activity Drawer."""
    from ui import studio

    all_jobs = sorted(jobs.jobs.values(), key=lambda j: j.created, reverse=True)
    running = [studio.job_view(j) for j in all_jobs if j.status == "running"]
    queued = [studio.job_view(j) for j in all_jobs if j.status == "queued"]
    recent = [studio.job_view(j) for j in all_jobs if j.status in ("done", "failed", "cancelled")][:8]
    for r in recent:
        r["has_video"] = bool(r["slug"]) and paths.find(r["slug"], "mp4") is not None
    upcoming, scheduled = _upcoming()
    proc = daemon["proc"]
    return {
        "now": running[0] if running else None,
        "running": running,
        "queued": queued,
        "upcoming": upcoming,
        "scheduled": scheduled,
        "recent": recent,
        "daemon": bool(proc and proc.poll() is None),
        "nodes": [{"id": n, "label": studio.NODE_LABELS[n], "engine": studio.NODE_ENGINES[n]} for n in studio.NODES],
    }


@app.get("/api/engines")
def engines_health(refresh: bool = False) -> dict[str, Any]:
    from ui import studio

    data = studio.engines(force=refresh)
    return {"engines": data, **studio.engines_summary(data)}


@app.get("/api/onboarding")
def onboarding() -> dict[str, Any]:
    """What the first-run modal needs: is the brain connected, what can the demo show."""
    from llm.providers import PROVIDER_KEYS, PROVIDER_NAMES
    from ui import studio

    cfg = settings.load()["llm"]
    key = PROVIDER_KEYS.get(cfg["provider"])
    _pkg = studio._pkg_version
    return {
        "provider": cfg["provider"],
        "key_name": key,
        # a backup brain with a key (Settings > Backup brains) can write scripts too
        "key_set": (bool(settings.env(key)) if key else True)
        or any(settings.env(PROVIDER_KEYS[p]) for p in cfg.get("fallback_providers", []) if p in PROVIDER_KEYS),
        # what the organ transplant can offer (Stitched Engines)
        "brains": {p: (bool(settings.env(PROVIDER_KEYS[p])) if p in PROVIDER_KEYS else True) for p in PROVIDER_NAMES},
        "voices": {"edge-tts": bool(_pkg("edge-tts")), "kokoro": bool(_pkg("kokoro"))},
        "voice_engine": settings.load()["defaults"].get("voice_engine", "edge-tts"),
        "engines": studio.engines_summary(),
        "projects": len([p for p in PROJECTS.glob("*/script.json") if not p.parent.name.startswith("_")]),
        "rendered": len(paths.project_ids()),
        "demo": studio.demo_assets(),
    }


VOICE_CACHE = ROOT / ".cache" / "voice-preview"


def _voices_public() -> dict[str, Any]:
    from common import voices

    return voices.public()


@app.get("/api/voice/preview")
async def voice_preview(text: str = "", voice: str = "", style: str = "", language: str = "english") -> FileResponse:
    """A few seconds of a narrator (Edge-TTS, cached). For the Style Picker's ghost voice.

    No text: the style's own sample line. No voice: the style's narrator (or the language's default voice).
    """
    import hashlib

    from common import voices

    if voice and not all(c.isalnum() or c in "-_" for c in voice) or len(voice) > 60:
        raise HTTPException(400, "voice: letters, digits, - and _ only")
    if text and len(" ".join(text.split())) < 3:
        raise HTTPException(400, "text is too short to read aloud")
    text = " ".join((text or voices.sample_line(style, language)).split())[:220]
    voice = voices.voice_for(style, language, voice or None)["voice"]
    if "Neural" not in voice:  # a Kokoro voice id; the preview always speaks through Edge-TTS
        voice = voices.LANGUAGES[voices.language_key(language)]["default_voice"]
    VOICE_CACHE.mkdir(parents=True, exist_ok=True)
    dest = VOICE_CACHE / f"{hashlib.sha1(f'{voice}|{text}'.encode()).hexdigest()[:20]}.mp3"
    if not dest.exists() or dest.stat().st_size == 0:
        import edge_tts

        try:
            await asyncio.wait_for(edge_tts.Communicate(text, voice).save(str(dest)), timeout=25)
        except Exception as exc:  # noqa: BLE001 - edge_tts raises several transport errors
            dest.unlink(missing_ok=True)
            raise HTTPException(502, f"the voice did not answer ({type(exc).__name__})") from exc
    return FileResponse(dest, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/demo/batch")
def demo_batch() -> dict[str, Any]:
    """The sample workbook's rows, validated exactly like an upload (for Judge Demo Mode)."""
    from batch import sheet

    rows = sheet.read_upload("sample.xlsx", sheet.sample_xlsx())
    return {"raw": rows, "results": _batch_results(rows), "columns": sheet.COLUMNS, "sample": True}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, bool]:
    return {"ok": jobs.cancel(job_id)}


# ------------------------------------------------------------------ Create
def _slug_ok(slug: str) -> str:
    if not slug or not all(c.isalnum() or c in "-_" for c in slug) or len(slug) > 60:
        raise HTTPException(400, "slug: letters, digits, - and _ only")
    return slug


def _inside(rel_path: str, root: Path, field: str) -> Path:
    """A repo-relative path from a request, refused unless it resolves inside `root`."""
    p = (ROOT / rel_path).resolve()
    if not p.is_relative_to(root.resolve()):
        raise HTTPException(400, f"{field} must be inside {root.relative_to(ROOT).as_posix()}/")
    return p


@app.get("/api/options")
def options() -> dict[str, Any]:
    return {
        "styles": sorted(ROUTES),
        "aspects": ["9:16", "16:9", "1:1"],
        "moods": ["chill", "documentary", "upbeat", "dramatic"],
        "caption_styles": ["word_highlight", "phrase_box", "minimal_editorial", "none"],
        "platforms": ["youtube", "instagram", "tiktok"],
        "defaults": settings.load()["defaults"],
        "visual_types": VISUAL_TYPES,
        "templates": {s: REGISTRY.for_style(s).public() for s in sorted(ROUTES)},
        "grounding": settings.load()["llm"].get("grounding", True),
        **_voices_public(),
    }


@app.get("/api/projects")
def projects() -> list[dict[str, Any]]:
    out = []
    for p in sorted(PROJECTS.glob("*/script.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.parent.name.startswith("_"):
            continue
        try:
            s = read_json(p)
        except ValueError:
            continue
        out.append(
            {
                "slug": p.parent.name,
                "title": s.get("title", ""),
                "style": s.get("style", ""),
                "aspect_ratio": s.get("aspect_ratio", ""),
                "scenes": len(s.get("scenes", [])),
                "rendered": paths.find(p.parent.name, "mp4") is not None,
                "needs_approval": bool(s.get("blueprint")) and s.get("approval") != "approved",
                "language": s.get("language", "english"),
                "voice": (s.get("voice") or {}).get("voice", ""),
                "duration_sec": round(
                    sum(len(str(sc.get("narration", "")).split()) for sc in s.get("scenes", [])) / 2.6
                ),
                "mtime": p.stat().st_mtime,
            }
        )
    published = _published_ids()
    for row in out:
        row["published"] = row["slug"] in published
        # the three shelves on the Operating Table: written -> rendered -> out in the world
        row["stage"] = "published" if row["published"] else "rendered" if row["rendered"] else "script"
    return out


def _published_ids() -> set[str]:
    try:
        from common import db

        with closing(sqlite3.connect(db.DB_PATH)) as conn:
            return {r[0] for r in conn.execute("SELECT DISTINCT project_id FROM published")}
    except sqlite3.Error:
        return set()


@app.get("/api/projects/{slug}")
def get_project(slug: str) -> dict[str, Any]:
    p = PROJECTS / _slug_ok(slug) / "script.json"
    if not p.exists():
        raise HTTPException(404)
    return read_json(p)


@app.put("/api/projects/{slug}")
def save_project(slug: str, script: dict[str, Any] = Body(...)) -> dict[str, Any]:
    if not script.get("scenes"):
        raise HTTPException(400, "script needs at least one scene")
    proj = PROJECTS / _slug_ok(slug)
    proj.mkdir(parents=True, exist_ok=True)
    write_json(proj / "script.json", script)
    return {"ok": True, "slug": slug}


@app.post("/api/projects/write")
def write_script_job(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """mode=idea: the model writes the script. mode=script: your text is kept verbatim."""
    mode = body.get("mode", "idea")
    if mode not in ("idea", "script"):
        raise HTTPException(400, "mode must be idea or script")
    args = ["-m", "llm.cli", "write-script", "--mode", mode]
    label = ""
    if mode == "script":
        text = str(body.get("script", "")).strip()
        if len(text.split()) < 8:
            raise HTTPException(400, "paste your script (at least a couple of sentences)")
        if len(text) > 200_000:
            raise HTTPException(413, "script is too long")
        inbox = ROOT / "ui" / "logs" / "inputs"  # long scripts exceed the Windows command-line limit
        inbox.mkdir(parents=True, exist_ok=True)
        path = inbox / f"{secrets.token_hex(6)}.txt"
        path.write_text(text, encoding="utf-8")
        args += ["--text-file", str(path)]
        label = str(body.get("title") or text[:40])
    else:
        prompt = str(body.get("prompt", "")).strip()
        if not prompt:
            raise HTTPException(400, "write what the video should explain")
        args += ["--prompt", prompt]
        label = prompt[:60]
    if str(body.get("title", "")).strip():
        args += ["--title", str(body["title"]).strip()[:100]]
    for key, flag in (("slug", "--slug"), ("style", "--style"), ("aspect", "--aspect"), ("mood", "--mood")):
        if body.get(key):
            args += [flag, str(body[key])]
    if body.get("duration"):
        args += ["--duration", str(int(body["duration"]))]
    if body.get("platforms"):
        args += ["--platforms", ",".join(body["platforms"])]
    if body.get("overwrite"):
        args.append("--overwrite")
    from common import voices

    if body.get("language"):
        if body["language"] not in voices.LANGUAGES:
            raise HTTPException(400, f"language must be one of {', '.join(voices.LANGUAGES)}")
        args += ["--language", body["language"]]
    if body.get("voice"):
        if body["voice"] not in voices.VOICE_IDS:
            raise HTTPException(400, "unknown voice")
        args += ["--voice", body["voice"]]
    if "grounding" in body:
        args.append("--ground" if body["grounding"] else "--no-ground")
    return jobs.submit("llm", f"{'keep script' if mode == 'script' else 'write script'}: {label}", args).public()


@app.post("/api/projects/{slug}/render")
def render_job(slug: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    if not (PROJECTS / _slug_ok(slug) / "script.json").exists():
        raise HTTPException(404, "no script.json for that project")
    args = ["make_video.py", f"projects/{slug}"]
    for key, flag in (("style", "--style"), ("aspect", "--aspect"), ("mood", "--mood")):
        if body.get(key):
            args += [flag, str(body[key])]
    for key, flag in (("safe_zones", "--safe-zones"), ("strict_qa", "--strict-qa"), ("no_llm", "--no-llm")):
        if body.get(key):
            args.append(flag)
    job = jobs.submit("render", f"render {slug}", args, {"slug": slug})
    return job.public()


# ------------------------------------------------------------------ Ideas (reference videos)
VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".m4v")


@app.post("/api/analyze")
def analyze(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    urls = [u.strip() for u in body.get("urls", []) if str(u).strip()]
    if not urls:
        raise HTTPException(400, "add at least one link or file path")
    for u in urls:
        if u.startswith(("https://", "http://")):
            continue
        # Local files must be videos: the analyzer copies them under analyzer/work/ (served by /files/),
        # so any other path would let a caller copy out .env or cookie files.
        p = Path(u)
        if p.suffix.lower() not in VIDEO_EXTS or not p.is_file():
            raise HTTPException(400, f"not a URL or an existing video file ({', '.join(VIDEO_EXTS)}): {u}")
    style = str(body.get("style") or "my_style")
    if body.get("depth") in ("fast", "detailed"):  # plain labels in the UI; the analyzer's own mode names stay internal
        body["mode"] = {"fast": "hook", "detailed": "condensed"}[body["depth"]]
    args = [
        "analyzer/analyze_reference.py",
        "analyze",
        *urls,
        "--style",
        style,
        "--mode",
        str(body.get("mode", "condensed")),
    ]
    if body.get("topic"):
        args += ["--topic", str(body["topic"])]
    if body.get("confirm_large"):
        args.append("--yes")
    job = jobs.submit("analyze", f"analyze {len(urls)} reference(s) -> {style}", args)
    return job.public()


@app.get("/api/blueprints")
def blueprints() -> list[dict[str, Any]]:
    from analyzer.analyze_reference import list_blueprints

    return list_blueprints()


@app.post("/api/ideas/brainstorm")
def brainstorm(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    topic = str(body.get("topic", "")).strip()
    if not topic:
        raise HTTPException(400, "type a topic or niche to brainstorm from")
    args = ["analyzer/analyze_reference.py", "brainstorm", "--topic", topic]
    if body.get("blueprint"):
        args += ["--blueprint", str(body["blueprint"])]
    return jobs.submit("llm", f"brainstorm: {topic[:50]}", args).public()


@app.put("/api/ideas/{run}/{n}")
def edit_idea_card(run: str, n: int, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    from analyzer.analyze_reference import edit_idea

    try:
        return edit_idea(_run_dir(run), n, body)
    except KeyError as exc:
        raise HTTPException(404, "no such idea") from exc


@app.get("/api/ideas")
def ideas_runs() -> list[dict[str, Any]]:
    out = []
    work = ROOT / "analyzer" / "work"
    for run in sorted(work.glob("*/approval.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        d = run.parent
        approval = read_json(run)
        bp_path = ROOT / approval["blueprint"] if approval.get("blueprint") else None
        analyses = read_json(d / "analysis.json") if (d / "analysis.json").exists() else []
        sheets = [s for a in analyses for s in a.get("contact_sheets", [])]
        out.append(
            {
                "run": d.name,
                "status": approval.get("status"),
                "approved": approval.get("approved", []),
                "projects": approval.get("projects", []),
                "blueprint": read_json(bp_path) if bp_path and bp_path.exists() else {},
                "mode": approval.get("mode", "reference"),
                "topic": approval.get("topic", ""),
                "ideas": read_json(d / "ideas.json") if (d / "ideas.json").exists() else [],
                "sheets": sheets[:8],
                "sources": [a.get("source") for a in analyses],
            }
        )
    return out


def _run_dir(run: str) -> Path:
    d = (ROOT / "analyzer" / "work" / run).resolve()
    if not d.is_relative_to((ROOT / "analyzer" / "work").resolve()) or not (d / "approval.json").exists():
        raise HTTPException(404, "unknown analysis run")
    return d


@app.post("/api/ideas/{run}/propose")
def propose(run: str, body: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    d = _run_dir(run)
    code = (
        "import sys; from pathlib import Path; from analyzer.analyze_reference import propose_ideas; "
        f"ideas = propose_ideas(Path({str(d)!r}), {str(body.get('topic', ''))!r}, {settings.load()['defaults']['niche']!r}); "
        "[print(i['n'], i['title'], '|', i['hook']) for i in ideas]"
    )
    return jobs.submit("llm", f"5 ideas for {run}", ["-c", code]).public()


@app.post("/api/ideas/{run}/approve")
def approve(run: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    d = _run_dir(run)
    chosen = [int(n) for n in body.get("ideas", []) if str(n).isdigit() and 1 <= int(n) <= 5]
    if not chosen:
        raise HTTPException(400, "pick at least one idea")
    args = ["analyzer/analyze_reference.py", "approve", "--work", str(d), "--ideas", ",".join(map(str, chosen))]
    if body.get("render_after"):
        args.append("--render")  # project slugs come from the written titles, so the job renders them itself
    return jobs.submit("approve", f"approve ideas {chosen} ({run})", args).public()


# ------------------------------------------------------------------ Library
# ------------------------------------------------------------------ Batch
def _batch_results(raw: list[dict[str, str]]) -> list[dict[str, Any]]:
    from batch import sheet

    tz = _schedule_raw().get("defaults", {}).get("timezone", "Asia/Kolkata")
    return sheet.validate_rows(raw, tz)


@app.get("/api/batch/sample")
def batch_sample() -> Response:
    from batch import sheet

    return Response(
        sheet.sample_xlsx(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="video-factory-batch-sample.xlsx"'},
    )


@app.post("/api/batch/preview-file")
async def batch_preview_file(file: UploadFile = File(...)) -> dict[str, Any]:
    from batch import sheet

    raw = await file.read(5_000_001)  # read at most one byte past the limit
    if len(raw) > 5_000_000:
        raise HTTPException(413, "spreadsheet is larger than 5 MB")
    try:
        rows = sheet.read_upload(file.filename or "", raw)
    except Exception as exc:  # noqa: BLE001 - corrupt xlsx raises many types
        raise HTTPException(400, f"could not read the spreadsheet: {str(exc)[:160]}") from exc
    return {"raw": rows, "results": _batch_results(rows), "columns": sheet.COLUMNS}


@app.post("/api/batch/preview-url")
def batch_preview_url(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    from batch import sheet

    try:
        rows = sheet.fetch_google_sheet(str(body.get("url", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"could not download the sheet: {str(exc)[:160]}") from exc
    return {"raw": rows, "results": _batch_results(rows), "columns": sheet.COLUMNS}


@app.post("/api/batch/run")
def batch_run(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Validate again on the server, compute upload times, then run ONE job that renders rows one by one."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from batch import sheet

    mode = str(body.get("mode") or "render")
    if mode not in ("render", "scripts"):
        raise HTTPException(400, "mode must be render or scripts")
    results = [r for r in _batch_results(body.get("raw") or []) if r.get("data")]
    if body.get("skip_bad"):
        results = [r for r in results if r["ok"]]  # run the good rows now; the red ones wait for a fix
    if body.get("only_rows"):  # retry: just these sheet rows
        wanted = {int(x) for x in body["only_rows"]}
        results = [r for r in results if r["row"] in wanted]
    if not results:
        raise HTTPException(400, "no rows to run")
    if not all(r["ok"] for r in results):
        raise HTTPException(400, "fix the rows marked in red first, or skip them")
    try:
        step = sheet.parse_interval(str(body.get("interval", "1h")))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    tz = ZoneInfo(_schedule_raw().get("defaults", {}).get("timezone", "Asia/Kolkata"))
    start = datetime.now(tz)
    if body.get("start"):
        try:
            start = datetime.fromisoformat(str(body["start"]))
            start = start if start.tzinfo else start.replace(tzinfo=tz)
        except ValueError as exc:
            raise HTTPException(400, "first upload time is not a valid date/time") from exc
    times = sheet.upload_times(results, start, step)
    spec = {
        "mode": mode,
        "rows": [
            {"row": r["row"], "data": r["data"], "upload_at": t.isoformat() if t else None}
            for r, t in zip(results, times, strict=True)
        ],
    }
    inbox = ROOT / "ui" / "logs" / "inputs"
    inbox.mkdir(parents=True, exist_ok=True)
    path = inbox / f"batch-{secrets.token_hex(5)}.json"
    write_json(path, spec)
    label = (
        f"batch: write and render {len(results)} video(s), one at a time"
        if mode == "render"
        else f"batch: write {len(results)} script(s)"
    )
    return jobs.submit("batch", label, ["batch/run.py", str(path)]).public()


@app.post("/api/batch/render-written")
def batch_render_written(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Render scripts a script-only batch wrote (one job, one video at a time)."""
    slugs = [_slug_ok(str(s)) for s in body.get("slugs") or []]
    if not slugs:
        raise HTTPException(400, "no scripts to render")
    missing = [s for s in slugs if not (PROJECTS / s / "script.json").exists()]
    if missing:
        raise HTTPException(404, f"no script for: {', '.join(missing[:3])}")
    code = (
        "import sys; sys.path.insert(0, '.'); from make_video import produce; from pathlib import Path\n"
        f"slugs = {slugs!r}\n"
        "bad = 0\n"
        "for k, s in enumerate(slugs, 1):\n"
        "    print(f'[batch {k}/{len(slugs)}] ROW {s} RENDERING {s}', flush=True)\n"
        "    try:\n"
        "        produce(Path('projects') / s); print(f'[batch {k}/{len(slugs)}] ROW {s} DONE {s}', flush=True)\n"
        "    except Exception as exc:\n"
        "        bad += 1; print(f'[batch {k}/{len(slugs)}] ROW {s} FAILED render: {str(exc)[:180]}', flush=True)\n"
        "sys.exit(1 if bad else 0)\n"
    )
    return jobs.submit("batch", f"batch: render {len(slugs)} written script(s)", ["-c", code]).public()


# ------------------------------------------------------------------ analytics
@app.get("/api/analytics")
def analytics() -> dict[str, Any]:
    from common import db

    with db.connect() as conn:
        stats = {r["project_id"]: dict(r) for r in conn.execute("SELECT * FROM analytics")}
        urls = {r["project_id"]: r["url"] for r in conn.execute("SELECT project_id, url FROM published")}
    return {"stats": stats, "urls": urls, "top": db.top_performers(3)}


@app.put("/api/projects/{slug}/published")
def set_published_url(slug: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    from common import db

    url = str(body.get("url", "")).strip()
    if not url.startswith(("https://", "http://")):
        raise HTTPException(400, "paste the full https:// link of the published video")
    db.set_published(_slug_ok(slug), str(body.get("platform", "youtube")), url)
    return {"ok": True}


@app.post("/api/analytics/sync")
def sync_analytics() -> dict[str, Any]:
    return jobs.submit("llm", "sync analytics (yt-dlp)", ["analyzer/sync_analytics.py"]).public()


def _library_item(slug: str, full: bool = False) -> dict[str, Any] | None:
    meta_file = paths.find(slug, "meta")
    if meta_file is None:
        return None
    meta = read_json(meta_file)
    video, thumb = paths.find(slug, "mp4"), paths.find(slug, "thumb")
    item: dict[str, Any] = {
        "slug": slug,
        "title": meta.get("title", slug),
        "aspect_ratio": meta.get("aspect_ratio", ""),
        "style": "",
        "has_video": video is not None,
        "mtime": meta_file.stat().st_mtime,
        "qa_ok": meta.get("qa_ok"),
    }
    script_file = PROJECTS / slug / "script.json"
    script = read_json(script_file) if script_file.exists() else {}
    item["style"] = script.get("style", "")
    claims = script.get("claims", [])
    item["unverified"] = (
        sum(1 for c in claims if not c.get("verified")) if claims else len(meta.get("facts_to_verify", []))
    )
    if not full:
        return item
    qa_dir = PROJECTS / slug / "qa"
    report = read_json(qa_dir / "report.json") if (qa_dir / "report.json").exists() else None
    frames = [f for f in ("cover", "hook", "early", "mid", "outro") if (qa_dir / f"{f}.png").exists()]
    item.update(
        {
            "meta": meta,
            "thumbnail": rel(thumb) if thumb else None,
            "stream": f"/api/projects/{slug}/stream",
            "download": f"/api/projects/{slug}/download",
            "qa": report,
            "qa_frames": [
                {
                    "name": f,
                    "src": rel(qa_dir / f"{f}.png"),
                    "overlay": rel(qa_dir / f"{f}.overlay.png") if (qa_dir / f"{f}.overlay.png").exists() else None,
                }
                for f in frames
            ],
            "claims": claims,
            "grounded": script.get("grounded", False),
            "sources": script.get("sources", []),
            "facts_to_verify": meta.get("facts_to_verify", []),
        }
    )
    from common import db

    with db.connect() as conn:
        row = conn.execute("SELECT url FROM published WHERE project_id=? AND platform='youtube'", (slug,)).fetchone()
        stats = conn.execute("SELECT views, likes FROM analytics WHERE project_id=?", (slug,)).fetchone()
    item["published_url"] = row["url"] if row else ""
    item["stats"] = dict(stats) if stats else None
    return item


@app.get("/api/library")
def library(q: str = "", style: str = "", aspect: str = "", page: int = 1, per_page: int = 12) -> dict[str, Any]:
    """Light, paginated list (recent first). The Inspector loads one project at a time from /api/library/{slug}."""
    per_page = max(1, min(per_page, 50))
    needle = q.strip().lower()
    items = []
    for slug in paths.project_ids():
        item = _library_item(slug)
        if item is None:
            continue
        if needle and needle not in f"{slug} {item['title']}".lower():
            continue
        if style and item["style"] != style:
            continue
        if aspect and item["aspect_ratio"] != aspect:
            continue
        items.append(item)
    total = len(items)
    pages = max(1, -(-total // per_page))
    page = max(1, min(page, pages))
    return {
        "items": items[(page - 1) * per_page : page * per_page],
        "total": total,
        "page": page,
        "pages": pages,
        "styles": sorted({i["style"] for i in items if i["style"]}),
    }


@app.get("/api/library/{slug}")
def library_item(slug: str) -> dict[str, Any]:
    item = _library_item(_slug_ok(slug), full=True)
    if item is None:
        raise HTTPException(404, "no rendered video with that id")
    return item


@app.get("/api/projects/{slug}/stream")
def stream_video(slug: str, request: Request) -> Response:
    video = paths.find(_slug_ok(slug), "mp4")
    if video is None:
        raise HTTPException(404, "no video file for that project")
    return stream_file(video, request)


@app.get("/api/projects/{slug}/download")
def download_video(slug: str) -> Response:
    video = paths.find(_slug_ok(slug), "mp4")
    if video is None:
        raise HTTPException(404, "no video file for that project")
    return download_file(video, f"{slug}.mp4")


EDITABLE_META = (
    "title",
    "description",
    "hashtags",
    "tags",
    "visibility",
    "pinned_comment",
    "thumbnail_text",
    "platform_targets",
)


@app.put("/api/library/{slug}/meta")
def edit_meta(slug: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    meta_path = paths.find(_slug_ok(slug), "meta")
    if meta_path is None:
        raise HTTPException(404)
    meta = read_json(meta_path)
    edits = {k: body[k] for k in EDITABLE_META if k in body}
    if "hashtags" in edits:
        edits["hashtags"] = [("#" + str(h).lstrip("#")).replace(" ", "") for h in edits["hashtags"] if str(h).strip()]
    meta.update(edits)
    meta["metadata_source"] = "user"
    write_json(meta_path, meta)
    script_path = PROJECTS / slug / "script.json"
    if script_path.exists():  # keep edits across re-renders
        script = read_json(script_path)
        script["metadata"] = {**(script.get("metadata") or {}), **edits}
        write_json(script_path, script)
    return meta


@app.post("/api/library/{slug}/metadata")
def regen_meta(slug: str) -> dict[str, Any]:
    return jobs.submit("llm", f"metadata for {slug}", ["-m", "llm.cli", "metadata", "--slug", _slug_ok(slug)]).public()


@app.post("/api/library/{slug}/publish")
def publish(slug: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    platform = body.get("platform")
    if platform not in ("youtube", "instagram", "tiktok"):
        raise HTTPException(400, "platform must be youtube, instagram or tiktok")
    meta_file = paths.find(_slug_ok(slug), "meta")
    if meta_file is None:
        raise HTTPException(404, "render this video first")
    args = ["publisher/publish.py", "upload", rel(meta_file), "--platform", platform]
    if body.get("visibility") in ("unlisted", "private", "public"):
        args += ["--visibility", body["visibility"]]
    if body.get("method") in ("cookie", "api"):
        args += ["--method", body["method"]]
    if body.get("headed"):
        args.append("--headed")
    if body.get("force"):
        args.append("--force")
    return jobs.submit("publish", f"upload {slug} -> {platform}", args, {"slug": slug}).public()


# ------------------------------------------------------------------ Schedule
def _schedule_raw() -> dict[str, Any]:
    if not SCHEDULE.exists():
        return {}
    return yaml.safe_load(SCHEDULE.read_text(encoding="utf-8")) or {}


@app.get("/api/schedule")
def schedule() -> dict[str, Any]:
    from publisher import post_log
    from scheduler import run_scheduler as rs

    sch = rs.load_schedule()
    try:
        with closing(rs.connect()) as conn:
            rs.sync(conn, sch)
            state = {
                r["id"]: dict(r)
                for r in conn.execute("SELECT id, gen_status, gen_attempts, last_error, meta_path FROM jobs")
            }
            ups: dict[str, list[dict[str, Any]]] = {}
            for r in conn.execute("SELECT job_id, platform, status, attempts, next_at, last_error FROM uploads"):
                ups.setdefault(r["job_id"], []).append(dict(r))
            events = [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY at DESC LIMIT 25")]
        caps = {
            p: {"used": post_log.count_today(p), "cap": post_log.cap_for(p)} for p in ("youtube", "instagram", "tiktok")
        }
    except sqlite3.OperationalError as exc:  # another process is mid-write; the page just retries
        raise HTTPException(503, f"scheduler state is busy ({exc}); refresh in a moment") from exc
    proc = daemon["proc"]
    tz = sch["defaults"]["timezone"]
    prefs = settings.load()["scheduler"]
    with closing(rs.connect()) as conn:
        auth = guard.auth_overview(conn)
        held = {r["job_id"] for r in conn.execute("SELECT job_id FROM uploads WHERE status='needs_review'")}
    from common import db as _db

    with _db.connect() as dbc:
        links = {r["project_id"]: r["url"] for r in dbc.execute("SELECT project_id, url FROM published")}
    cards = []
    for j in _schedule_raw().get("jobs", []):
        st, upl = state.get(j["id"]), ups.get(j["id"], [])
        project = Path(str(j.get("script_or_prompt") or j.get("meta") or "")).parent.name
        if j.get("meta"):
            project = Path(j["meta"]).stem.removesuffix(".meta")
        cards.append(
            {
                **j,
                "state": st,
                "uploads": upl,
                "title": _title_of(project) or j["id"],
                "generate_human": builder.human_time(j.get("generate_at"), tz)
                if j.get("generate_at")
                else "as soon as possible",
                "upload_human": builder.human_time(j.get("upload_at"), tz)
                if j.get("upload_at")
                else "right after rendering",
                "step": _job_step(j, st, upl),
                "needs_review": j["id"] in held,
                "link": links.get(project, ""),
                "paused": j.get("enabled", True) is False,
            }
        )
    return {
        "defaults": sch["defaults"],
        "jobs": cards,
        "events": events,
        "caps": caps,
        "posts": post_log.recent(20),
        "daemon": bool(proc and proc.poll() is None),
        "preflight": {"keep_awake": prefs["keep_awake"], "safe_publish": prefs["safe_publish"], "auth": auth},
    }


STEPS = ["Queued", "Rendering", "Uploading", "Published"]


def _job_step(job: dict[str, Any], state: dict[str, Any] | None, uploads: list[dict[str, Any]]) -> int:
    """Current stage of a queue card: 0 queued, 1 rendering, 2 uploading (or waiting to), 3 published."""
    if uploads and all(u["status"] == "done" for u in uploads):
        return 3
    if any(u["status"] == "running" for u in uploads):
        return 2
    gen = (state or {}).get("gen_status", "pending")
    if gen == "running":
        return 1
    if gen in ("done", "skipped"):
        return 2
    return 0


def _title_of(project: str) -> str:
    script = PROJECTS / project / "script.json" if project else None
    if script and script.exists():
        try:
            return str(read_json(script).get("title", ""))
        except ValueError:
            return ""
    meta = paths.find(project, "meta") if project else None
    return str(read_json(meta).get("title", "")) if meta else ""


def _write_schedule(data: dict[str, Any]) -> None:
    from scheduler import jobs as sched_jobs

    sched_jobs.write(data, SCHEDULE)


@app.post("/api/schedule/jobs")
def add_schedule_job(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    data = _schedule_raw()
    data.setdefault("defaults", {})
    data.setdefault("jobs", [])
    jid = _slug_ok(str(body.get("id", "")))
    if any(j["id"] == jid for j in data["jobs"]):
        raise HTTPException(400, "a job with that id exists")
    project = _slug_ok(str(body.get("project") or jid))
    kind = body.get("type", "generate_and_upload")
    if kind not in ("generate_and_upload", "generate_only", "upload_only"):
        raise HTTPException(400, "type must be generate_and_upload, generate_only or upload_only")
    script = str(body.get("script_or_prompt") or f"projects/{project}/script.json")
    if script.endswith(".json") or "/" in script or "\\" in script:
        _inside(script, PROJECTS, "script_or_prompt")  # a path must stay in projects/; plain text is a prompt
    job = {
        "id": jid,
        "enabled": bool(body.get("enabled", True)),
        "type": kind,
        "script_or_prompt": script,
        "generate_at": body.get("generate_at") or None,
        "upload_at": body.get("upload_at") or None,
        "platforms": body.get("platforms") or ["youtube"],
    }
    if body.get("visibility"):
        job["visibility"] = body["visibility"]
    if job["type"] == "upload_only":
        found = paths.find(project, "meta")
        meta = str(body.get("meta") or (rel(found) if found else f"output/{project}/{project}.meta.json"))
        # The meta file names the video that gets uploaded, so it must be one of ours.
        if not meta.endswith(".meta.json"):
            raise HTTPException(400, "meta must be an output/<id>/<id>.meta.json file")
        _inside(meta, OUTPUT, "meta")
        job["meta"] = meta
    data["jobs"].append({k: v for k, v in job.items() if v is not None})
    _write_schedule(data)
    return {"ok": True}


@app.put("/api/schedule/jobs/{job_id}")
def update_schedule_job(job_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    data = _schedule_raw()
    for j in data.get("jobs", []):
        if j["id"] == job_id:
            for k in ("enabled", "generate_at", "upload_at", "platforms", "visibility"):
                if k in body:
                    j[k] = body[k]
            _write_schedule(data)
            return {"ok": True}
    raise HTTPException(404)


@app.delete("/api/schedule/jobs/{job_id}")
def delete_schedule_job(job_id: str) -> dict[str, Any]:
    data = _schedule_raw()
    before = len(data.get("jobs", []))
    data["jobs"] = [j for j in data.get("jobs", []) if j["id"] != job_id]
    if len(data["jobs"]) == before:
        raise HTTPException(404)
    _write_schedule(data)
    return {"ok": True}


@app.put("/api/schedule/defaults")
def schedule_defaults(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    data = _schedule_raw()
    allowed = {
        "timezone",
        "youtube_visibility",
        "instagram_daily_cap",
        "youtube_daily_cap",
        "tiktok_daily_cap",
        "account",
    }
    data["defaults"] = {**(data.get("defaults") or {}), **{k: v for k, v in body.items() if k in allowed}}
    _write_schedule(data)
    return data["defaults"]


@app.put("/api/schedule/preflight")
def put_preflight(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    update = {k: bool(body[k]) for k in ("keep_awake", "safe_publish") if k in body}
    return settings.save_prefs({"scheduler": update})["scheduler"]


@app.post("/api/schedule/check-auth")
def schedule_check_auth(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    platform = body.get("platform")
    if platform not in ("youtube", "instagram", "tiktok"):
        raise HTTPException(400, "platform must be youtube, instagram or tiktok")
    return jobs.submit(
        "login", f"check {platform} session", ["scheduler/run_scheduler.py", "check-auth", platform]
    ).public()


@app.post("/api/schedule/release/{job_id}")
def release_held(job_id: str) -> dict[str, Any]:
    """Approve a video the Safe-Publish Gate held, after the facts have been checked by a human."""
    from scheduler import run_scheduler as rs

    with closing(rs.connect()) as conn:
        n = conn.execute(
            "UPDATE uploads SET status='pending' WHERE job_id=? AND status='needs_review'", (_slug_ok(job_id),)
        ).rowcount
        if not n:
            raise HTTPException(404, "that job is not waiting for review")
        rs.event(conn, job_id, "review_approved", "facts checked by you; upload released")
        conn.commit()
    return {"ok": True, "released": n}


def _builder_plan(body: dict[str, Any]) -> list[dict[str, Any]]:
    slugs = [_slug_ok(str(s)) for s in body.get("projects", [])]
    if not slugs:
        raise HTTPException(400, "pick at least one video")
    tz = _schedule_raw().get("defaults", {}).get("timezone", "Asia/Kolkata")
    try:
        return builder.plan(
            slugs,
            first=str(body.get("first", "now")),
            spacing=str(body.get("spacing", "1h")),
            mode=str(body.get("mode", "all_now")),
            tz_name=tz,
            lead_min=int(body.get("lead_min", builder.RENDER_LEAD_MIN)),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/schedule/builder/preview")
def builder_preview(body: dict[str, Any] = Body(...)) -> list[dict[str, Any]]:
    tz = _schedule_raw().get("defaults", {}).get("timezone", "Asia/Kolkata")
    return [
        {
            "slug": e["slug"],
            "title": _title_of(e["slug"]) or e["slug"],
            "upload_at": e["upload_at"].isoformat(),
            "upload_human": builder.human_time(e["upload_at"], tz),
            "generate_human": builder.human_time(e["generate_at"], tz) if e["generate_at"] else "now",
            "rendered": paths.find(e["slug"], "meta") is not None,
        }
        for e in _builder_plan(body)
    ]


@app.post("/api/schedule/builder")
def builder_create(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    import time as _time

    from scheduler import jobs as sched_jobs

    platforms = body.get("platforms") or ["youtube"]
    made = []
    for e in _builder_plan(body):
        slug = e["slug"]
        meta = paths.find(slug, "meta")
        job: dict[str, Any] = {
            "id": f"{slug}-{int(_time.time()) % 100000}",
            "type": "upload_only" if meta else "generate_and_upload",
            "upload_at": e["upload_at"].isoformat(),
            "platforms": platforms,
        }
        if meta:
            job["meta"] = rel(meta)
        else:
            if not (PROJECTS / slug / "script.json").exists():
                raise HTTPException(404, f"no script for {slug}")
            job["script_or_prompt"] = f"projects/{slug}/script.json"
            job["generate_at"] = e["generate_at"].isoformat() if e["generate_at"] else None
        if body.get("visibility"):
            job["visibility"] = body["visibility"]
        sched_jobs.add_job(job, SCHEDULE)
        made.append(job["id"])
    return {"ok": True, "jobs": made}


@app.post("/api/schedule/run/{job_id}")
def run_scheduled_now(job_id: str) -> dict[str, Any]:
    return jobs.submit(
        "render", f"run-now {job_id}", ["scheduler/run_scheduler.py", "run-now", _slug_ok(job_id)]
    ).public()


@app.post("/api/schedule/retry/{job_id}")
def retry_scheduled(job_id: str) -> dict[str, Any]:
    return jobs.submit("llm", f"retry {job_id}", ["scheduler/run_scheduler.py", "retry", _slug_ok(job_id)]).public()


@app.post("/api/schedule/daemon")
def toggle_daemon(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    proc = daemon["proc"]
    running = bool(proc and proc.poll() is None)
    if body.get("run") and not running:
        log = (ROOT / "scheduler" / "logs").resolve()
        log.mkdir(parents=True, exist_ok=True)
        daemon["proc"] = subprocess.Popen(
            [sys.executable, "scheduler/run_scheduler.py", "daemon"],
            cwd=ROOT,
            stdout=(log / "ui_daemon.log").open("ab"),
            stderr=subprocess.STDOUT,
        )
    elif not body.get("run") and running and proc:
        proc.terminate()
        daemon["proc"] = None
    return {"daemon": body.get("run", False)}


# ------------------------------------------------------------------ Settings
@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    from publisher import official_apis

    view = settings.public_view()
    sau_cookies = ROOT / "publisher" / "social-auto-upload" / "cookies"
    view["cookie_accounts"] = sorted(p.stem for p in sau_cookies.glob("*.json")) if sau_cookies.exists() else []
    view["api_status"] = official_apis.status()
    return view


@app.put("/api/settings/prefs")
def put_prefs(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    allowed = {"llm", "defaults", "publish", "analytics"}
    channel = str((body.get("analytics") or {}).get("channel_url") or "").strip()
    if channel and not channel.startswith(("https://", "http://")):
        # It reaches yt-dlp's argument list; "--exec ..." would otherwise be read as an option.
        raise HTTPException(400, "channel URL must start with https://")
    return settings.save_prefs({k: v for k, v in body.items() if k in allowed})


@app.put("/api/settings/secrets")
def put_secrets(body: dict[str, str] = Body(...)) -> dict[str, Any]:
    try:
        settings.save_env({k: str(v) for k, v in body.items()})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return settings.public_view()["env"]


@app.post("/api/settings/youtube-client")
async def upload_youtube_client(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read(64_001)
    if len(raw) > 64_000:
        raise HTTPException(400, "file too large for an OAuth client JSON")
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(400, "not JSON") from exc
    if "installed" not in data:
        raise HTTPException(400, "expected a Desktop-app OAuth client (JSON with an 'installed' key)")
    settings.SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    (settings.SECRETS_DIR / "youtube_client_secret.json").write_bytes(raw)
    return {"ok": True}


@app.get("/api/usage")
def llm_usage() -> dict[str, Any]:
    from llm import usage

    return usage.summary()


@app.post("/api/settings/test-notify")
def test_notify() -> dict[str, Any]:
    from common import notify

    if not any(notify.configured().values()):
        raise HTTPException(400, "add a Telegram bot token + chat id, or a Discord webhook URL, and save first")
    return {
        "results": notify.send("video-factory: test message", ["Notifications are working."], {"UI": notify.UI_URL})
    }


@app.post("/api/settings/test-platform")
def test_platform(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    platform = body.get("platform")
    if platform not in ("youtube", "instagram", "tiktok"):
        raise HTTPException(400, "platform must be youtube, instagram or tiktok")
    code = f"from publisher.official_apis import test_connection; print(test_connection({platform!r}))"
    return jobs.submit("login", f"test {platform} API connection", ["-c", code]).public()


@app.post("/api/settings/test-llm")
def test_llm() -> dict[str, Any]:
    return jobs.submit("llm", "test language model", ["-m", "llm.cli", "ping"]).public()


@app.post("/api/settings/gemini-models")
def gemini_models() -> dict[str, Any]:
    return jobs.submit("llm", "list Gemini models", ["-m", "llm.cli", "models"]).public()


@app.post("/api/settings/models/{provider}")
def provider_models(provider: str) -> dict[str, Any]:
    """Models the saved key can use (OpenRouter: free models only). Results land in the job log."""
    if provider not in ("gemini", "groq", "openrouter"):
        raise HTTPException(400, "provider must be gemini, groq or openrouter")
    label = {"gemini": "Gemini", "groq": "Groq", "openrouter": "OpenRouter free"}[provider]
    return jobs.submit("llm", f"list {label} models", ["-m", "llm.cli", "models", "--provider", provider]).public()


@app.post("/api/settings/login")
def cookie_login(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    platform = body.get("platform")
    if platform not in ("youtube", "instagram", "tiktok"):
        raise HTTPException(400)
    account = _slug_ok(str(body.get("account") or "main"))
    return jobs.submit(
        "login", f"{platform} login ({account})", ["publisher/publish.py", "login", platform, "--account", account]
    ).public()


@app.post("/api/settings/check")
def cookie_check(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    platform = body.get("platform")
    if platform not in ("youtube", "instagram", "tiktok"):
        raise HTTPException(400)
    account = _slug_ok(str(body.get("account") or "main"))
    return jobs.submit(
        "login",
        f"{platform} cookie check ({account})",
        ["publisher/publish.py", "check", platform, "--account", account],
    ).public()


@app.post("/api/settings/youtube-connect")
def youtube_connect() -> dict[str, Any]:
    code = "from publisher.official_apis import youtube_connect; print(youtube_connect())"
    return jobs.submit("login", "connect YouTube Data API", ["-c", code]).public()


@app.post("/api/health")
def health() -> dict[str, Any]:
    return jobs.submit("doctor", "system health (doctor.py)", ["scripts/doctor.py"]).public()


@app.post("/api/smoke")
def smoke() -> dict[str, Any]:
    return jobs.submit("smoke", "smoke test (5 s render)", ["scripts/smoke_test.py"]).public()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to reach it from your phone on the same Wi-Fi")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args()
    url = f"http://127.0.0.1:{a.port}/"
    if a.host != "127.0.0.1":
        import socket

        LAN["enabled"] = True
        url = f"http://127.0.0.1:{a.port}/?t={TOKEN}"
        lan = socket.gethostbyname(socket.gethostname())
        print(f"WARNING: listening on {a.host}. Anyone on this network who has the link below can use the UI.")
        print(f"Phone link: http://{lan}:{a.port}/?t={TOKEN}")
    print(f"video-factory UI: {url}")
    if not a.no_browser:
        webbrowser.open(url)
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
