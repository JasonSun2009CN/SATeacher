"""Shared data structures for the PDF -> SAT-MD conversion profiles.

Kept in their own module so the plain-text profile (pdf.py) and the
Bluebook two-column profile (bluebook.py) can reference them without
circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Item:
    text: str
    page: int
    chunk: int
    y0: float
    y1: float
    size: float


@dataclass
class BuiltQuestion:
    material: str | None
    stem: str
    options: dict[str, str]
    no: int | None
    sec: str
    answer: str | None
    source: str


@dataclass
class PageReport:
    """Per-page conversion outcome, surfaced by the import pipeline UI.

    ``status`` is one of: ``text`` (text layer), ``ocr_ok``, ``low_confidence``,
    ``ocr_unavailable`` (no engine), ``ocr_failed`` (engine errored), ``empty``
    (OCR ran but read nothing). ``confidence`` is the engine's real mean word
    confidence in 0–1, or ``None`` when the source has no such signal.
    """

    no: int
    status: str
    source: str | None = None
    confidence: float | None = None
    reason: str | None = None
