"""PDF export via WeasyPrint (deterministic, 0 token)."""

from __future__ import annotations

import base64
import html
from pathlib import Path

from app.export import math_render
from app.export.model import ExportDoc, section_label

_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".svg": "image/svg+xml"}

_CSS = """
@page {
  size: A4;
  margin: 18mm 16mm 16mm 16mm;
  @bottom-center { content: counter(page); font-size: 9pt; color: #94a3b8; }
}
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
       font-size: 10.5pt; line-height: 1.5; color: #1e293b; }
h1 { font-size: 20pt; margin: 0 0 2mm 0; }
.meta { color: #64748b; font-size: 9pt; margin-bottom: 6mm; }
h2 { font-size: 13pt; margin: 8mm 0 3mm 0; padding-bottom: 1.5mm;
     border-bottom: 0.4mm solid #e2e8f0; color: #0f172a; }
.q { margin-bottom: 6mm; break-inside: avoid; }
.q-head { font-weight: 600; font-size: 10.5pt; color: #0f172a; margin-bottom: 1mm; }
.q-source { color: #94a3b8; font-weight: 400; font-size: 9pt; }
.material { margin: 1.5mm 0; padding: 2mm 3mm; background: #f8fafc;
            border-left: 0.8mm solid #cbd5e1; color: #334155; }
.material p { margin: 0 0 1.5mm 0; }
.material p:last-child { margin-bottom: 0; }
.stem { margin: 1.5mm 0; }
ol.options { margin: 1mm 0 0 0; padding-left: 7mm; }
ol.options li { margin: 0.5mm 0; }
img.q-img { display: block; max-width: 100%; margin: 2mm 0; }
img.math-inline, img.math-block { max-width: 100%; }
img.math-block { display: block; margin: 2mm 0; }
.math-fallback { font-family: "SFMono-Regular", Consolas, monospace;
                 background: #f1f5f9; padding: 0 1mm; border-radius: 1mm; }
.key { columns: 4; column-gap: 6mm; margin: 0; padding: 0; list-style: none; }
.key li { font-size: 10pt; margin-bottom: 1mm; }
.explain { margin-bottom: 4mm; break-inside: avoid; }
.exp-head { font-weight: 600; }
table { width: 100%; border-collapse: collapse; font-size: 9.5pt; }
th, td { border: 0.3mm solid #cbd5e1; padding: 1.5mm 2mm; text-align: left;
         vertical-align: top; }
th { background: #f1f5f9; }
.muted { color: #94a3b8; }
"""


def _data_uri(path: Path) -> str:
    mime = _MIME.get(path.suffix.lower(), "application/octet-stream")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _rich(text: str, svgs: dict) -> str:
    """HTML for a text/math string; math -> inline SVG image (or plain text)."""
    parts: list[str] = []
    for kind, value in math_render.split_math(text or ""):
        if kind == "text":
            parts.append(html.escape(value).replace("\n", "<br/>"))
            continue
        tex, display = value
        svg = svgs.get(value)
        if svg:
            b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
            cls = "math-display" if display else "math-inline"
            parts.append(f'<img class="{cls}" src="data:image/svg+xml;base64,{b64}"/>')
        else:
            parts.append(f'<code class="math-fallback">{html.escape(f"${tex}$")}</code>')
    return "".join(parts)


def _html(doc: ExportDoc, svgs: dict) -> str:
    out: list[str] = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<style>{_CSS}</style></head><body>",
        f"<h1>{html.escape(doc.title)}</h1>",
        f"<div class='meta'>{html.escape(doc.source_filename)} · "
        f"{len(doc.questions)} questions · {doc.answered} answered</div>",
        "<h2>Questions</h2>",
    ]
    for q in doc.questions:
        source = f" <span class='q-source'>{html.escape(q.source)}</span>" if q.source else ""
        out.append("<div class='q'>")
        out.append(
            f"<div class='q-head'>Question {q.no} · {section_label(q.sec)}{source}</div>"
        )
        if q.material:
            out.append(f"<div class='material'>{_rich(q.material, svgs)}</div>")
        out.append(f"<div class='stem'>{_rich(q.stem, svgs)}</div>")
        if q.options:
            out.append("<div class='options'>")
            for letter in "ABCD":
                if letter in q.options:
                    out.append(f"<div>{letter}. {_rich(q.options[letter], svgs)}</div>")
            out.append("</div>")
        for image in q.images:
            out.append(f"<img class='q-image' src='{_data_uri(image)}'/>")
        out.append("</div>")

    out.append("<h2>Answer Key</h2><div class='answers'>")
    key_bits = [
        f"<span class='key-item' style='display:inline-block;min-width:16mm'>"
        f"{q.no}. {html.escape(q.answer) if q.answer else '—'}</span>"
        for q in doc.questions
    ]
    out.append("".join(key_bits) or "<span class='muted'>No answers.</span>")
    out.append("</div>")

    out.append("<h2>Explanations</h2>")
    explained = [q for q in doc.questions if q.explain]
    if not explained:
        out.append("<p class='muted'>No explanations saved yet.</p>")
    for q in explained:
        out.append(
            f"<div class='ex'> <span class='ex-head'>Question {q.no}.</span> "
            f"{_rich(q.explain, svgs)}</div>"
        )

    if doc.vocab_rows:
        out.append("<h2>Vocabulary</h2><table><thead><tr>")
        for header in doc.vocab_headers:
            out.append(f"<th>{_rich(header, svgs)}</th>")
        out.append("</tr></thead><tbody>")
        for row in doc.vocab_rows:
            out.append("<tr>")
            for cell in row:
                out.append(f"<td>{_rich(cell, svgs)}</td>")
            out.append("</tr>")
        out.append("</tbody></table>")

    out.append("</body></html>")
    return "".join(out)


def _all_text(doc: ExportDoc) -> list[str]:
    texts = [doc.title, doc.source_filename, *doc.vocab_headers]
    for q in doc.questions:
        texts += [q.material or "", q.stem, q.explain or "", *q.options.values()]
    for row in doc.vocab_rows:
        texts.extend(row)
    return texts


def render_pdf(doc: ExportDoc) -> bytes:
    from weasyprint import HTML

    svgs = math_render.render(math_render.collect_math(_all_text(doc)))
    return HTML(string=_html(doc, svgs)).write_pdf()