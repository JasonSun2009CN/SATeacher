"""Staged import pipeline (/api/imports) — deterministic, 0 token, async."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pymupdf
import pytest

from tests.conftest import MINI_SATMD

TERMINAL = ("review", "done", "failed", "cancelled")


def _post(client, filename: str, content: bytes | str):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return client.post(
        "/api/imports",
        files={"file": (filename, content, "application/octet-stream")},
    )


def _wait(client, job_id: str, timeout: float = 30.0) -> dict:
    """Poll the job until the background conversion settles."""
    deadline = time.time() + timeout
    while True:
        job = client.get(f"/api/imports/{job_id}").json()
        if job.get("status") in TERMINAL:
            return job
        assert time.time() < deadline, f"job never settled: {job}"
        time.sleep(0.01)


def _create(client, filename: str, content: bytes | str) -> dict:
    """POST an upload and wait for the async conversion to finish."""
    resp = _post(client, filename, content)
    if resp.status_code != 202:
        return resp                            # validation failures (400/415/413)
    return _wait(client, resp.json()["id"])


def test_create_import_starts_async(client) -> None:
    """POST returns 202 immediately; the conversion runs in the background."""
    resp = _post(client, "mini.sat.md", MINI_SATMD)
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "converting"       # snapshot taken before the thread ran
    assert job["stage"] == "convert"
    assert job["kind"] == "satmd"
    assert job["pages"] == []                  # per-page report arrives via polling

    settled = _wait(client, job["id"])
    assert settled["status"] == "review"
    assert settled["question_count"] == 2
    assert settled["pages_done"] == settled["pages_total"] == 1


def test_import_satmd_job_requires_no_review(client) -> None:
    job = _create(client, "mini.sat.md", MINI_SATMD)
    assert job["kind"] == "satmd"
    assert job["import_source"] == "sat.md"
    assert job["status"] == "review"
    assert job["question_count"] == 2
    assert job["pages_total"] == 1
    assert job["used_ai"] is False
    assert job["needs_review"] is False          # clean text import
    assert job["pages"][0]["status"] == "text"


def test_commit_creates_a_document(client) -> None:
    job = _create(client, "mini.sat.md", MINI_SATMD)
    resp = client.post(f"/api/imports/{job['id']}/commit")
    assert resp.status_code == 200, resp.text
    done = resp.json()
    assert done["status"] == "done"
    assert done["document_id"]

    doc = client.get(f"/api/documents/{done['document_id']}").json()
    assert doc["title"] == "Mini Bank"
    assert doc["question_count"] == 2


def test_commit_is_idempotent(client) -> None:
    job = _create(client, "mini.sat.md", MINI_SATMD)
    first = client.post(f"/api/imports/{job['id']}/commit").json()
    second = client.post(f"/api/imports/{job['id']}/commit").json()
    assert first["document_id"] == second["document_id"]


def test_import_pdf_job(client, sat_pdf: Path) -> None:
    job = _create(client, "sat-sample.pdf", sat_pdf.read_bytes())
    assert job["kind"] == "pdf"
    assert job["import_source"] == "pdf"
    assert job["question_count"] == 5
    assert job["pages"] and all(p["status"] in ("text", "ocr_ok") for p in job["pages"])


def test_import_docx_job(client, sat_docx: Path) -> None:
    job = _create(client, "sat-sample.docx", sat_docx.read_bytes())
    assert job["kind"] == "docx"
    assert job["import_source"] == "docx"
    assert job["question_count"] == 5


def test_cancel_job(client) -> None:
    job = _create(client, "mini.sat.md", MINI_SATMD)
    resp = client.post(f"/api/imports/{job['id']}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    # a cancelled job can no longer be committed
    assert client.post(f"/api/imports/{job['id']}/commit").status_code == 409


def test_delete_job(client) -> None:
    job = _create(client, "mini.sat.md", MINI_SATMD)
    assert client.delete(f"/api/imports/{job['id']}").status_code == 200
    assert client.get(f"/api/imports/{job['id']}").status_code == 404


def test_unsupported_type_is_rejected(client) -> None:
    resp = _post(client, "notes.txt", "hello")
    assert resp.status_code == 415


def test_empty_file_is_rejected(client) -> None:
    resp = _post(client, "empty.sat.md", b"")
    assert resp.status_code == 400


def test_empty_pdf_reports_a_failed_job(client) -> None:
    doc = pymupdf.open()
    doc.new_page()
    empty = doc.tobytes()
    doc.close()

    resp = _post(client, "blank.pdf", empty)
    assert resp.status_code == 202, resp.text
    job = _wait(client, resp.json()["id"])
    assert job["status"] == "failed"
    assert job["stage"] == "convert"
    assert "no text could be extracted" in (job["error"] or "")


def test_cancel_during_conversion_stays_cancelled(client, monkeypatch) -> None:
    """Cancelling a running job stops it before the result is staged."""
    import app.imports as imports_service

    started = threading.Event()
    release = threading.Event()
    saved = threading.Event()
    real_convert = imports_service.convert_upload
    real_save = imports_service.save_result
    real_start = imports_service.start_job
    threads: list[threading.Thread] = []

    def slow_convert(filename, data, *, progress=None):
        started.set()
        assert release.wait(10), "test never released the conversion"
        if progress is not None:
            progress(1, 2)                     # raises JobCancelled once cancelled
        return real_convert(filename, data, progress=progress)

    def tracking_start(job_id, filename, data):
        thread = real_start(job_id, filename, data)
        threads.append(thread)
        return thread

    def saving(*args, **kwargs):
        saved.set()
        return real_save(*args, **kwargs)

    monkeypatch.setattr(imports_service, "convert_upload", slow_convert)
    monkeypatch.setattr(imports_service, "save_result", saving)
    monkeypatch.setattr(imports_service, "start_job", tracking_start)

    resp = _post(client, "mini.sat.md", MINI_SATMD)
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "converting"
    assert started.wait(5), "background conversion never started"

    assert client.post(f"/api/imports/{job['id']}/cancel").status_code == 200
    release.set()
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive(), "cancelled job kept converting"

    assert not saved.is_set(), "cancelled job staged a result anyway"
    assert client.get(f"/api/imports/{job['id']}").json()["status"] == "cancelled"


def test_convert_upload_reports_pdf_page_progress(sat_pdf: Path) -> None:
    """The PDF converter reports monotonic per-page progress."""
    import app.imports as imports_service

    calls: list[tuple[int, int]] = []
    imports_service.convert_upload(
        "sat-sample.pdf", sat_pdf.read_bytes(), progress=lambda d, t: calls.append((d, t))
    )
    assert calls, "no progress was reported"
    total = calls[0][1]
    assert total > 0
    assert calls[0] == (0, total)
    assert calls[-1] == (total, total)
    assert [d for d, _ in calls] == sorted(d for d, _ in calls)
    assert all(t == total for _, t in calls)


def test_ai_fallback_no_problematic_pages(client) -> None:
    """AI fallback on a sat.md import (no OCR pages) returns job unchanged."""
    job = _create(client, "mini.sat.md", MINI_SATMD)
    resp = client.post(f"/api/imports/{job['id']}/ai-fallback")
    # No original PDF stored for sat.md, and no problematic pages -> 409
    assert resp.status_code == 409


def test_get_unknown_job_is_404(client) -> None:
    assert client.get("/api/imports/j_does_not_exist").status_code == 404


@pytest.mark.skipif(
    not __import__("app.convert.ocr.tesseract", fromlist=["available"]).available(),
    reason="tesseract binary not installed",
)
def test_scanned_pdf_job_reports_ocr_pages(client, sat_scanned: Path) -> None:
    job = _create(client, "sat-scanned.pdf", sat_scanned.read_bytes())
    assert job["question_count"] >= 3
    assert any(p["status"] in ("ocr_ok", "low_confidence") for p in job["pages"])
    assert any(p["source"] == "tesseract" for p in job["pages"])