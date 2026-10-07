"""OCR via the system `tesseract` binary (any OS) — no Python dependency.

We invoke the binary directly instead of requiring ``pytesseract`` so the app
stays installable everywhere; Tesseract itself stays optional. Word boxes come
from tesseract's TSV output (level 5 rows), with the engine's real per-word
confidence (conf, 0–100; -1 means "not a word").

Set `SATEACHER_OCR_LANG` to override the language (default `eng`).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.convert.ocr.base import OcrLine, OcrUnavailable

NAME = "tesseract"
DEFAULT_LANG = os.environ.get("SATEACHER_OCR_LANG", "eng")
TIMEOUT = 120


def binary() -> str | None:
    return shutil.which("tesseract")


def available() -> bool:
    return binary() is not None


def _parse_tsv(tsv: str) -> list[OcrLine]:
    """Group word rows (level 5) into visual lines with real confidences."""
    groups: dict[tuple[str, str, str, str], list[str]] = {}
    boxes: dict[tuple[str, str, str, str], list[float]] = {}
    confs: dict[tuple[str, str, str, str], list[float]] = {}

    for row in tsv.splitlines():
        cols = row.split("\t")
        if len(cols) < 12:
            continue
        if cols[0] != "5":                       # keep word-level rows only
            continue
        text = "\t".join(cols[11:]).strip()
        if not text:
            continue
        key = (cols[1], cols[2], cols[3], cols[4])
        try:
            left, top, width, height = (float(cols[6]), float(cols[7]),
                                        float(cols[8]), float(cols[9]))
        except ValueError:
            continue
        groups.setdefault(key, []).append(text)
        prev = boxes.get(key)
        if prev is None:
            boxes[key] = [left, top, left + width, top + height]
        else:
            prev[0] = min(prev[0], left)
            prev[1] = min(prev[1], top)
            prev[2] = max(prev[2], left + width)
            prev[3] = max(prev[3], top + height)
        try:
            conf = float(cols[10])
        except ValueError:
            conf = -1.0
        if conf >= 0:
            confs.setdefault(key, []).append(conf / 100.0)

    lines: list[OcrLine] = []
    for key, words in groups.items():
        box = boxes[key]
        confs_key = confs.get(key)
        confidence = sum(confs_key) / len(confs_key) if confs_key else None
        lines.append(OcrLine(" ".join(words), box[0], box[1], box[2], box[3], confidence))
    lines.sort(key=lambda line: (round(line.y0, 1), line.x0))
    return lines


def recognize(png: bytes, *, lang: str | None = None, binary_path: str | None = None) -> list[OcrLine]:
    exe = binary_path or binary()
    if exe is None:
        raise OcrUnavailable("the `tesseract` binary was not found on PATH")
    with tempfile.TemporaryDirectory(prefix="satocr-") as tmp:
        img = Path(tmp) / "page.png"
        img.write_bytes(png)
        out = Path(tmp) / "out"
        proc = subprocess.run(
            [exe, str(img), str(out), "-l", lang or DEFAULT_LANG, "--psm", "3", "tsv"],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        tsv_path = out.with_suffix(".tsv")
        if proc.returncode != 0 or not tsv_path.exists():
            message = (proc.stderr or "tesseract produced no output").strip()
            raise OcrUnavailable(f"tesseract failed: {message}")
        return _parse_tsv(tsv_path.read_text(encoding="utf-8", errors="replace"))