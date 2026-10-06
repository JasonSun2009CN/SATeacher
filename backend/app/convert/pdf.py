"""PDF -> SAT-MD conversion.

Deterministic pipeline (PLAN.md §3): text extraction, column ordering, chunking,
question grouping by number sequence, option detection, answer-key backfill and
image placement. The LLM is NOT involved — it only gets a chance to run in
Phase 4 as a per-page fallback for pages this module cannot read.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from app import llm
from app.convert import bluebook as _bluebook
from app.convert import images as _images
from app.convert.model import BuiltQuestion, Item
from app.convert.normalize import (
    clean_text,
    guess_sec,
    is_answer_key_heading,
    is_chrome,
    join_lines,
    match_question_start,
    match_section_heading,
    parse_answer_entries,
    split_option_segments,
)
from app.satmd.parser import SatMdError, parse as parse_satmd

IMG_TOKEN_RE = re.compile(r"^\[\[IMG:([^\]]+)\]\]$")
INLINE_ANSWER_RE = re.compile(r"(?i)^\s*(?:answer|正确答案|答案)\s*[:：]?\s*\(?([A-D])\)?\s*$")

GAP_MERGE = 0.55         # line gap <= this * size -> same paragraph
GAP_BLANK = 1.6          # line gap >  this * size -> certainly a new paragraph
INDENT_JUMP = 12.0       # pt; a larger indent starts a new paragraph
NEW_QUESTION_GAP = 0.7   # gap that lets a numbered line start a new question


class ConvertError(Exception):
    """A user-facing conversion failure (bad file, unreadable layout, ...).

    `fallback=False` marks errors the LLM cannot help with either (no text
    layer, broken file) — those must not trigger an AI retry.
    """

    def __init__(self, message: str, *, fallback: bool = True):
        super().__init__(message)
        self.fallback = fallback


@dataclass
class Line:
    text: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    size: float


@dataclass
class Group:
    no: int | None
    page: int
    start: int                       # index of the first item, for section headings
    chunks: list[list[str]] = field(default_factory=list)


@dataclass
class ConvertedDoc:
    satmd: str
    assets: dict[str, bytes]
    warnings: list[str]
    answers_status: str          # inline | external | none
    question_count: int


# --------------------------------------------------------------------------
# page scan
# --------------------------------------------------------------------------


def _rank(line: Line, mid: float, width: float, height: float) -> tuple[int, float, float]:
    if line.x1 - line.x0 > width * 0.6:
        wide = True
    elif line.x1 <= mid + 10 or line.x0 >= mid - 10:
        wide = False
    else:
        wide = True
    if wide:
        band = 0 if line.y0 < height / 2 else 3
    else:
        band = 1 if line.x0 < mid else 2
    return band, line.y0, line.x0


def _is_figure(line: Line) -> bool:
    return line.text.startswith("[[IMG:")


def _order(lines: list[Line], width: float, height: float, mid: float) -> list[Line]:
    """Read a page top-to-bottom; switch to column order only for true 2-column pages."""
    left = [l for l in lines if l.x1 <= mid - 5 and not _is_figure(l)]
    right = [l for l in lines if l.x0 >= mid + 5 and not _is_figure(l)]
    two_column = len(left) >= 4 and len(right) >= 4
    if two_column:
        lines.sort(key=lambda l: _rank(l, mid, width, height))
    else:
        lines.sort(key=lambda l: (l.y0, l.x0))
    return lines


def _scan_page(
    page: pymupdf.Page,
    page_no: int,
    seen: set[str],
    warnings: list[str],
) -> tuple[list[Line], dict[str, bytes]]:
    """Extract ordered text lines plus figure PNGs for one page."""
    try:
        page_dict = page.get_text("dict", sort=False)
    except Exception as exc:
        warnings.append(f"page {page_no}: text extraction failed ({exc})")
        return [], {}

    width, height = page.rect.width, page.rect.height
    mid = width / 2
    figs = _images.collect_images(page, page_dict, page_no, seen)
    assets = {Path(f.name).stem: f.png for f in figs}
    lines: list[Line] = []
    anchored: set[tuple[float, float]] = set()

    for block in page_dict["blocks"]:
        if block["type"] != 0:
            rect = pymupdf.Rect(block["bbox"])
            if (rect.x1 - rect.x0) < 12 or (rect.y1 - rect.y0) < 12:
                continue
            fig = next(
                (f for f in figs
                 if abs(f.rect[0] - rect.x0) < 3 and abs(f.rect[1] - rect.y0) < 3),
                None,
            )
            if fig is None:
                continue
            stem = Path(fig.name).stem
            anchored.add((round(rect.x0, 1), round(rect.y0, 1)))
            lines.append(Line(f"[[IMG:{stem}]]", page_no,
                              rect.x0, rect.y0, rect.x1, rect.y1, rect.y1 - rect.y0))
            continue

        buf, first_y, last_y, size = "", None, None, 10.0
        for raw in block["lines"]:
            text = clean_text("".join(s.get("text", "") for s in raw.get("spans", [])))
            if not text:
                continue
            y0, y1 = raw["bbox"][1], raw["bbox"][3]
            if first_y is None:
                first_y = y0
            last_y = y1
            size = max(size, max((s.get("size", 10.0) for s in raw["spans"]), default=10.0))
            buf = join_lines(buf, text) if buf else text
        if not buf or first_y is None or last_y is None:
            continue
        if is_chrome(buf, first_y, last_y, height):
            continue
        lines.append(Line(buf, page_no, block["bbox"][0], first_y, block["bbox"][2], last_y, size))

    for fig in figs:                       # vector figures: anchor to nearest line
        key = (round(fig.rect[0], 1), round(fig.rect[1], 1))
        if key in anchored:
            continue
        stem = Path(fig.name).stem
        lines.append(Line(f"[[IMG:{stem}]]", page_no,
                          fig.rect[0], fig.rect[1], fig.rect[2], fig.rect[3],
                          max(fig.rect[3] - fig.rect[1], 8.0)))

    return _order(lines, width, height, mid), assets


# --------------------------------------------------------------------------
# chunking: lines -> paragraphs
# --------------------------------------------------------------------------


def _chunk_page(lines: list[Line]) -> list[list[Line]]:
    """Group lines into paragraphs by vertical gap and indent jump."""
    chunks: list[list[Line]] = []
    cur: list[Line] = []
    min_x = min((l.x0 for l in lines), default=0.0)
    for line in lines:
        if not cur or _is_figure(line) or _is_figure(cur[-1]):
            if cur:
                chunks.append(cur)
            cur = [line]
            continue
        prev = cur[-1]
        gap = line.y0 - prev.y1
        indented = (line.x0 - prev.x0) > INDENT_JUMP and line.x0 > min_x + INDENT_JUMP
        mergeable = gap <= GAP_MERGE * prev.size and not indented
        if mergeable and gap <= GAP_BLANK * prev.size:
            cur.append(line)
        else:
            chunks.append(cur)
            cur = [line]
    if cur:
        chunks.append(cur)
    return chunks


def _collect_items(pages: list[list[Line]]) -> list[Item]:
    items: list[Item] = []
    chunk_id = 0
    for lines in pages:
        for chunk in _chunk_page(lines):
            for line in chunk:
                items.append(Item(line.text, line.page, chunk_id, line.y0, line.y1, line.size))
            chunk_id += 1
    return items


# --------------------------------------------------------------------------
# answers
# --------------------------------------------------------------------------


def _find_answer_key(items: list[Item]) -> tuple[int, dict[int, str]]:
    for idx, item in enumerate(items):
        if is_answer_key_heading(item.text):
            tail = [i.text for i in items[idx + 1:] if not IMG_TOKEN_RE.match(i.text)]
            return idx, parse_answer_entries(tail)
    return len(items), {}


# --------------------------------------------------------------------------
# grouping: items -> questions
# --------------------------------------------------------------------------


def _has_options(items: list[Item]) -> bool:
    letters: set[str] = set()
    for it in items:
        if IMG_TOKEN_RE.match(it.text):
            continue
        _, segs = split_option_segments(it.text)
        letters.update(letter for letter, _ in segs)
        if letters >= {"A", "B", "C", "D"}:
            return True
    return False


def _group_questions(
    items: list[Item], key_start: int, warnings: list[str], relaxed: bool = False
) -> list[Group]:
    """Split the stream on question numbers that follow the source sequence.

    `relaxed=True` is a second pass for documents whose first question number is
    unusual (e.g. a section that starts at 10).
    """
    groups: list[Group] = []
    cur: list[Item] = []
    cur_no: int | None = None
    cur_start = 0
    expected: int | None = None

    def flush() -> None:
        nonlocal cur, cur_no, cur_start
        if cur:
            groups.append(_build_group(cur, cur_no, cur_start))
        cur, cur_no = [], None

    for idx, item in enumerate(items[:key_start]):
        n = None if IMG_TOKEN_RE.match(item.text) else match_question_start(item.text)
        if n is not None:
            prev = items[idx - 1] if idx else None
            new_page = prev is not None and prev.page != item.page
            gap_ok = prev is None or (item.y0 - prev.y1) > NEW_QUESTION_GAP * item.size
            ready = prev is None or new_page or gap_ok or _has_options(cur)

            if expected is None:
                primary = relaxed or n <= 3
            elif n == expected:
                primary = True
            elif n == 1 and expected > 1:          # next section restarts numbering
                primary = True
            elif expected < n <= expected + 10 and (new_page or gap_ok):
                primary = True                     # recover after a broken question
            else:
                primary = False

            if primary and ready:
                flush()
                cur_no, cur_start = n, idx
                expected = n + 1
                cur = [item]
                continue
        cur.append(item)
    flush()

    # groups without a number are leading instructions (or un-numbered content)
    kept = [g for g in groups if g.no is not None]
    if len(kept) < len(groups):
        ignored = " ".join(
            " ".join(_flat(g)) for g in groups if g.no is None
        )
        if len(ignored) > 80:
            warnings.append(
                f"ignored {len(ignored)} characters of content before the first numbered question"
            )
    return kept


def _flat(group: Group) -> list[str]:
    return [t for chunk in group.chunks for t in chunk]


def _build_group(items: list[Item], no: int | None, start: int) -> Group:
    chunks: list[list[str]] = []
    last_chunk: int | None = None
    for item in items:
        if last_chunk is None or item.chunk != last_chunk:
            chunks.append([])
            last_chunk = item.chunk
        chunks[-1].append(item.text)
    return Group(no=no, page=items[0].page, start=start, chunks=chunks)


# --------------------------------------------------------------------------
# question building
# --------------------------------------------------------------------------


def _build_question(
    group: Group, section_hint: str | None, warnings: list[str]
) -> BuiltQuestion | None:
    pre: list[list[str]] = []
    options: dict[str, str] = {}
    order: list[str] = []
    trailing: list[str] = []
    answer: str | None = None
    state = "pre"
    pending: list[str] = []

    def flush_pre() -> None:
        nonlocal pending
        if pending:
            pre.append(pending)
            pending = []

    for chunk in group.chunks:
        for text in chunk:
            if state == "pre":
                lead, segs = split_option_segments(text)
                # In the stem region only "A." can open the option list; anything
                # else (e.g. "The answer is D. ...") is stem text.
                if segs and segs[0][0] != "A":
                    pending.append(text)
                elif segs:
                    if lead:
                        pending.append(lead)
                    flush_pre()
                    state = "opt"
                    for letter, content in segs:
                        _add_option(options, order, letter, content, trailing)
                else:
                    pending.append(text)
                continue

            if state == "opt":
                if _add_option_line(options, order, text, trailing) and len(order) == 4:
                    state = "post"
                continue

            # post: everything after the fourth option
            if IMG_TOKEN_RE.match(text):
                _append_to_last(options, order, text)
            else:
                trailing.append(text)
        if state == "pre":
            flush_pre()

    flush_pre()
    if len(options) != 4:
        warnings.append(f"skipped question {_label(group)}: found {len(options)} of 4 options")
        return None

    material, stem = _split_material_stem(pre)
    if not stem:
        warnings.append(f"skipped question {_label(group)}: empty stem")
        return None
    if group.no is not None:
        if material is not None:
            material = _strip_question_number(material, group.no)
        else:
            stem = _strip_question_number(stem, group.no)

    for text in trailing:
        m = INLINE_ANSWER_RE.match(text)
        if m:
            answer = m.group(1)
        elif len(text) > 30:
            warnings.append(
                f"{_label(group)}: dropped trailing text {text[:40]!r} (after the options)"
            )

    sec = section_hint or guess_sec(f"{stem}\n{material or ''}")
    return BuiltQuestion(
        material=material,
        stem=stem,
        options=options,
        no=group.no,
        sec=sec,
        answer=answer,
        source=f"p.{group.page}",
    )


def _strip_question_number(text: str, no: int) -> str:
    """Drop the leading '12.' / '(12)' / 'Question 12' that we already store as `no`."""
    text = re.sub(rf"^\s*(?:Question|Q)\s*#?\s*{no}\s*[.):：]?\s*", "", text, count=1)
    text = re.sub(rf"^\s*\(?\s*{no}\s*[.、)．]\s+", "", text, count=1)
    return text


def _label(group: Group) -> str:
    return f"#{group.no}" if group.no is not None else f"(page {group.page})"


def _add_option(
    options: dict[str, str],
    order: list[str],
    letter: str,
    content: str,
    trailing: list[str],
) -> None:
    if letter in options:
        if content:
            options[letter] = join_lines(options[letter], content)
        return
    expected = "ABCD"[len(order)]
    if letter != expected:
        trailing.append(f"{letter}. {content}")
        return
    options[letter] = content
    order.append(letter)


def _add_option_line(
    options: dict[str, str], order: list[str], text: str, trailing: list[str]
) -> bool:
    """Handle one line after the options started; True when a marker was seen."""
    if IMG_TOKEN_RE.match(text):
        _append_to_last(options, order, text)
        return False
    lead, segs = split_option_segments(text)
    if not segs:
        if lead:
            if len(order) == 4:
                trailing.append(lead)
            else:
                _append_to_last(options, order, lead)
        return False
    if lead:
        if len(order) < 4:
            _append_to_last(options, order, lead)
        else:
            trailing.append(lead)
    for letter, content in segs:
        _add_option(options, order, letter, content, trailing)
    return True


def _append_to_last(options: dict[str, str], order: list[str], text: str) -> None:
    if order:
        last = order[-1]
        options[last] = join_lines(options[last], text)


def _split_material_stem(pre: list[list[str]]) -> tuple[str | None, str]:
    """The last paragraph above the options is the stem; everything before is material."""
    emitted = [e for e in (_emit(chunk) for chunk in pre) if e]
    if not emitted:
        return None, ""
    if len(emitted) == 1:
        return None, emitted[0]
    # An image-only paragraph at the end belongs to the stem, not to the material.
    if not _VISIBLE_TEXT_RE.sub("", emitted[-1]).strip() and len(emitted) >= 2:
        material = "\n\n".join(emitted[:-2])
        return (material or None), f"{emitted[-2]}\n\n{emitted[-1]}"
    return "\n\n".join(emitted[:-1]), emitted[-1]


_VISIBLE_TEXT_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def _emit(lines: list[str]) -> str:
    paragraphs: list[str] = []
    buf = ""
    for text in lines:
        m = IMG_TOKEN_RE.match(text)
        if m:
            if buf:
                paragraphs.append(buf)
                buf = ""
            paragraphs.append(f"![figure](assets/{m.group(1)}.png)")
        else:
            buf = join_lines(buf, text) if buf else text
    if buf:
        paragraphs.append(buf)
    return "\n\n".join(p for p in paragraphs if p)


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def _render_question(idx: int, q: BuiltQuestion) -> str:
    attrs = [f"#Q{idx:03d}", f"sec={q.sec}"]
    if q.no is not None:
        attrs.append(f"no={q.no}")
    out = [f":::q {{{' '.join(attrs)}}}"]
    if q.material:
        out += ["@material", q.material, ""]
    out += ["@stem", q.stem, ""]
    for letter in "ABCD":
        out.append(f"- {letter}. {q.options[letter]}")
    if q.answer:
        out.append(f"! answer: {q.answer}")
    out.append(f"! source: {q.source}")
    out.append(":::")
    return "\n".join(out)


def _front_matter(title: str, source: str, status: str, lang: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        "---\n"
        "satmd: 1\n"
        f'title: "{title}"\n'
        f'source: "{source}"\n'
        f"lang: {lang}\n"
        f"imported_at: {stamp}\n"
        f"answers: {status}\n"
        "---\n"
    )


def _detect_lang(text: str) -> str:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    total = cjk + latin
    if total == 0:
        return "en"
    ratio = cjk / total
    if ratio < 0.05:
        return "en"
    if ratio > 0.6:
        return "zh"
    return "mixed"


def _validate_block(block: str, title: str) -> str | None:
    try:
        parse_satmd(_front_matter(title, "-", "none", "en") + "\n" + block + "\n")
    except SatMdError as exc:
        return str(exc)
    return None


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def _assemble(
    title: str,
    source: str,
    questions: list[BuiltQuestion],
    answer_map: dict[int, str],
    lang: str,
    all_assets: dict[str, bytes],
    warnings: list[str],
) -> ConvertedDoc:
    """Validate, render and package questions — shared by both profiles."""
    inline_answers = 0
    for q in questions:
        if q.answer:
            inline_answers += 1
        elif q.no is not None and q.no in answer_map:
            q.answer = answer_map[q.no]

    blocks: list[str] = []
    for q in questions:
        block = re.sub(
            r"\[\[IMG:([^\]]+)\]\]", r"![figure](assets/\1.png)",
            _render_question(len(blocks) + 1, q),
        )
        err = _validate_block(block, title)
        if err:
            label = f"#{q.no}" if q.no is not None else f"(page {q.source})"
            warnings.append(f"skipped question {label}: {err}")
            continue
        blocks.append(block)

    if not blocks:
        raise ConvertError(
            "questions were detected but none could be converted cleanly: "
            + (warnings[0] if warnings else "unknown layout problem")
        )

    status = "external" if answer_map else ("inline" if inline_answers else "none")
    if status == "none":
        warnings.append("no answers in the source — fill them in on the next screen")

    # assets are written from the `![figure](assets/x.png)` refs in the rendered blocks
    referenced = {
        m for block in blocks for m in re.findall(r"!\[[^\]]*\]\(assets/([^)]+)\)", block)
    }
    assets = {name: all_assets[name.removesuffix(".png")] for name in referenced
              if name.removesuffix(".png") in all_assets}
    missing = {name for name in referenced if name.removesuffix(".png") not in all_assets}
    if missing:
        warnings.append(f"{len(missing)} figure(s) could not be extracted")

    satmd = _front_matter(title, source, status, lang) + "\n" + "\n\n".join(blocks) + "\n"

    try:
        parsed = parse_satmd(satmd)
    except SatMdError as exc:  # pragma: no cover - each block is validated above
        raise ConvertError(f"internal error: generated SAT-MD is invalid ({exc})") from exc

    return ConvertedDoc(
        satmd=satmd,
        assets=assets,
        warnings=warnings,
        answers_status=status,
        question_count=len(parsed.questions),
    )


def convert_pdf(path: Path, title: str | None = None) -> ConvertedDoc:
    """Convert a PDF to SAT-MD.

    Deterministic layout profiles run first (0 token). When they fail and an
    LLM API is configured, control passes to the labeling fallback
    (PLAN.md §3: the LLM rescues unreadable layouts, it is never the main path).
    """
    title = title or path.stem
    warnings: list[str] = []
    try:
        return _convert_deterministic(path, title, warnings)
    except ConvertError as err:
        if not err.fallback:
            raise
        if not llm.configured():
            raise ConvertError(
                f"{err} — no LLM API configured; add an API key and a model in "
                "Settings to enable AI-assisted import"
            ) from err
        from app.convert import llm_fallback

        llm_warnings: list[str] = []
        try:
            return llm_fallback.convert(path, title, llm_warnings)
        except ConvertError as ai_err:
            raise ConvertError(
                f"built-in layouts failed ({err}) and the AI fallback "
                f"failed too: {ai_err}"
            ) from ai_err


def _convert_deterministic(path: Path, title: str, warnings: list[str]) -> ConvertedDoc:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise ConvertError(f"cannot open PDF: {exc}", fallback=False) from exc
    try:
        if doc.needs_pass:
            raise ConvertError("the PDF is password protected", fallback=False)
        if doc.page_count == 0:
            raise ConvertError("the PDF has no pages", fallback=False)

        if _bluebook.detect(doc):
            result = _bluebook.convert(doc, warnings)
            if not result.questions:
                raise ConvertError(
                    "questions were detected but none could be converted cleanly: "
                    + (warnings[0] if warnings else "no readable two-column questions")
                )
            key_start, answer_map = _find_answer_key(result.items)
            if answer_map:
                warnings.append(f"answer key found: {len(answer_map)} entries")
            elif key_start < len(result.items):
                warnings.append("an answer-key heading was found but no answers could be read")
            lang = _detect_lang(" ".join(i.text for i in result.items[:key_start]))
            return _assemble(
                title, path.name, result.questions, answer_map, lang,
                result.assets, warnings,
            )

        seen_hashes: set[str] = set()
        pages: list[list[Line]] = []
        all_assets: dict[str, bytes] = {}
        for index in range(doc.page_count):
            lines, page_assets = _scan_page(doc.load_page(index), index + 1, seen_hashes, warnings)
            pages.append(lines)
            all_assets.update(page_assets)
    finally:
        doc.close()

    items = _collect_items(pages)
    if not items:
        raise ConvertError(
            "no text could be extracted (the PDF may be a scanned image)",
            fallback=False,
        )

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
            "such as '12.' or 'Question 12'."
        )

    headings = [
        (idx, h)
        for idx, item in enumerate(items)
        if (h := match_section_heading(item.text))
    ]
    lang = _detect_lang(" ".join(i.text for i in items[:key_start]))

    questions: list[BuiltQuestion] = []
    section_hint: str | None = None
    heading_ptr = 0
    for group in groups:
        while heading_ptr < len(headings) and headings[heading_ptr][0] < group.start:
            section_hint = headings[heading_ptr][1]
            heading_ptr += 1

        built = _build_question(group, section_hint, warnings)
        if built is None:
            continue
        questions.append(built)

    return _assemble(title, path.name, questions, answer_map, lang, all_assets, warnings)
