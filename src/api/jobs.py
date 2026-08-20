"""Minimal in-process async job runner.

Long-running work (Phase-1 scan ~108s, later Phase-2 embed ~77s) can't block an
HTTP response, so endpoints submit a callable here, get a job id back immediately,
and the client polls for status/result.

Deliberately tiny and swappable: a `JobStore` holds jobs in memory and runs them
on a `ThreadPoolExecutor`. Phase-1 scanning is pure-Python CPU work with no torch,
so a worker thread is safe and keeps the event loop responsive. When Step 2 adds
the heavier torch embedding, this is the seam to swap for a real out-of-process
queue (Celery/RQ/arq) without touching the endpoints.
"""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

JobStatus = Literal["pending", "running", "done", "failed"]


@dataclass
class Job:
    id: str
    kind: str
    status: JobStatus = "pending"
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class JobStore:
    """Thread-safe registry of jobs plus the executor that runs them."""

    def __init__(self, max_workers: int = 2) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, kind: str, fn: Callable[[], dict[str, Any]]) -> Job:
        """Register a job and run `fn` in the background. `fn` returns the result dict."""
        job = Job(id=str(uuid.uuid4()), kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        self._executor.submit(self._run, job.id, fn)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job_id: str, fn: Callable[[], dict[str, Any]]) -> None:
        self._set(job_id, status="running")
        try:
            result = fn()
            self._set(job_id, status="done", result=result)
        except Exception as exc:  # noqa: BLE001 — surface any failure to the client
            self._set(job_id, status="failed", error=f"{type(exc).__name__}: {exc}")

    def _set(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = time.time()
