"""Image extraction: embedded bitmaps and clustered vector drawings -> PNG assets."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pymupdf

MIN_SIZE = 25.0            # pt; smaller things are icons/spacers
MAX_FILL = 0.55            # max text coverage inside a vector cluster bbox
CLUSTER_GAP = 6.0          # pt; drawings closer than this belong to one figure
ZOOM = 3.0                 # rendering scale for clipped screenshots


@dataclass
class ExtractedImage:
    rect: tuple[float, float, float, float]
    name: str
    png: bytes


def _to_png(data: bytes) -> bytes | None:
    try:
        pix = pymupdf.Pixmap(data)
        if pix.alpha or pix.n not in (1, 3, 4):
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        return pix.tobytes("png")
    except Exception:
        return None


def _clip_png(page: pymupdf.Page, rect: pymupdf.Rect) -> bytes:
    pix = page.get_pixmap(clip=rect, matrix=pymupdf.Matrix(ZOOM, ZOOM), alpha=False)
    return pix.tobytes("png")


def _cluster(rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Union nearby drawing rects into figure-sized clusters."""
    boxes = [pymupdf.Rect(r) for r in rects]
    merged = True
    while merged and len(boxes) > 1:
        merged = False
        out: list[pymupdf.Rect] = []
        used = [False] * len(boxes)
        for i, a in enumerate(boxes):
            if used[i]:
                continue
            box = pymupdf.Rect(a)
            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                b = boxes[j]
                grown = pymupdf.Rect(
                    box.x0 - CLUSTER_GAP, box.y0 - CLUSTER_GAP,
                    box.x1 + CLUSTER_GAP, box.y1 + CLUSTER_GAP,
                )
                if grown.intersects(b):
                    box |= b
                    used[j] = True
                    merged = True
            used[i] = True
            out.append(box)
        boxes = out
    return boxes


def _text_coverage(box: pymupdf.Rect, lines: list[dict]) -> float:
    area = max((box.x1 - box.x0) * (box.y1 - box.y0), 1.0)
    covered = 0.0
    for line in lines:
        r = pymupdf.Rect(line["bbox"])
        inter = pymupdf.Rect(r) & box
        if inter.is_valid and inter.x1 > inter.x0 and inter.y1 > inter.y0:
            covered += (inter.x1 - inter.x0) * (inter.y1 - inter.y0)
    return covered / area


def _on_edge(page: pymupdf.Page, rect: pymupdf.Rect) -> bool:
    """True when the rect hugs two page edges — tiled backgrounds, not figures."""
    w, h = page.rect.width, page.rect.height
    near = 2.0
    r = pymupdf.Rect(rect)
    touches = 0
    if r.x0 <= near:
        touches += 1
    if r.x1 >= w - near:
        touches += 1
    if r.y0 <= near:
        touches += 1
    if r.y1 >= h - near:
        touches += 1
    return touches >= 2


def collect_images(
    page: pymupdf.Page,
    page_dict: dict,
    page_no: int,
    seen_hashes: set[str],
) -> list[ExtractedImage]:
    """Return every figure on the page, in reading order, with de-duplicated names."""
    out: list[ExtractedImage] = []
    taken: list[pymupdf.Rect] = []
    lines = [ln for b in page_dict["blocks"] if b["type"] == 0 for ln in b.get("lines", [])]

    def name_for(h: str) -> str:
        return f"p{page_no:02d}-{h[:8]}.png"

    # 1. embedded bitmaps (already in the block stream, keep their position)
    for block in page_dict["blocks"]:
        if block["type"] != 1:
            continue
        rect = pymupdf.Rect(block["bbox"])
        if (rect.x1 - rect.x0) < MIN_SIZE or (rect.y1 - rect.y0) < MIN_SIZE:
            continue
        if _on_edge(page, rect):
            continue                    # page background / watermark tile
        png = _to_png(block["image"])
        if not png:
            continue
        h = hashlib.sha1(png).hexdigest()
        if h in seen_hashes:
            taken.append(rect)
            continue
        seen_hashes.add(h)
        taken.append(rect)
        out.append(ExtractedImage(tuple(rect), name_for(h), png))

    # 2. vector figures (number lines, geometry sketches, charts)
    rects = [pymupdf.Rect(d["rect"]) for d in page.get_drawings() if d.get("rect")]
    for box in _cluster(rects):
        w, h = box.x1 - box.x0, box.y1 - box.y0
        if w < 40 or h < 25:
            continue
        if box.x0 < 0 or box.y0 < 0 or box.x1 > page.rect.width + 1 or box.y1 > page.rect.height + 1:
            continue
        if _on_edge(page, box):
            continue                    # full-page background strokes
        if _text_coverage(box, lines) > MAX_FILL:
            continue                      # that's a table/bordered text, not a figure
        if any((pymupdf.Rect(t) & box).get_area() > pymupdf.Rect(t).get_area() * 0.5 for t in taken):
            continue                      # already captured as a bitmap
        padded = pymupdf.Rect(box.x0 - 3, box.y0 - 3, box.x1 + 3, box.y1 + 3) & page.rect
        png = _clip_png(page, padded)
        h2 = hashlib.sha1(png).hexdigest()
        if h2 in seen_hashes:
            continue
        seen_hashes.add(h2)
        out.append(
            ExtractedImage(
                (padded.x0, padded.y0, padded.x1, padded.y1), name_for(h2), png
            )
        )

    out.sort(key=lambda img: (img.rect[1], img.rect[0]))
    return out
