"""LLM-assisted import fallback: label extracted text, assemble with code.

Triggered by convert_pdf() ONLY when the deterministic profiles fail and an
API key is configured (PLAN.md §3: the LLM is a fallback, never the main path).

Context engineering: the model sees raw extracted text plus labeling rules and
a strict JSON contract — it tags material/question/option/answer/ignore spans
but never rewrites or invents content (verbatim fidelity is enforced against
the source text below).

Harness engineering: fixed-size page chunks, JSON-only responses, a
whitespace/quote-tolerant substring check against the source, structural
validation (four options per question, real numbers), and exactly one
corrective retry per chunk that feeds the validation errors back.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pymupdf

from app import llm
from app.convert.model import BuiltQuestion
from app.convert.normalize import guess_sec
from app.convert.pdf import (  # pdf does not import this module at load time
    ConvertError,
    ConvertedDoc,
    _assemble,
    _detect_lang,
    _strip_question_number,
)

CHUNK_CHARS = 6000
MAX_ATTEMPTS = 2
SEG_TYPES = {"material", "question", "option", "answer", "ignore"}

SYSTEM = """\
You label segments of exam text extracted from a PDF. The input may contain
layout noise (line breaks, headers, page numbers, directions).

Respond with ONLY a JSON object of this shape, no markdown fences, no prose:

{"segments": [{"type": "...", "text": "...", "no": 1, "letter": "A"}, ...]}

Segment types, in reading order:
- "material": passage/reading text that questions refer to. Emit it once
  before the first question that uses it, or again when a new passage begins.
- "question": one question stem. "no" = its printed number (if the questions
  are unnumbered, number them sequentially from 1). "text" = the stem only.
- "option": one choice of the currently open question: "no", "letter" (A-D)
  and "text".
- "answer": an answer-key entry with the correct "letter" for question "no".
  It carries no "text".
- "ignore": page headers, page numbers, directions, instructions,
  decorations — anything that does not belong to a question.

Rules:
1. Copy text VERBATIM from the input: same words, same order. Never
   paraphrase, translate, shorten, or fix anything. Whitespace may differ.
