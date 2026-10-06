import pytest

from app.satmd.parser import ParsedDoc, Question, SatMdError, parse, set_answer

VALID = """---
satmd: 1
title: "Fixture Paper"
source: "fixture.pdf"
lang: en
answers: none
---

<!-- preamble notes are ignored -->

:::q {#Q001 sec=rw no=1 type=vocab difficulty=m}
@material
Despite the reservations, the policy was adopted.

@stem
The author's attitude is best described as

- A. dismissive
- B. cautiously optimistic
- C. indifferent
- D. hostile
:::

:::q {#Q002 sec=math no=2}
If $3x + 5 = 20$, what is $x$?

![diagram](assets/q002-fig1.png)

(A) 3
(B) 5
(C) 8
(D) 15

! answer: B
! explain: Subtract 5, divide by 3.
! custom-key: kept
:::
"""


def test_parse_valid_document() -> None:
    doc = parse(VALID)
    assert doc.meta["title"] == "Fixture Paper"
    assert doc.meta["answers"] == "none"
    assert len(doc.questions) == 2
    assert "preamble notes" in doc.preamble


def test_question_fields() -> None:
    q1, q2 = parse(VALID).questions
    assert (q1.ext_id, q1.sec, q1.no, q1.type, q1.difficulty) == ("Q001", "rw", 1, "vocab", "m")
    assert q1.material is not None and "reservations" in q1.material
    assert q1.stem.startswith("The author's")
    assert q1.answer is None
    assert q1.options == [
        "A. dismissive",
        "B. cautiously optimistic",
        "C. indifferent",
        "D. hostile",
    ]
    assert q1.letter_options["B"] == "cautiously optimistic"

    assert q2.sec == "math"
    assert q2.material is None
    assert q2.answer == "B"
    assert q2.explain == "Subtract 5, divide by 3."
    assert q2.meta == {"custom-key": "kept"}
    assert q2.images == ["assets/q002-fig1.png"]


def test_option_spellings_all_accepted() -> None:
    text = VALID.replace("(A) 3", "- (A) 3").replace("(B) 5", "B. 5")
    q2 = parse(text).questions[1]
    assert q2.options[0] == "A. 3"
    assert q2.options[1] == "B. 5"


def test_question_without_markers_uses_whole_body_as_stem() -> None:
    q = parse(VALID).questions[0]
    assert q.stem  # covered via @material/@stem above; this guards the no-marker path
    no_markers = VALID.replace("@material\n", "").replace("@stem\n", "")
    q0 = parse(no_markers).questions[0]
    assert q0.material is None
    assert q0.stem.startswith("Despite")


def test_stem_marker_only_treats_prefix_as_material() -> None:
    text = VALID.replace("@material\n", "")
    q0 = parse(text).questions[0]
    assert q0.material is not None and "reservations" in q0.material
    assert q0.stem.startswith("The author's")


# --- error cases -----------------------------------------------------------


def test_missing_front_matter() -> None:
    with pytest.raises(SatMdError) as e:
        parse(":::q {#Q1 sec=rw}\nstem\n- A. a\n- B. b\n- C. c\n- D. d\n:::\n")
    assert e.value.line == 1


def test_unsupported_version() -> None:
    with pytest.raises(SatMdError, match="unsupported SAT-MD version"):
        parse(VALID.replace("satmd: 1", "satmd: 2"))


def test_missing_id() -> None:
    with pytest.raises(SatMdError, match="missing #id"):
        parse(VALID.replace("#Q001 ", ""))


def test_missing_sec() -> None:
    with pytest.raises(SatMdError, match="missing sec="):
        parse(VALID.replace(" sec=rw", ""))


def test_invalid_sec() -> None:
    with pytest.raises(SatMdError, match="invalid sec="):
        parse(VALID.replace("sec=rw", "sec=read"))


def test_invalid_difficulty() -> None:
    with pytest.raises(SatMdError, match="invalid difficulty="):
        parse(VALID.replace("difficulty=m", "difficulty=zz"))


def test_three_options_rejected() -> None:
    with pytest.raises(SatMdError, match="exactly 4 options, found 3"):
        parse(VALID.replace("- D. hostile\n", ""))


def test_five_options_rejected() -> None:
    with pytest.raises(SatMdError, match="more than 4 options"):
        parse(VALID.replace("- D. hostile", "- D. hostile\n- A. extra"))


def test_unknown_option_letter_rejected() -> None:
    with pytest.raises(SatMdError, match="unexpected option letter 'E'"):
        parse(VALID.replace("- D. hostile", "- D. hostile\n- E. extra"))


def test_out_of_order_options_rejected() -> None:
    with pytest.raises(SatMdError, match="expected option C."):
        parse(
            VALID.replace(
                "- C. indifferent\n- D. hostile",
                "- D. indifferent\n- C. hostile",
            )
        )


def test_invalid_answer_rejected() -> None:
    with pytest.raises(SatMdError, match="invalid answer"):
        parse(VALID.replace("! answer: B", "! answer: E"))


def test_duplicate_id_rejected() -> None:
    with pytest.raises(SatMdError, match="duplicate question id"):
        parse(VALID.replace("#Q002", "#Q001"))


def test_unterminated_block() -> None:
    with pytest.raises(SatMdError, match="unterminated"):
        parse(VALID.rsplit(":::", 1)[0] + "still inside\n")


def test_no_questions() -> None:
    with pytest.raises(SatMdError, match="no ':::q' blocks"):
        parse("---\nsatmd: 1\n---\nnothing here\n")


def test_material_without_stem_rejected() -> None:
    broken = VALID.replace("@stem\n", "")
    with pytest.raises(SatMdError, match="@material requires a following @stem"):
        parse(broken)


# --- set_answer ------------------------------------------------------------


def test_set_answer_inserts_into_block_without_answer() -> None:
    updated = set_answer(VALID, "Q001", "a")
    assert "! answer: A" in updated.split(":::q {#Q002")[0]
    assert parse(updated).questions[0].answer == "A"


def test_set_answer_replaces_existing() -> None:
    updated = set_answer(VALID, "Q002", "D")
    block = updated.split(":::q {#Q002")[1]
    assert block.count("! answer:") == 1
    assert "! answer: D" in block
    assert parse(updated).questions[1].answer == "D"


def test_set_answer_unknown_id() -> None:
    with pytest.raises(KeyError):
        set_answer(VALID, "Q999", "A")


def test_set_answer_invalid_letter() -> None:
    with pytest.raises(ValueError):
        set_answer(VALID, "Q001", "E")


def test_round_trip_is_idempotent() -> None:
    updated = set_answer(VALID, "Q001", "B")
    assert parse(updated).questions[0].answer == "B"
    assert parse(set_answer(updated, "Q001", "B")).questions[0].answer == "B"
