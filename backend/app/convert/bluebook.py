"""Bluebook-style two-column profile for the PDF -> SAT-MD converter.

Some SAT exports (e.g. documents re-assembled from Bluebook screenshots)
render every question as a two-column row:

    [ passage text ]    [ badge 1 ]
                        [ stem     ]
                        [ (a) opt  ]
                        [ (b) opt  ]

Characteristics this module reads from block geometry — deterministically,
no LLM, no tokens:

* question numbers are detached digit badges (` 1`) in the right column,
  not prefixes of the stem;
* content-stream order does not follow visual order (rows come out 2, 1);
* options use circled lowercase letters (`LTCCircledW95-Caps`) and wrap
  into separate indented continuation blocks;
* every page carries its own header/footer (book page numbers, dates).

Pairing rule: a badge row owns the right-column blocks below it and the
left-column blocks top-aligned with it (within ROW_OFFSET points).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.convert import images as _images
from app.convert.model import BuiltQuestion, Item
from app.convert.normalize import clean_text, guess_sec, is_chrome, join_lines

BADGE_RE = re.compile(r"^\d{1,3}$")
OPT_START_RE = re.compile(r"^([a-d])[.)]?\s+\S")
OPT_SPLIT_RE = re.compile(r"^([a-d])[.)]?\s+(\S.*)$", re.S)

BADGE_Y0_MIN = 0.05          # below the page header
BADGE_Y0_MAX = 0.80          # above the footer zone
CONTENT_BOTTOM = 0.95         # last possible y for row content
OPTION_WINDOW = 0.55          # h; option list must start this close to the badge
ROW_OFFSET = 40.0             # pt; passages are top-aligned with their badge row
FOOTER_EDGE = 0.90            # bluebook footers sit higher than plain page edges
FOOTER_LEN = 40               # footer texts are short; real content is not
HEADER_MAX = 80
MIN_OPTIONS = 4


@dataclass
class Block:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    size: float
    circled: bool


@dataclass
class BluebookResult:
    questions: list[BuiltQuestion]
    items: list[Item]
    assets: dict[str, bytes]
    skipped_chars: int


# --------------------------------------------------------------------------
# page scan
# --------------------------------------------------------------------------


def _read_block(b: dict, page_no: int) -> Block | None:
    buf, first_y, last_y, size, circled = "", None, None, 10.0, False
    for raw in b.get("lines", []):
        text = ""
        for span in raw.get("spans", []):
            text += span.get("text", "")
            if "circled" in span.get("font", "").lower():
                circled = True
            size = max(size, span.get("size", 10.0))
        text = clean_text(text)
        if not text:
            continue
        if buf:
            buf = join_lines(buf, text)
        else:
            buf, first_y = text, raw["bbox"][1]
        last_y = raw["bbox"][3]
    if not buf or first_y is None or last_y is None:
        return None
    x0, _, x1, _ = b["bbox"]
    return Block(page_no, x0, first_y, x1, last_y, buf, size, circled)


def _is_footer(text: str, y0: float, y1: float, h: float) -> bool:
    if y1 <= FOOTER_EDGE * h:
        return False
    t = text.strip()
    if len(t) > FOOTER_LEN:
        return False
    return t.isdigit() or bool(re.search(r"\b(?:19|20)\d{2}\b", t)) or t.isupper()


def _section_of(text: str) -> str | None:
    if re.search(r"(?i)reading\s+and\s+writing", text):
        return "rw"
    if re.search(r"(?i)\bmath(?:ematics)?\b", text):
        return "math"
    return None


def _scan(page: pymupdf.Page, page_no: int) -> tuple[list[Block], str | None]:
    """Text blocks of one page with chrome removed, plus the section hint."""
    h = page.rect.height
    mid = page.rect.width / 2
    try:
        pdict = page.get_text("dict", sort=False)
    except Exception:
        return [], None
    blocks: list[Block] = []
    sec: str | None = None
    for b in pdict["blocks"]:
        if b["type"] != 0:
            continue
        blk = _read_block(b, page_no)
        if blk is None:
            continue
        if (
            sec is None
            and blk.y0 < h * 0.15
            and blk.x0 < mid
            and len(blk.text) <= HEADER_MAX
        ):
            sec = _section_of(blk.text)
        # digit badges are single numbers mid-page; chrome filtering must not
        # eat them (structural validation in _rows weeds out real page numbers)
        badge_here = (
            BADGE_RE.match(blk.text) is not None
            and blk.x0 >= mid
            and BADGE_Y0_MIN * h < blk.y0 < BADGE_Y0_MAX * h
        )
        if not badge_here and (
            is_chrome(blk.text, blk.y0, blk.y1, h)
            or _is_footer(blk.text, blk.y0, blk.y1, h)
        ):
            continue
        blocks.append(blk)
    return blocks, sec


# --------------------------------------------------------------------------
# badge / row detection
# --------------------------------------------------------------------------


def _is_option_start(blk: Block, badge: Block, circled_seen: bool) -> bool:
    if blk.circled:
        return True
    if circled_seen:
        return False
    return bool(OPT_START_RE.match(blk.text)) and blk.x0 - badge.x0 <= 15.0


def _rows(
    blocks: list[Block], mid: float, h: float
) -> list[tuple[Block, list[Block], list[Block]]]:
    """(badge, right-column region, left-column row) for every valid badge."""
    candidates = [
        b
        for b in blocks
        if BADGE_RE.match(b.text)
        and b.x0 >= mid
        and BADGE_Y0_MIN * h < b.y0 < BADGE_Y0_MAX * h
    ]
    candidates.sort(key=lambda b: b.y0)

    valid: list[Block] = []
    for badge in candidates:
        window = [
            b
            for b in blocks
            if b.x0 >= mid and badge.y0 < b.y0 < badge.y0 + OPTION_WINDOW * h
        ]
        circled_seen = any(b.circled for b in window)
        starts = sum(1 for b in window if _is_option_start(b, badge, circled_seen))
        if starts >= MIN_OPTIONS:
            valid.append(badge)

    out: list[tuple[Block, list[Block], list[Block]]] = []
    for i, badge in enumerate(valid):
        top = badge.y0
        bottom = valid[i + 1].y0 if i + 1 < len(valid) else CONTENT_BOTTOM * h
        right = sorted(
            (b for b in blocks if b.x0 >= mid and top < b.y0 < bottom),
            key=lambda b: b.y0,
        )
        left_top = top - ROW_OFFSET
        left_bottom = (
            valid[i + 1].y0 - ROW_OFFSET
            if i + 1 < len(valid)
            else CONTENT_BOTTOM * h
        )
        left = sorted(
            (b for b in blocks if b.x0 < mid and left_top <= b.y0 < left_bottom),
            key=lambda b: b.y0,
        )
        out.append((badge, right, left))
    return out


def detect(doc: pymupdf.Document) -> bool:
    """True when the document looks like a Bluebook two-column export."""
    pages_hit = 0
    badges_seen = 0
    for index in range(min(doc.page_count, 8)):
        page = doc.load_page(index)
        blocks, _ = _scan(page, index + 1)
        if not blocks:
            continue
        rows = _rows(blocks, page.rect.width / 2, page.rect.height)
        if rows:
            pages_hit += 1
            badges_seen += len(rows)
        if pages_hit >= 2 and badges_seen >= 3:
            return True
    return False


# --------------------------------------------------------------------------
# conversion
# --------------------------------------------------------------------------


def _assemble_field(
    blocks: list[Block], figs: list[tuple[float, str]]
) -> str:
    """Text blocks and figure tokens poured out in visual order."""
    entries = [(b.y0, b.x0, b.text) for b in blocks]
    entries += [(y, 0.0, f"[[IMG:{name}]]") for y, name in figs]
    entries.sort()
    return "\n\n".join(text for _, _, text in entries)


def _fig_is_chrome(fig: _images.ExtractedImage, blocks: list[Block], mid: float) -> bool:
    """True for screenshots of the question UI itself (badge/option boxes).

    Bluebook pages draw a rounded box around every option and behind the
    number badge; when those cluster into a low-text-coverage rectangle the
    generic extractor mistakes them for a figure. A figure covering a badge,
    a circled option, or any right-column text is UI chrome, not content.
    """
    rect = pymupdf.Rect(fig.rect)
    for b in blocks:
        cx, cy = (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2
        if not (rect.x0 - 2 <= cx <= rect.x1 + 2 and rect.y0 - 2 <= cy <= rect.y1 + 2):
            continue
        if b.circled or BADGE_RE.match(b.text):
            return True
        if cx >= mid:
            return True
    return False


MERGE_GAP = 95.0   # pt; graph fragments closer than this belong to one figure


def _merge_band_figs(page: pymupdf.Page, figs: list[_images.ExtractedImage]) -> list[_images.ExtractedImage]:
    """Union nearby fragments (bars, axis, legend) into one screenshot."""
    out = list(figs)
    if len(out) < 2:
        return out
    merged = True
    while merged:
        merged = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = pymupdf.Rect(out[i].rect), pymupdf.Rect(out[j].rect)
                grown = pymupdf.Rect(a.x0 - MERGE_GAP, a.y0 - MERGE_GAP,
                                     a.x1 + MERGE_GAP, a.y1 + MERGE_GAP)
                if not grown.intersects(b):
                    continue
                union = a | b
                png = _images._clip_png(page, union & page.rect)
                name = f"p{page.number + 1:02d}-{hashlib.sha1(png).hexdigest()[:8]}.png"
                out[i] = _images.ExtractedImage(
                    (union.x0, union.y0, union.x1, union.y1), name, png
                )
                out.pop(j)
                merged = True
                break
            if merged:
                break
    return out


def convert(doc: pymupdf.Document, warnings: list[str]) -> BluebookResult:
    seen: set[str] = set()
    questions: list[BuiltQuestion] = []
    items: list[Item] = []
    assets: dict[str, bytes] = {}
    skipped = 0
    chunk = 0

    for index in range(doc.page_count):
        page = doc.load_page(index)
        page_no = index + 1
        h, mid = page.rect.height, page.rect.width / 2

        try:
            pdict = page.get_text("dict", sort=False)
            figs = _images.collect_images(page, pdict, page_no, seen)
        except Exception:
            pdict, figs = {"blocks": []}, []
        blocks, sec_page = _scan(page, page_no)

        # drop screenshots of the question UI itself (option/badge boxes)
        figs = [f for f in figs if not _fig_is_chrome(f, blocks, mid)]
        assets.update({Path(f.name).stem: f.png for f in figs})
        rows = _rows(blocks, mid, h)

        # every kept block starts out unconsumed; questions claim theirs
        claimed: set[int] = set()

        def fig_center(f: _images.ExtractedImage) -> float:
            return (f.rect[1] + f.rect[3]) / 2

        figs_left = [
            f for f in figs
            if (f.rect[0] + f.rect[2]) / 2 < mid and fig_center(f) < CONTENT_BOTTOM * h
        ]
        figs_right = [
            f for f in figs
            if (f.rect[0] + f.rect[2]) / 2 >= mid and fig_center(f) < CONTENT_BOTTOM * h
        ]

        page_questions: list[BuiltQuestion] = []
        for row_i, (badge, right, left) in enumerate(rows):
            for b in [badge, *right, *left]:
                claimed.add(id(b))

            circled_seen = any(b.circled for b in right)
            starts: list[tuple[int, str, str]] = []
            bad = ""
            for i, b in enumerate(right):
                if not _is_option_start(b, badge, circled_seen):
                    continue
                m = OPT_SPLIT_RE.match(b.text)
                if not m:
                    bad = f"unrecognized option format {b.text[:30]!r}"
                    break
                starts.append((i, m.group(1).upper(), m.group(2)))

            label = f"#{badge.text.strip()}"
            if bad:
                warnings.append(f"skipped question {label}: {bad}")
                continue
            if len(starts) < MIN_OPTIONS:
                warnings.append(
                    f"skipped question {label}: found {len(starts)} of 4 options"
                )
                continue
            if len(starts) > 4 or [s[1] for s in starts[:4]] != list("ABCD"):
                warnings.append(
                    f"skipped question {label}: option letters "
                    f"{'/'.join(s[1] for s in starts)} are not A/B/C/D in order"
                )
                continue

            # figures: left-column ones go to the material, right-column to the stem
            next_top = (
                rows[row_i + 1][0].y0 - ROW_OFFSET
                if row_i + 1 < len(rows)
                else CONTENT_BOTTOM * h
            )
            mat_cands = [
                f for f in figs_left
                if badge.y0 - ROW_OFFSET <= fig_center(f) < next_top
            ]
            stem_cands = [
                f for f in figs_right
                if badge.y0 < fig_center(f) < badge.y0 + OPTION_WINDOW * h
            ]
            mat_cands = _merge_band_figs(page, mat_cands)
            stem_cands = _merge_band_figs(page, stem_cands)
            assets.update({Path(f.name).stem: f.png for f in [*mat_cands, *stem_cands]})
            mat_figs = [(fig_center(f), Path(f.name).stem) for f in mat_cands]
            stem_figs = [(fig_center(f), Path(f.name).stem) for f in stem_cands]

            stem_blocks = right[: starts[0][0]]
            if not any(b.text for b in stem_blocks):
                warnings.append(f"skipped question {label}: empty stem")
                continue
            stem = _assemble_field(stem_blocks, stem_figs)

            options: dict[str, str] = {}
            for n, (idx, letter, text) in enumerate(starts[:4]):
                end = starts[n + 1][0] if n + 1 < len(starts) else len(right)
                content = text
                for cont in right[idx + 1 : end]:
                    content = join_lines(content, cont.text)
                options[letter] = content

            material = _assemble_field(left, mat_figs) or None

            no = int(badge.text.strip())
            sec = sec_page or guess_sec(f"{stem}\n{material or ''}")
            q = BuiltQuestion(
                material=material,
                stem=stem,
                options=options,
                no=no,
                sec=sec,
                answer=None,
                source=f"p.{page_no}",
            )
            page_questions.append(q)

        questions.extend(page_questions)

        # bookkeeping: unconsumed text is skipped content, everything becomes
        # an item so the answer-key scanner and language detector see the doc
        for b in sorted(blocks, key=lambda b: (b.y0, b.x0)):
            items.append(Item(b.text, page_no, chunk, b.y0, b.y1, b.size))
            chunk += 1
            if id(b) not in claimed:
                skipped += len(b.text)

    if skipped > 80:
        warnings.append(
            f"skipped {skipped} characters of cover/header/directions content"
        )
    return BluebookResult(questions=questions, items=items, assets=assets, skipped_chars=skipped)
