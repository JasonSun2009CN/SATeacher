"""Staged import pipeline (/api/imports) — deterministic, 0 token."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from tests.conftest import MINI_SATMD


def _create(client, filename: str, content: bytes | str) -> dict:
    if isinstance(content, str):
        content = content.encode("utf-8")
    resp = client.post(
        "/api/imports",
        files={"file": (filename, content, "application/octet-stream")},
    )
    return resp


def test_import_satmd_job_requires_no_review(client) -> None:
    resp = _create(client, "mini.sat.md", MINI_SATMD)
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["kind"] == "satmd"
    assert job["import_source"] == "sat.md"
    assert job["status"] == "review"
    assert job["question_count"] == 2
    assert job["pages_total"] == 1
    assert job["used_ai"] is False
    assert job["needs_review"] is False          # clean text import
    assert job["pages"][0]["status"] == "text"


def test_commit_creates_a_document(client) -> None:
    job = _create(client, "mini.sat.md", MINI_SATMD).json()
    resp = client.post(f"/api/imports/{job['id']}/commit")
    assert resp.status_code == 200, resp.text
    done = resp.json()
    assert done["status"] == "done"
    assert done["document_id"]

    doc = client.get(f"/api/documents/{done['document_id']}").json()
    assert doc["title"] == "Mini Bank"
    assert doc["question_count"] == 2


def test_commit_is_idempotent(client) -> None:
    job = _create(client, "mini.sat.md", MINI_SATMD).json()
    first = client.post(f"/api/imports/{job['id']}/commit").json()
    second = client.post(f"/api/imports/{job['id']}/commit").json()
    assert first["document_id"] == second["document_id"]


def test_import_pdf_job(client, sat_pdf: Path) -> None:
    job = _create(client, "sat-sample.pdf", sat_pdf.read_bytes()).json()
    assert job["kind"] == "pdf"
    assert job["import_source"] == "pdf"
    assert job["question_count"] == 5
    assert job["pages"] and all(p["status"] in ("text", "ocr_ok") for p in job["pages"])


def test_import_docx_job(client, sat_docx: Path) -> None:
    job = _create(client, "sat-sample.docx", sat_docx.read_bytes()).json()
    assert job["kind"] == "docx"
    assert job["import_source"] == "docx"
    assert job["question_count"] == 5


def test_cancel_job(client) -> None:
    job = _create(client, "mini.sat.md", MINI_SATMD).json()
    resp = client.post(f"/api/imports/{job['id']}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
    # a cancelled job can no longer be committed
    assert client.post(f"/api/imports/{job['id']}/commit").status_code == 409


def test_delete_job(client) -> None:
    job = _create(client, "mini.sat.md", MINI_SATMD).json()
    assert client.delete(f"/api/imports/{job['id']}").status_code == 200
    assert client.get(f"/api/imports/{job['id']}").status_code == 404


def test_unsupported_type_is_rejected(client) -> None:
    resp = _create(client, "notes.txt", "hello")
    assert resp.status_code == 415


def test_empty_file_is_rejected(client) -> None:
    resp = _create(client, "empty.sat.md", b"")
    assert resp.status_code == 400


def test_empty_pdf_reports_a_failed_job(client) -> None:
    doc = pymupdf.open()
    doc.new_page()
    empty = doc.tobytes()
    doc.close()

    resp = _create(client, "blank.pdf", empty)
    assert resp.status_code == 202, resp.text
    job = resp.json()
    assert job["status"] == "failed"
    assert job["stage"] == "convert"
    assert "no text could be extracted" in (job["error"] or "")


def test_ai_fallback_no_problematic_pages(client) -> None:
    """AI fallback on a sat.md import (no OCR pages) returns job unchanged."""
    job = _create(client, "mini.sat.md", MINI_SATMD).json()
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
    job = _create(client, "sat-scanned.pdf", sat_scanned.read_bytes()).json()
    assert job["question_count"] >= 3
    assert any(p["status"] in ("ocr_ok", "low_confidence") for p in job["pages"])
    assert any(p["source"] == "tesseract" for p in job["pages"])