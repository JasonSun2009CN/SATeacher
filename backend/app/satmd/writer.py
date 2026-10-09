"""SAT-MD writer: `ParsedDoc` -> text. Inverse of :func:`app.satmd.parser.parse`.

Round-trip holds at the parse level: ``parse(render(doc))`` reproduces every
field the parser keeps — front-matter keys (order included), preamble, and each
question's attributes, material/stem, four options, meta lines and unknown
``!`` keys. Byte-identical output is *not* guaranteed (quotes are stripped from
front-matter values), but nothing is lost.

Why this exists: normalization rewrites question text, so the file has to be
written back. Re-rendering with the PDF pipeline's ``_render_question`` (which
targets ``BuiltQuestion``: dict options, ``q.source``) corrupts parser output
(``options`` is a list there, and ids would be renumbered).
"""

from __future__ import annotations

from app.satmd.parser import ParsedDoc, Question

FORMAT_KEY = "satmd"


def render_question(q: Question) -> list[str]:
    """One ``:::q`` block (without the trailing blank line)."""
    attrs = [f"#{q.ext_id}", f"sec={q.sec}"]
    if q.no is not None:
        attrs.append(f"no={q.no}")
    if q.type is not None:
        attrs.append(f"type={q.type}")
    if q.difficulty is not None:
        attrs.append(f"difficulty={q.difficulty}")

    out = [f":::q {{{' '.join(attrs)}}}"]
    if q.material:
        out += ["@material", q.material, ""]
    out += ["@stem", q.stem, ""]
    out.append("")
    for opt in q.options:                       # already "A. text"
        out.append(f"- {opt}")
    if q.answer:
        out.append(f"! answer: {q.answer}")
    if q.explain:
        out.append(f"! explain: {q.explain}")
    if q.source_ref:
        out.append(f"! source: {q.source_ref}")
    for key, value in q.meta.items():           # unknown ! keys, preserved verbatim
        out.append(f"! {key}: {value}")
    out.append(":::")
    return out


def render(doc: ParsedDoc) -> str:
    """Render a parsed document back to SAT-MD text."""
    lines = ["---"]
    for key, value in doc.meta.items():
        lines.append(f"{key}: {value}")
    lines.append("---")

    body: list[str] = []
    if doc.preamble:
        body += [doc.preamble, ""]
    for q in doc.questions:
        body += render_question(q)
        body.append("")
    while body and body[-1] == "":
        body.pop()

    return "\n".join(lines + body) + "\n"


def render_block(q: Question) -> str:
    """Render a single question as its own document (used for validation)."""
    return render(ParsedDoc(meta={FORMAT_KEY: "1"}, questions=[q]))