2. Every question must receive exactly four non-empty options A, B, C, D.
3. Emit segments in reading order; never merge or split questions.
4. Output a single JSON object with a "segments" array — nothing else.
"""

_PAGE_RE = re.compile(r"^=== page (\d+) ===")


# --------------------------------------------------------------------------
# extraction & chunking
# --------------------------------------------------------------------------


def _extract_pages(path: Path, page_numbers: list[int] | None = None) -> tuple[list[str], int]:
    """Return (page texts marked with page headers, image count)."""
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001 - pymupdf raises many types
        raise ConvertError(f"cannot open PDF: {exc}", fallback=False) from exc
    try:
        if doc.needs_pass:
            raise ConvertError("the PDF is password protected", fallback=False)
        if doc.page_count == 0:
            raise ConvertError("the PDF has no pages", fallback=False)
        pages: list[str] = []
        images = 0
        for index in range(doc.page_count):
            page_no = index + 1
            if page_numbers is not None and page_no not in page_numbers:
                continue
            page = doc.load_page(index)
            images += len(page.get_images(full=True))
            text = page.get_text("text", sort=True).strip()
            if text:
                pages.append(f"=== page {page_no} ===\n{text}")
        if not pages:
            raise ConvertError(
                "no text could be extracted from the selected pages",
                fallback=False,
            )
        return pages, images
    finally:
        doc.close()


def _split_big_block(block: str, page_no: int, size: int) -> list[str]:
    """Split an oversized page at line boundaries, repeating its header."""
    pieces: list[str] = []
    buf = ""
    for line in block.split("\n")[1:]:          # skip the original header
        candidate = f"{buf}\n{line}" if buf else line
        if buf and len(candidate) > size:
            pieces.append(buf)
            buf = line
        else:
            buf = candidate
    if buf:
        pieces.append(buf)
    return [f"=== page {page_no} ===\n{p}" for p in pieces]


def _chunk_pages(pages: list[str]) -> list[tuple[str, int]]:
    """Group page blocks into ~CHUNK_CHARS chunks of (text, first page no)."""
    blocks: list[tuple[str, int]] = []
    for block in pages:
        page_no = int(_PAGE_RE.match(block).group(1))
        if len(block) > CHUNK_CHARS:
            blocks.extend(
                (piece, page_no) for piece in _split_big_block(block, page_no, CHUNK_CHARS)
            )
        else:
            blocks.append((block, page_no))

    chunks: list[tuple[str, int]] = []
    buf, start = "", 0
    for block, page_no in blocks:
        if buf and len(buf) + len(block) > CHUNK_CHARS:
            chunks.append((buf, start))
            buf, start = "", 0
        if not buf:
            start = page_no
        buf = f"{buf}\n{block}" if buf else block
    if buf:
        chunks.append((buf, start))
    return chunks


# --------------------------------------------------------------------------
# response parsing
# --------------------------------------------------------------------------


def _parse(raw: str) -> tuple[list[dict] | None, list[str]]:
    """Pull the JSON segments array out of the raw model response."""
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None, ["response contained no JSON object"]
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return None, [f"response was not valid JSON: {exc}"]
    if isinstance(data, list):                       # tolerate a bare array
        data = {"segments": data}
    segments = data.get("segments")
    if not isinstance(segments, list):
        return None, ['missing the "segments" array']
    errors: list[str] = []
    for index, seg in enumerate(segments):
        if not isinstance(seg, dict):
            errors.append(f"segment {index} is not an object")
            continue
        seg_type = seg.get("type")
        if seg_type not in SEG_TYPES:
            errors.append(f"segment {index} has unknown type {seg_type!r}")
    if errors:
        return None, errors
    return segments, []


def _norm(text: str) -> str:
    """Whitespace/quote/case-insensitive normal form for fidelity checks."""
    text = unicodedata.normalize("NFKC", text)
    for src, dst in (
        ("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'),
        ("\u2013", "-"), ("\u2014", "-"), ("\u2026", "..."),
    ):
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _check_fidelity(segments: list[dict], source: str) -> list[str]:
    """Every labeled span must exist verbatim in the source chunk."""
    src = _norm(source)
    errors: list[str] = []
    for seg in segments:
        if seg.get("type") in ("ignore", "answer"):
            continue
        text = seg.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{seg.get('type')} segment has empty text")
            continue
        if _norm(text) not in src:
            errors.append(f"text not found verbatim in the source: {text[:60]!r}")
    return errors


# --------------------------------------------------------------------------
# assembly: labeled segments -> BuiltQuestion list
# --------------------------------------------------------------------------


def _interpret(
    segments: list[dict], page_hint: int
) -> tuple[list[BuiltQuestion], dict[int, str], list[str]]:
    """Group labeled segments into questions; returns (questions, answers, errors)."""
    questions: list[BuiltQuestion] = []
    answer_map: dict[int, str] = {}
    errors: list[str] = []
    material: list[str] = []          # sticky: carries to following questions
    material_stale = False            # a question started since the last passage
    cur: dict | None = None

    def flush() -> None:
        nonlocal cur
        if cur is None:
            return
        if not cur["stem"]:
            errors.append(f"question {cur['no']} has an empty stem")
        elif set(cur["options"]) != set("ABCD"):
            missing = sorted(set("ABCD") - set(cur["options"]))
            errors.append(f"question {cur['no']} is missing options {', '.join(missing)}")
        else:
            stem = _strip_question_number(cur["stem"], cur["no"])
            if not stem:
                errors.append(f"question {cur['no']} has an empty stem")
            else:
                text = stem + " " + " ".join(cur["material"])
                questions.append(
                    BuiltQuestion(
                        material="\n\n".join(cur["material"]) or None,
                        stem=stem,
                        options=cur["options"],
                        no=cur["no"],
                        sec=guess_sec(text),
                        answer=answer_map.get(no),
                        source=f"p.{page_hint}",
                    )
                )
        cur = None

    for seg in segments:
        seg_type = seg["type"]
        no = seg.get("no")

        if seg_type == "ignore":
            continue

        if seg_type == "answer":
            if isinstance(no, int) and seg.get("letter") in "ABCD" and seg.get("letter"):
                answer_map[no] = seg["letter"]
            else:
                errors.append(f"malformed answer segment: {seg!r}")
            continue

        if seg_type == "material":
            if material_stale:
                material = []
                material_stale = False
            material.append(str(seg.get("text", "")))
            continue

        if not isinstance(no, int) or no < 1:
            errors.append(f"{seg_type} segment has no valid question number: {seg!r}")
            continue

        if seg_type == "question":
            flush()
            material_stale = True
            cur = {
                "no": no,
                "stem": str(seg.get("text", "")).strip(),
                "options": {},
                "material": list(material),
            }
            continue

        # option
        letter = seg.get("letter")
        if letter not in "ABCD" or not letter:
            errors.append(f"option has no valid letter: {seg!r}")
            continue
        if cur is None or cur["no"] != no:
            errors.append(f"option {letter} for question {no} appears outside that question")
            continue
        text = str(seg.get("text", "")).strip()
        # tolerate the model copying the whole "A. one" line: drop the marker
        text = re.sub(rf"^\s*{re.escape(letter)}\s*[.):、]\s*", "", text, count=1)
        if letter in cur["options"]:
            cur["options"][letter] = f"{cur['options'][letter]} {text}".strip()
        else:
            cur["options"][letter] = text

    flush()
    return questions, answer_map, errors


# --------------------------------------------------------------------------
# chunk labeling with one corrective retry
# --------------------------------------------------------------------------


def _label_chunk(text: str, page_hint: int) -> tuple[list[dict], dict[int, str]]:
    task = (
        f"Label the following exam text (extracted from page {page_hint} onwards):\n\n"
        f"{text}"
    )
    messages: list[dict[str, str]] = [{"role": "user", "content": task}]
    last_errors: list[str] = []

    for _attempt in range(MAX_ATTEMPTS):
        try:
            raw = llm.complete(SYSTEM, messages)
        except llm.LLMError as exc:
            raise ConvertError(f"AI request failed: {exc}") from exc

        segments, errors = _parse(raw)
        if segments is not None:
            errors = _check_fidelity(segments, text)
            if not errors:
                _questions, answer_map, errors = _interpret(segments, page_hint)
                if not errors:
                    return segments, answer_map
        last_errors = errors
        shown = "\n".join(f"- {e}" for e in errors[:8])
        messages = [
            *messages,
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "Your response failed validation:\n"
                    f"{shown}\n\n"
                    "Fix these problems and respond with the corrected JSON object "
                    "only (same contract as before)."
                ),
            },
        ]

    raise ConvertError(
        "the AI could not produce a valid structure: " + "; ".join(last_errors[:3])
    )


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def convert(
    path: Path, title: str, warnings: list[str], page_numbers: list[int] | None = None
) -> ConvertedDoc:
    pages, images = _extract_pages(path, page_numbers)
    questions: list[BuiltQuestion] = []
    answer_map: dict[int, str] = {}

    for text, page_hint in _chunk_pages(pages):
        _segments, chunk_answers = _label_chunk(text, page_hint)
        built, chunk_map, errors = _interpret(_segments, page_hint)
        if errors:  # pragma: no cover - _label_chunk already validated this
            raise ConvertError("AI structure invalid: " + "; ".join(errors[:3]))
        questions.extend(built)
        answer_map.update(chunk_map)

    if not questions:
        raise ConvertError("the AI found no questions in the extracted text")

    warnings.append(
        "AI-assisted import: the layout was not recognized, "
        "question structure was extracted by the LLM"
    )
    if images:
        warnings.append(
            f"{images} image(s) in the source were not extracted by the AI fallback"
        )

    lang = _detect_lang(
        " ".join(
            [q.stem for q in questions]
            + [q.material or "" for q in questions]
        )
    )
    return _assemble(title, path.name, questions, answer_map, lang, {}, warnings)
