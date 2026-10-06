"""Batch-A exports: questions + answers + explanations as PDF / DOCX."""

from __future__ import annotations

from io import BytesIO

import fitz
from docx import Document
from tests.conftest import MINI_SATMD, upload

EXPLAIN = 'Because x + 2 = 5, so x = 3; watch the "quotes", too.'


def _doc_with_explain(client) -> int:
    resp = upload(client, "mini.sat.md", MINI_SATMD)
    assert resp.status_code == 200, resp.text
    doc_id = resp.json()["id"]
    questions = client.get(f"/api/documents/{doc_id}/questions").json()
    client.put(
        f"/api/documents/{doc_id}/answers", json={"answers": {"Q001": "B", "Q002": "D"}}
    )
    ok = client.put(
        f"/api/documents/{doc_id}/questions/{questions[1]['id']}/explain",
        json={"content": EXPLAIN},
    )
    assert ok.status_code == 200, ok.text
    return doc_id


def test_export_pdf(client) -> None:
    doc_id = _doc_with_explain(client)
    resp = client.get(f"/api/documents/{doc_id}/export/pdf")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/pdf")
    assert ".pdf" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF-")
    assert len(resp.content) > 1000


def test_export_pdf_content(client) -> None:
    doc_id = _doc_with_explain(client)
    resp = client.get(f"/api/documents/{doc_id}/export/pdf")
    pdf = fitz.open(stream=resp.content, filetype="pdf")
    text = "\n".join(page.get_text() for page in pdf)
    assert "Mini Bank" in text
    assert "A. one" in text
    assert "1. B" in text and "2. D" in text
    assert "Because x + 2 = 5" in text


def test_export_docx(client) -> None:
    doc_id = _doc_with_explain(client)
    resp = client.get(f"/api/documents/{doc_id}/export/docx")
    assert resp.status_code == 200, resp.text
    assert "wordprocessingml" in resp.headers["content-type"]
    assert ".docx" in resp.headers["content-disposition"]
    assert resp.content[:2] == b"PK"          # zip container


def test_export_docx_content(client) -> None:
    doc_id = _doc_with_explain(client)
    resp = client.get(f"/api/documents/{doc_id}/export/docx")
    document = Document(BytesIO(resp.content))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "Mini Bank" in text
    assert "A. one" in text
    assert "1. B" in text and "2. D" in text
    assert EXPLAIN in text


def test_export_validation(client) -> None:
    doc_id = _doc_with_explain(client)
    # the old md/csv/json formats are gone
    assert client.get(f"/api/documents/{doc_id}/export/json").status_code == 400
    assert client.get(f"/api/documents/{doc_id}/export/csv").status_code == 400
    assert client.get(f"/api/documents/{doc_id}/export/md").status_code == 400
    assert client.get("/api/documents/999999/export/pdf").status_code == 404
    assert client.get("/api/documents/999999/export/docx").status_code == 404


def test_math_bridge_renders_svg() -> None:
    import pytest

    from app.export import math_render

    if not math_render.available():
        pytest.skip("MathJax bridge not installed")
    svg = math_render.render([("x^2+1", False)])[("x^2+1", False)]
    assert svg and "<svg" in svg


def test_export_with_math_does_not_crash(client) -> None:
    math_md = MINI_SATMD.replace(
        "Which choice best completes the sentence?",
        r"What is the value of $x^2 + \frac{1}{2}$?",
    )
    resp = upload(client, "math.sat.md", math_md)
    assert resp.status_code == 200, resp.text
    doc_id = resp.json()["id"]
    for fmt in ("pdf", "docx"):
        export = client.get(f"/api/documents/{doc_id}/export/{fmt}")
        assert export.status_code == 200, export.text