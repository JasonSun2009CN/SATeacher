"""DOCX -> SAT-MD conversion (deterministic, 0 token).

Word documents are a flat stream of paragraphs and tables. We flatten them into
the same `Item` stream the PDF profile produces, then hand that stream to the
shared grouping / question-building / assembly pipeline (``app.convert.pdf``).
That keeps numbering, option detection, material/stem split, answer-key
backfill and rendering identical across input formats — no LLM, no tokens.

Security: a ``.docx`` is a ZIP container. Before python-docx ever opens it we
inspect the archive (entry count, uncompressed size, compression ratio, macro
parts) so a zip bomb or a macro-enabled file cannot reach the parser.
"""

from __future__ import annotations

import hashlib
import zipfile
from io import BytesIO
from pathlib import Path

import pymupdf
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.convert.model import BuiltQuestion, Item, PageReport
from app.convert.normalize import clean_text, match_section_heading
from app.convert.pdf import (
    ConvertError,
    ConvertedDoc,
    _assemble,
    _build_question,
    _detect_lang,
    _find_answer_key,
    _group_questions,
)

# ZIP safety limits (see RENOVATION_PLAN §12 risk 5).
MAX_ENTRIES = 5000
MAX_UNCOMPRESSED = 300 * 1024 * 1024          # 300 MB
MAX_RATIO = 200                               # uncompressed / compressed
RATIO_FLOOR = 5 * 1024 * 1024                 # ignore ratio for small files

# Synthetic geometry: the shared pipeline reads lines by vertical gap, so give
# every paragraph a large, constant gap (new questions start cleanly) and a
# small height. Values are arbitrary but stable across runs.
Y_STEP = 20.0
Y_HEIGHT = 8.0
SIZE = 12.0

# VML (legacy Word drawings) is not in python-docx's namespace map.
VML_IMAGEDATA = "{urn:schemas-microsoft-com:vml}imagedata"
R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _fail(message: str) -> None:
    raise ConvertError(message, fallback=False)


