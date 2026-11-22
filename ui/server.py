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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402
import yaml  # noqa: E402
from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse  # noqa: E402

from common import OUTPUT, PROJECTS, ROOT, read_json, settings, write_json  # noqa: E402
from llm.tasks import VISUAL_TYPES  # noqa: E402
from pipeline.router import ROUTES  # noqa: E402
from prompts.script_templates import REGISTRY  # noqa: E402
from ui.jobs import JobManager  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
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
    if path.startswith("/api/") or path.startswith("/files/"):
        supplied = request.headers.get("x-vf-token") or request.query_params.get("t")
        if not supplied or not secrets.compare_digest(supplied, TOKEN):
            return JSONResponse(error_body(401, "missing or wrong session token"), status_code=401)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


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
    if LAN["enabled"] and not secrets.compare_digest(t, TOKEN):
        return HTMLResponse(
            "<h3>video-factory: open the link printed in the console (it contains the access token).</h3>", 401
        )
    return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8").replace("__VF_TOKEN__", TOKEN))


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


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, bool]:
    return {"ok": jobs.cancel(job_id)}


# ------------------------------------------------------------------ Create
def _slug_ok(slug: str) -> str:
    if not slug or not all(c.isalnum() or c in "-_" for c in slug) or len(slug) > 60:
        raise HTTPException(400, "slug: letters, digits, - and _ only")
    return slug


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
                "rendered": (OUTPUT / f"{p.parent.name}.mp4").exists(),
                "needs_approval": bool(s.get("blueprint")) and s.get("approval") != "approved",
            }
        )
    return out


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
@app.post("/api/analyze")
def analyze(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    urls = [u.strip() for u in body.get("urls", []) if str(u).strip()]
    if not urls:
        raise HTTPException(400, "add at least one link or file path")
    for u in urls:
        if not (u.startswith(("https://", "http://")) or Path(u).exists()):
            raise HTTPException(400, f"not a URL or existing file: {u}")
    style = str(body.get("style") or "my_style")
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


@app.get("/api/ideas")
def ideas_runs() -> list[dict[str, Any]]:
    out = []
    work = ROOT / "analyzer" / "work"
    for run in sorted(work.glob("*/approval.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        d = run.parent
        approval = read_json(run)
        bp_path = ROOT / approval["blueprint"]
        analyses = read_json(d / "analysis.json") if (d / "analysis.json").exists() else []
        sheets = [s for a in analyses for s in a.get("contact_sheets", [])]
        out.append(
            {
                "run": d.name,
                "status": approval.get("status"),
                "approved": approval.get("approved", []),
                "projects": approval.get("projects", []),
                "blueprint": read_json(bp_path) if bp_path.exists() else {},
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
@app.get("/api/library")
def library() -> list[dict[str, Any]]:
    out = []
    for meta_path in sorted(OUTPUT.glob("*.meta.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        slug = meta_path.name.removesuffix(".meta.json")
        meta = read_json(meta_path)
        qa_dir = PROJECTS / slug / "qa"
        report = read_json(qa_dir / "report.json") if (qa_dir / "report.json").exists() else None
        frames = [f for f in ("cover", "hook", "early", "mid", "outro") if (qa_dir / f"{f}.png").exists()]
        out.append(
            {
                "slug": slug,
                "meta": meta,
                "video": rel(OUTPUT / f"{slug}.mp4") if (OUTPUT / f"{slug}.mp4").exists() else None,
                "thumbnail": rel(OUTPUT / f"{slug}.thumb.jpg") if (OUTPUT / f"{slug}.thumb.jpg").exists() else None,
                "qa": report,
                "qa_frames": [
                    {
                        "name": f,
                        "src": rel(qa_dir / f"{f}.png"),
                        "overlay": rel(qa_dir / f"{f}.overlay.png") if (qa_dir / f"{f}.overlay.png").exists() else None,
                    }
                    for f in frames
                ],
                "mtime": meta_path.stat().st_mtime,
            }
        )
    return out


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
    meta_path = OUTPUT / f"{_slug_ok(slug)}.meta.json"
    if not meta_path.exists():
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
    args = ["publisher/publish.py", "upload", f"output/{_slug_ok(slug)}.meta.json", "--platform", platform]
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
    from contextlib import closing

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
    return {
        "defaults": sch["defaults"],
        "jobs": [
            {**j, "state": state.get(j["id"]), "uploads": ups.get(j["id"], [])} for j in _schedule_raw().get("jobs", [])
        ],
        "events": events,
        "caps": caps,
        "posts": post_log.recent(20),
        "daemon": bool(proc and proc.poll() is None),
    }


def _write_schedule(data: dict[str, Any]) -> None:
    SCHEDULE.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


@app.post("/api/schedule/jobs")
def add_schedule_job(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    data = _schedule_raw()
    data.setdefault("defaults", {})
    data.setdefault("jobs", [])
    jid = _slug_ok(str(body.get("id", "")))
    if any(j["id"] == jid for j in data["jobs"]):
        raise HTTPException(400, "a job with that id exists")
    job = {
        "id": jid,
        "enabled": bool(body.get("enabled", True)),
        "type": body.get("type", "generate_and_upload"),
        "script_or_prompt": body.get("script_or_prompt") or f"projects/{body.get('project', jid)}/script.json",
        "generate_at": body.get("generate_at") or None,
        "upload_at": body.get("upload_at") or None,
        "platforms": body.get("platforms") or ["youtube"],
    }
    if body.get("visibility"):
        job["visibility"] = body["visibility"]
    if job["type"] == "upload_only":
        job["meta"] = body.get("meta") or f"output/{body.get('project', jid)}.meta.json"
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
    allowed = {"llm", "defaults", "publish", "clipper"}
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
    raw = await file.read()
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


@app.post("/api/settings/test-llm")
def test_llm() -> dict[str, Any]:
    return jobs.submit("llm", "test language model", ["-m", "llm.cli", "ping"]).public()


@app.post("/api/settings/gemini-models")
def gemini_models() -> dict[str, Any]:
    return jobs.submit("llm", "list Gemini models", ["-m", "llm.cli", "models"]).public()


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
