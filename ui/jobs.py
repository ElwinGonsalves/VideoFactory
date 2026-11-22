"""Background jobs for the UI: each job is a subprocess with a log file the browser can tail.

Heavy jobs (render, analyze, approve, smoke) share one worker so the GPU, RAM and Chrome are
never oversubscribed; light jobs (doctor, publish, llm, login) run immediately.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from common import ROOT

LOG_DIR = ROOT / "ui" / "logs"
HEAVY = {"render", "analyze", "approve", "smoke"}
PY = sys.executable


@dataclass
class Job:
    id: str
    kind: str
    title: str
    cmd: list[str]
    status: str = "queued"  # queued | running | done | failed | cancelled
    created: float = field(default_factory=time.time)
    started: float | None = None
    ended: float | None = None
    returncode: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def log_path(self) -> Path:
        return LOG_DIR / f"{self.id}.log"

    def public(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("cmd")
        return d


class JobManager:
    def __init__(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self.procs: dict[str, subprocess.Popen[bytes]] = {}
        self.heavy_q: queue.Queue[Job] = queue.Queue()
        self.lock = threading.Lock()
        threading.Thread(target=self._heavy_worker, daemon=True).start()

    def submit(self, kind: str, title: str, args: list[str], meta: dict[str, Any] | None = None) -> Job:
        job = Job(uuid.uuid4().hex[:10], kind, title, [PY, *args], meta=meta or {})
        with self.lock:
            self.jobs[job.id] = job
        job.log_path.write_text(f"$ {kind}: {title}\n", encoding="utf-8")
        if kind in HEAVY:
            self.heavy_q.put(job)
        else:
            threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def _heavy_worker(self) -> None:
        while True:
            job = self.heavy_q.get()
            if job.status == "queued":
                self._run(job)

    def _run(self, job: Job) -> None:
        job.status, job.started = "running", time.time()
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with job.log_path.open("ab") as log:
            try:
                proc = subprocess.Popen(
                    job.cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env, creationflags=flags
                )
            except OSError as exc:
                log.write(f"\nfailed to start: {exc}\n".encode())
                job.status, job.ended, job.returncode = "failed", time.time(), -1
                return
            self.procs[job.id] = proc
            code = proc.wait()
        self.procs.pop(job.id, None)
        job.returncode, job.ended = code, time.time()
        if job.status != "cancelled":
            job.status = "done" if code == 0 else "failed"
        with job.log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[exit {code}] {job.status}\n")

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job:
            return False
        job.status = "cancelled"
        proc = self.procs.get(job_id)
        if proc and proc.poll() is None:
            if os.name == "nt":  # kill the whole tree (Remotion spawns Chrome + FFmpeg)
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            else:
                proc.terminate()
        return True

    def list(self, limit: int = 30) -> list[dict[str, Any]]:
        jobs = sorted(self.jobs.values(), key=lambda j: j.created, reverse=True)[:limit]
        return [j.public() for j in jobs]

    def read_log(self, job_id: str, offset: int = 0) -> tuple[str, int]:
        job = self.jobs.get(job_id)
        if not job or not job.log_path.exists():
            return "", offset
        with job.log_path.open("rb") as fh:
            fh.seek(offset)
            data = fh.read(256_000)
        return data.decode("utf-8", "replace"), offset + len(data)