def _check_archive(data: bytes) -> None:
    """Reject anything that is not a small, macro-free, sane Office ZIP."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            infos = zf.infolist()
    except zipfile.BadZipFile:
        _fail("the file is not a valid .docx (Word) document")

    if len(infos) > MAX_ENTRIES:
        _fail("the .docx archive has too many entries to be a Word document")
    total = sum(info.file_size for info in infos)
    if total > MAX_UNCOMPRESSED:
        _fail("the .docx expands to more than 300 MB — refusing to process it")
    compressed = sum(max(info.compress_size, 1) for info in infos)
    if total > RATIO_FLOOR and total / compressed > MAX_RATIO:
        _fail("the .docx looks like a compressed archive bomb — refusing it")
    if any(info.filename.lower().endswith("vbaproject.bin") for info in infos):
        _fail("macro-enabled documents are not supported; save as .docx without macros")


def _to_png(blob: bytes) -> bytes | None:
    """Normalize an embedded image (png/jpeg/...) to PNG via PyMuPDF."""
    try:
        pix = pymupdf.Pixmap(blob)
        if pix.alpha or pix.n not in (1, 3, 4):
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        return pix.tobytes("png")
    except Exception:
        return None


def _paragraph_text(paragraph: Paragraph) -> str:
    """Paragraph text with manual line breaks (`Shift+Enter`) preserved as \\n."""
    parts: list[str] = []
    for node in paragraph._p.iter():
        tag = node.tag
        if tag == qn("w:t"):
            parts.append(node.text or "")
        elif tag in (qn("w:br"), qn("w:cr")):
            parts.append("\n")
        elif tag == qn("w:tab"):
            parts.append("\t")
    return "".join(parts)


def _paragraph_images(paragraph: Paragraph, doc) -> list[bytes]:
    """Embedded image bytes for a paragraph, in document order."""
    out: list[bytes] = []
    rids: list[str] = []
    for blip in paragraph._p.findall(".//" + qn("a:blip")):
        rid = blip.get(qn("r:embed")) or blip.get(qn("r:link"))
        if rid:
            rids.append(rid)
    for imagedata in paragraph._p.findall(".//" + VML_IMAGEDATA):
        rid = imagedata.get(R_ID)
        if rid:
            rids.append(rid)
    for rid in rids:
        rel = doc.part.rels.get(rid)
        if rel is None or not rel.reltype.endswith("/image"):
            continue
        try:
            out.append(rel.target_part.blob)
        except Exception:
            continue
    return out


def _iter_blocks(doc):
    """Yield paragraphs and tables in true document order."""
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def _docx_stream(doc, warnings: list[str]) -> tuple[list[Item], dict[str, bytes]]:
    """Flatten the document into the shared Item stream plus PNG assets.

    Each emitted line/image gets its own chunk id; the shared question builder
    treats one chunk as one paragraph, which mirrors the PDF profile closely
    enough for numbering, options and material/stem detection.
    """
    items: list[Item] = []
    assets: dict[str, bytes] = {}
    seen_hashes: set[str] = set()
    unreadable = 0

    def add_token(text: str) -> None:
        n = len(items)
        items.append(Item(text, 1, n, n * Y_STEP, n * Y_STEP + Y_HEIGHT, SIZE))

    def add_image(blob: bytes) -> None:
        nonlocal unreadable
        png = _to_png(blob)
        if png is None:
            unreadable += 1
            return
        digest = hashlib.sha1(png).hexdigest()
        if digest in seen_hashes:
            return
        seen_hashes.add(digest)
        stem = f"img{len(assets):02d}-{digest[:8]}"
        assets[stem] = png
        add_token(f"[[IMG:{stem}]]")

    def emit(paragraph: Paragraph) -> None:
        for line in _paragraph_text(paragraph).splitlines():
            cleaned = clean_text(line)
            if cleaned:
                add_token(cleaned)
        for blob in _paragraph_images(paragraph, doc):
            add_image(blob)

    for block in _iter_blocks(doc):
        if isinstance(block, Table):
            seen_cells: set[int] = set()
            for table_row in block.rows:
                for cell in table_row.cells:
                    key = id(cell._tc)                     # skip merged duplicates
                    if key in seen_cells:
                        continue
                    seen_cells.add(key)
                    for paragraph in cell.paragraphs:
                        emit(paragraph)
        else:
            emit(block)

    if unreadable:
        warnings.append(f"{unreadable} embedded image(s) could not be converted to PNG")
    return items, assets


def convert_docx(path: Path, title: str | None = None) -> ConvertedDoc:
    """Convert a Word .docx file to SAT-MD (deterministic, 0 token)."""
    title = title or path.stem
    warnings: list[str] = []

    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ConvertError(f"cannot read the file: {exc}", fallback=False) from exc
    if not data:
        raise ConvertError("the file is empty", fallback=False)
    _check_archive(data)

    try:
        doc = Document(BytesIO(data))
    except Exception as exc:
        raise ConvertError(f"cannot open DOCX: {exc}", fallback=False) from exc

    items, assets = _docx_stream(doc, warnings)
    if not items:
        raise ConvertError("no text could be extracted from the document", fallback=False)

    key_start, answer_map = _find_answer_key(items)
    if answer_map:
        warnings.append(f"answer key found: {len(answer_map)} entries")
    elif key_start < len(items):
        warnings.append("an answer-key heading was found but no answers could be read")

    groups = _group_questions(items, key_start, warnings)
    if not groups:
        groups = _group_questions(items, key_start, warnings, relaxed=True)
    if not groups:
        raise ConvertError(
            "no numbered questions detected. Questions must begin with a number "
            "such as '12.' or 'Question 12'.",
            fallback=False,
        )

    headings = [
        (idx, heading)
        for idx, item in enumerate(items)
        if (heading := match_section_heading(item.text))
    ]
    lang = _detect_lang(" ".join(item.text for item in items[:key_start]))

    questions: list[BuiltQuestion] = []
    section_hint: str | None = None
    heading_ptr = 0
    for group in groups:
        while heading_ptr < len(headings) and headings[heading_ptr][0] < group.start:
            section_hint = headings[heading_ptr][1]
            heading_ptr += 1
        built = _build_question(group, section_hint, warnings)
        if built is not None:
            questions.append(built)

    return _assemble(title, path.name, questions, answer_map, lang, assets, warnings,
                     pages=[PageReport(1, "text", source="docx")])