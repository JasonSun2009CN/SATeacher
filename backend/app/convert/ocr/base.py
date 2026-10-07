"""Cross-platform OCR for scanned PDF pages.

Engines, first available wins:

1. ``vision``    — macOS Vision framework (``pyobjc-framework-Vision``, optional)
2. ``tesseract`` — the system ``tesseract`` binary, on any OS (optional)

No engine is required to install SATeacher. When a page has no text layer and
no engine is present, the PDF importer fails with a friendly, actionable error
instead of crashing (PLAN.md / RENOVATION_PLAN §8.2).

Confidence values are only ever taken from the engine itself; engines that do
not report confidence return ``None`` and the caller shows "ok" rather than a
fabricated number.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OcrLine:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float | None = None


class OcrUnavailable(RuntimeError):
    """Raised by an engine when it cannot run on this machine."""


def _engine_modules():
    # Imported lazily so a missing optional dependency never breaks startup.
    from app.convert.ocr import tesseract, vision

    return [vision, tesseract]


def available_engines() -> list[str]:
    """Names of OCR engines usable right now, in preference order."""
    names: list[str] = []
    for module in _engine_modules():
        try:
            if module.available():
                names.append(module.NAME)
        except Exception:
            continue
    return names


def get_engine(name: str | None = None):
    """Return the preferred usable engine module, or ``None``."""
    for module in _engine_modules():
        if name is not None and module.NAME != name:
            continue
        try:
            if module.available():
                return module
        except Exception:
            continue
    return None


def is_available() -> bool:
    return get_engine() is not None