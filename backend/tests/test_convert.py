from pathlib import Path

import pytest

from app.convert.pdf import ConvertError, convert_pdf
from app.satmd.parser import parse
from tests.fixtures import build_numberless_pdf, build_sat_pdf


def test_converts_sample_pdf(sat_pdf: Path) -> None:
    result = convert_pdf(sat_pdf)
    doc = parse(result.satmd)

    assert result.question_count == 5 == len(doc.questions)
    assert result.answers_status == "external"
    assert not [w for w in result.warnings if w.startswith("skipped question")], result.warnings


def test_front_matter(sat_pdf: Path) -> None:
    result = convert_pdf(sat_pdf)
    doc = parse(result.satmd)
    assert doc.meta["satmd"] == "1"
    assert doc.meta["source"] == "sat-sample.pdf"
    assert doc.meta["answers"] == "external"
    assert doc.meta["lang"] == "en"


def test_material_and_stem_split(sat_pdf: Path) -> None:
    q1 = parse(convert_pdf(sat_pdf).satmd).questions[0]
    assert q1.no == 1
    assert q1.material and "reservations" in q1.material
    assert q1.stem.startswith("The author's attitude")
    assert q1.letter_options["B"] == "cautiously optimistic"
    assert q1.answer == "A"
    assert q1.source_ref == "p.1"


def test_wrapped_option_is_joined(sat_pdf: Path) -> None:
    q2 = parse(convert_pdf(sat_pdf).satmd).questions[1]
    assert q2.letter_options["B"] == (
        "well established and widely cited in the field for nearly a decade"
    )
    assert q2.answer == "C"


def test_bitmap_figure_is_extracted_and_placed(sat_pdf: Path) -> None:
    result = convert_pdf(sat_pdf)
    q3 = parse(result.satmd).questions[2]
    assert "assets/" in q3.stem, q3.stem
    assert q3.images, "image path should be recorded on the question"
    assert len(result.assets) >= 1
    name = q3.images[0].removeprefix("assets/")
    assert name in result.assets
    assert result.assets[name][:8] == b"\x89PNG\r\n\x1a\n"
    assert q3.letter_options["D"] == "30"
    assert q3.answer == "B"


def test_vector_figure_is_screenshotted(sat_pdf: Path) -> None:
    result = convert_pdf(sat_pdf)
    q4 = parse(result.satmd).questions[3]
    assert "3x + 5" in q4.stem
    assert "assets/" in q4.stem, q4.stem      # the axes drawing was captured
    assert len(result.assets) >= 2


def test_section_heading_sets_sec(sat_pdf: Path) -> None:
    questions = parse(convert_pdf(sat_pdf).satmd).questions
    assert [q.sec for q in questions[:3]] == ["rw", "rw", "rw"]
    assert [q.sec for q in questions[3:]] == ["math", "math"]


def test_options_on_one_line_and_two_per_line(sat_pdf: Path) -> None:
    questions = parse(convert_pdf(sat_pdf).satmd).questions
    assert questions[3].letter_options == {"A": "3", "B": "5", "C": "8", "D": "15"}
    assert questions[4].letter_options == {"A": "13", "B": "40", "C": "26", "D": "60"}
    assert questions[4].answer == "A"


def test_answer_key_applies_to_every_question(sat_pdf: Path) -> None:
    answers = [q.answer for q in parse(convert_pdf(sat_pdf).satmd).questions]
    assert answers == ["A", "C", "B", "D", "A"]


def test_numberless_pdf_is_rejected(tmp_path: Path) -> None:
    path = build_numberless_pdf(tmp_path / "no-numbers.pdf")
    with pytest.raises(ConvertError, match="no numbered questions"):
        convert_pdf(path)


def test_non_pdf_is_rejected(tmp_path: Path) -> None:
    junk = tmp_path / "junk.pdf"
    junk.write_text("not a pdf at all")
    with pytest.raises(ConvertError):
        convert_pdf(junk)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConvertError):
        convert_pdf(tmp_path / "absent.pdf")
