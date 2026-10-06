"""Bluebook two-column profile: detection, pairing, options, chrome, figures."""

from pathlib import Path

import pymupdf

from app.convert import bluebook
from app.convert.pdf import convert_pdf
from app.satmd.parser import parse
from tests.fixtures import build_bluebook_pdf


def _convert(path: Path):
    return convert_pdf(path)


def test_detects_bluebook_layout(tmp_path: Path) -> None:
    path = build_bluebook_pdf(tmp_path / "bluebook.pdf")
    doc = pymupdf.open(path)
    try:
        assert bluebook.detect(doc) is True
    finally:
        doc.close()


def test_plain_pdf_is_not_bluebook(sat_pdf: Path) -> None:
    doc = pymupdf.open(sat_pdf)
    try:
        assert bluebook.detect(doc) is False
    finally:
        doc.close()


def test_converts_every_badge(tmp_path: Path) -> None:
    path = build_bluebook_pdf(tmp_path / "bluebook.pdf")
    result = _convert(path)
    doc = parse(result.satmd)

    assert result.question_count == 4 == len(doc.questions)
    assert [q.no for q in doc.questions] == [1, 2, 3, 4]
    assert [q.sec for q in doc.questions] == ["rw", "rw", "rw", "rw"]
    assert not [w for w in result.warnings if w.startswith("skipped question #1")]


def test_rows_pair_passage_with_question(tmp_path: Path) -> None:
    path = build_bluebook_pdf(tmp_path / "bluebook.pdf")
    doc = parse(_convert(path).satmd)

    q1, q2 = doc.questions[0], doc.questions[1]
    assert q1.material and "hummingbirds" in q1.material
    assert q2.material and "bioacoustics" in q2.material
    # the second row's passage must not leak into the first row
    assert "bioacoustics" not in (q1.material or "")
    assert q1.letter_options["B"] == (
        "well established and widely cited in the field for nearly a decade"
    )


def test_option_continuation_joined(tmp_path: Path) -> None:
    path = build_bluebook_pdf(tmp_path / "bluebook.pdf")
    doc = parse(_convert(path).satmd)
    assert doc.questions[0].letter_options == {
        "A": "elusive",
        "B": "well established and widely cited in the field for nearly a decade",
        "C": "indifferent",
        "D": "hostile",
    }


def test_page_chrome_never_reaches_questions(tmp_path: Path) -> None:
    path = build_bluebook_pdf(tmp_path / "bluebook.pdf")
    doc = parse(_convert(path).satmd)
    blob = "".join(
        (q.material or "") + q.stem + "".join(q.letter_options.values())
        for q in doc.questions
    )
    for leak in ("Section 1, Module", "September 13", "Reading and Writing"):
        assert leak not in blob, leak


def test_stray_digit_is_skipped_not_promoted(tmp_path: Path) -> None:
    path = build_bluebook_pdf(tmp_path / "bluebook.pdf")
    result = _convert(path)
    assert result.question_count == 4
    assert any("skipped question #42" in w for w in result.warnings), result.warnings


def test_left_column_bitmap_attached_to_row(tmp_path: Path) -> None:
    path = build_bluebook_pdf(tmp_path / "bluebook.pdf")
    result = _convert(path)
    q4 = parse(result.satmd).questions[3]
    assert q4.images, "bitmap in Q4's material should be extracted"
    name = q4.images[0].removeprefix("assets/")
    assert name in result.assets
    assert "assets/" in (q4.material or "")


def test_answers_status_is_none_and_warned(tmp_path: Path) -> None:
    path = build_bluebook_pdf(tmp_path / "bluebook.pdf")
    result = _convert(path)
    assert result.answers_status == "none"
    assert any("no answers in the source" in w for w in result.warnings)
    assert all(q.answer is None for q in parse(result.satmd).questions)
