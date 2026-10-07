"""Document export (PDF / DOCX) built from the questions + vocabulary.

All content comes from the local database — exports are deterministic and
0 token. Math is rendered server-side when the optional Node bridge is present
(see ``math_render``), and degrades to plain text otherwise.
"""

from __future__ import annotations

from app.export.model import ExportDoc, ExportQuestion, build_export, section_label

__all__ = [
    "ExportDoc",
    "ExportQuestion",
    "build_export",
    "section_label",
    "render_pdf_bytes",
    "render_docx_bytes",
]


def render_pdf_bytes(doc: ExportDoc) -> bytes:
    from app.export.pdf import render_pdf

    return render_pdf(doc)


def render_docx_bytes(doc: ExportDoc) -> bytes:
    from app.export.docx import render_docx

    return render_docx(doc)