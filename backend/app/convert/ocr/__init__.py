"""Cross-platform OCR for scanned PDF pages (see ``base`` for the contract)."""

from __future__ import annotations

from app.convert.ocr.base import (
    OcrLine,
    OcrUnavailable,
    available_engines,
    get_engine,
    is_available,
)

__all__ = [
    "OcrLine",
    "OcrUnavailable",
    "available_engines",
    "get_engine",
    "is_available",
]