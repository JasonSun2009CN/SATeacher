"""Scanned-PDF OCR tests: adapter selection, TSV parsing, integration, fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.convert import ocr, pdf
from app.convert.ocr import tesseract
from app.convert.pdf import ConvertError, convert_pdf
from app.satmd.parser import parse

# --- engine discovery -------------------------------------------------------


def test_available_engines_shape() -> None:
    engines = ocr.available_engines()
    assert isinstance(engines, list)
    assert all(name in {"vision", "tesseract"} for name in engines)


def test_get_engine_returns_usable_or_none() -> None:
    engine = ocr.get_engine()
    if engine is not None:
        assert engine.NAME in ocr.available_engines()
        assert engine.available() is True


# --- tesseract TSV parsing (deterministic, no binary needed) ----------------


TSV = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
    "left\ttop\twidth\theight\tconf\ttext\n"
    "5\t1\t1\t1\t1\t1\t10\t20\t30\t12\t92.5\tHello\n"
    "5\t1\t1\t1\t1\t2\t45\t20\t40\t12\t88.0\tworld\n"
    "5\t1\t1\t1\t2\t1\t10\t40\t50\t12\t70.0\tSecond\n"
    "5\t1\t1\t1\t2\t2\t65\t40\t35\t12\t60.0\tline\n"
)


def test_parse_tsv_groups_words_into_lines() -> None:
    lines = tesseract._parse_tsv(TSV)
    assert [line.text for line in lines] == ["Hello world", "Second line"]
    first = lines[0]
    assert (first.x0, first.y0) == (10.0, 20.0)
    assert first.x1 == 85.0 and first.y1 == 32.0
    assert first.confidence == pytest.approx((0.925 + 0.880) / 2)
    assert lines[1].confidence == pytest.approx((0.70 + 0.60) / 2)


def test_parse_tsv_ignores_non_word_rows() -> None:
    ignored = (
        "5\t1\t1\t1\t9\t1\t0\t0\t0\t0\t-1\t\n"          # word row with empty text
        "1\t1\t0\t0\t0\t0\t0\t0\t0\t0\t-1\t\n"          # non-word row
    )
    assert [line.text for line in tesseract._parse_tsv(TSV + ignored)] == ["Hello world", "Second line"]


def test_parse_tsv_handles_empty() -> None:
    assert tesseract._parse_tsv("") == []
    assert tesseract._parse_tsv("garbage without tabs") == []


# --- integration ------------------------------------------------------------


needs_tesseract = pytest.mark.skipif(
    not tesseract.available(), reason="tesseract binary not installed"
)


@needs_tesseract
def test_scanned_pdf_is_read_by_ocr(sat_scanned: Path) -> None:
    result = convert_pdf(sat_scanned, title="Scanned")
    doc = parse(result.satmd)
    assert result.question_count >= 3, result.warnings
    assert len(doc.questions) == result.question_count
    assert any("OCR" in w for w in result.warnings), result.warnings


def test_text_pdf_does_not_trigger_ocr(sat_pdf: Path, monkeypatch) -> None:
    """A normal text PDF must never pay the OCR cost."""
    calls: list[int] = []

    def _boom(*_args, **_kwargs):  # pragma: no cover - must not run
        calls.append(1)
        raise AssertionError("OCR must not run on a text-layer PDF")

    monkeypatch.setattr(pdf._ocr, "get_engine", _boom)
    result = convert_pdf(sat_pdf)
    assert result.question_count == 5
    assert calls == []


def test_scanned_pdf_without_engine_is_friendly(sat_scanned: Path, monkeypatch) -> None:
    monkeypatch.setattr(pdf._ocr, "get_engine", lambda name=None: None)
    with pytest.raises(ConvertError, match="no OCR engine is available"):
        convert_pdf(sat_scanned)


def test_low_text_page_threshold() -> None:
    # Pages need at least this many visible characters before we trust the
    # text layer over OCR.
    assert pdf.PAGE_MIN_CHARS > 0