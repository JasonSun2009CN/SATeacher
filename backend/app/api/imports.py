"""Staged import pipeline endpoints (detect -> convert -> review -> commit).

The conversion itself is deterministic and fast (0 token), so the job is run
synchronously on ``POST /api/imports`` and the response already carries the
per-page report. Committing is a separate, explicit request so the UI can show
a review screen when a conversion looked ambiguous.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app import imports as imports_service
from app.repos import imports as jobs_repo

router = APIRouter(prefix="/api/imports", tags=["imports"])

_JOB_FIELDS = (
    "id",
    "filename",
    "status",
    "stage",
    "kind",
    "import_source",
    "pages_total",
    "pages_done",
    "question_count",
    "used_ai",
    "document_id",
    "error",
    "created_at",
)


def _fail(message: str, status: int = 422) -> None:
    raise HTTPException(status_code=status, detail=message)


def _payload(job: dict) -> dict:
    """Public view of a job: stable fields + derived ``needs_review``."""
    pages = job["pages"]
    needs_review = job["status"] == "review" and (
        bool(job["warnings"])
        or any(page.get("status") not in ("text", "ocr_ok") for page in pages)
    )
    out = {name: job[name] for name in _JOB_FIELDS}
    out["pages"] = pages
    out["warnings"] = job["warnings"]
    out["needs_review"] = needs_review
    return out


@router.post("", status_code=202)
async def create_import(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    filename = Path(file.filename or "upload").name
    try:
        imports_service.validate_upload(filename, data)
    except imports_service.ImportProblem as exc:
        _fail(str(exc), exc.status)
        raise                                          # pragma: no cover

    job_id = jobs_repo.create(filename)
    try:
        result = imports_service.convert_upload(filename, data)
    except imports_service.ImportProblem as exc:
        jobs_repo.update(job_id, status="failed", stage="convert", error=str(exc))
        return _payload(jobs_repo.get(job_id))

    staged = imports_service._stage(filename, data)
    try:
        result = imports_service.convert_upload(filename, data)
    except imports_service.ImportProblem as exc:
        jobs_repo.update(job_id, status="failed", stage="convert", error=str(exc))
        return _payload(jobs_repo.get(job_id))

    imports_service.save_result(job_id, result, original_pdf=staged)
    pages = imports_service.pages_to_json(result.pages)
    jobs_repo.update(
        job_id,
        status="review",
        stage="validate",
        kind=result.kind,
        import_source=result.import_source,
        pages_total=len(pages),
        pages_done=len(pages),
        question_count=result.question_count,
        used_ai=result.used_ai,
        pages_json=json.dumps(pages),
        warnings_json=json.dumps(result.warnings),
    )
    return _payload(jobs_repo.get(job_id))


@router.get("/{job_id}")
def get_import(job_id: str) -> dict:
    job = jobs_repo.get(job_id)
    if job is None:
        _fail("import job not found", 404)
        raise                                          # pragma: no cover
    return _payload(job)


@router.post("/{job_id}/commit")
def commit_import(job_id: str) -> dict:
    job = jobs_repo.get(job_id)
    if job is None:
        _fail("import job not found", 404)
        raise                                          # pragma: no cover
    if job["status"] == "done":
        return _payload(job)                           # idempotent
    if job["status"] != "review":
        _fail(f"job is not ready to commit (status: {job['status']})", 409)
        raise                                          # pragma: no cover

    result = imports_service.load_result(job_id)
    if result is None:
        _fail("the staged conversion result is missing — import the file again", 409)
        raise                                          # pragma: no cover

    try:
        doc_id = imports_service.commit(result)
    except imports_service.ImportProblem as exc:
        _fail(str(exc), exc.status)
        raise                                          # pragma: no cover

    jobs_repo.update(job_id, status="done", stage="commit", document_id=doc_id)
    imports_service.clear_result(job_id)
    return _payload(jobs_repo.get(job_id))


@router.post("/{job_id}/cancel")
def cancel_import(job_id: str) -> dict:
    job = jobs_repo.get(job_id)
    if job is None:
        _fail("import job not found", 404)
        raise                                          # pragma: no cover
    if job["status"] == "done":
        _fail("this import has already been committed", 409)
        raise                                          # pragma: no cover
    jobs_repo.update(job_id, status="cancelled", error=None)
    imports_service.clear_result(job_id)
    return _payload(jobs_repo.get(job_id))


@router.post("/{job_id}/ai-fallback")
def ai_fallback(job_id: str) -> dict:
    job = jobs_repo.get(job_id)
    if job is None:
        _fail("import job not found", 404)
        raise                                          # pragma: no cover
    try:
        imports_service.run_ai_fallback(job_id)
    except imports_service.ImportProblem as exc:
        _fail(str(exc), exc.status)
        raise                                          # pragma: no cover
    except Exception as exc:  # pragma: no cover - unexpected errors
        _fail(f"AI fallback failed: {exc}", 500)
        raise

    # Reload and return updated job.
    return _payload(jobs_repo.get(job_id))


@router.delete("/{job_id}")
def delete_import(job_id: str) -> dict:
    if not jobs_repo.delete(job_id):
        _fail("import job not found", 404)
        raise                                          # pragma: no cover
    imports_service.clear_result(job_id)
    return {"deleted": job_id}