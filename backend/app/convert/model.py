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
