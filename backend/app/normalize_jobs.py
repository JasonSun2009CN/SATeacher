"""In-process registry for document-wide normalization runs.

A whole-document run is one LLM call per question, so it takes minutes; the
endpoint only *starts* it and the browser polls ``GET /api/documents/{id}/normalize``
for progress. The registry is deliberately in-memory: a run is an explicit,
restartable user action, so it needs no schema change and no persistence —
losing it on restart just means the user clicks the button again.

Single-flight per document: while a run is going, ``start()`` hands back the
running job instead of launching a second one (double-click safe).
"""

from __future__ import annotations

import threading
from typing import Any

from app.llm import normalize as normalize_mod

_lock = threading.Lock()
_jobs: dict[int, dict[str, Any]] = {}


def _blank(doc_id: int) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "status": "running",       # running | done | failed
        "total": 0,
        "done": 0,
        "applied": 0,
        "unchanged": 0,
        "kept": 0,
        "errors": [],
        "error": None,
    }


def start(doc_id: int) -> dict[str, Any]:
    """Start (or re-attach to) the run for ``doc_id``; returns the job snapshot."""
    with _lock:
        job = _jobs.get(doc_id)
        if job is not None and job["status"] == "running":
            return dict(job)
        job = _blank(doc_id)
        _jobs[doc_id] = job
    threading.Thread(target=_run, args=(doc_id, job), daemon=True).start()
    return dict(job)


def get(doc_id: int) -> dict[str, Any] | None:
    """Snapshot of the latest run for ``doc_id`` (None if never started)."""
    with _lock:
        job = _jobs.get(doc_id)
        return dict(job) if job is not None else None


def _run(doc_id: int, job: dict[str, Any]) -> None:
    def progress(done: int, total: int) -> None:
        with _lock:
            job["done"] = done
            job["total"] = total

    try:
        summary = normalize_mod.normalize_document(doc_id, progress=progress)
    except Exception as exc:                       # noqa: BLE001 — surfaced as job.error
        with _lock:
            job["status"] = "failed"
            job["error"] = str(exc)
        return

    with _lock:
        job.update(summary)
        job["status"] = "done"
