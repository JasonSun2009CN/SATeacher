"""SAT-MD writer round-trip: parse -> render -> parse must lose nothing."""

from __future__ import annotations

from app.satmd.parser import parse
from app.satmd.writer import render, render_block
from tests.conftest import MINI_SATMD

RICH_SATMD = """---
satmd: 1
title: "Rich Bank"
source: "rich.md"
lang: en
answers: inline
imported_at: 2026-10-09T00:00:00Z
---

<!-- preamble note -->

:::q {#Q001 sec=rw no=1 type=mc difficulty=e}
@material
Scientists have long debated the origin of the trait.

@stem
Which choice best completes the passage?

- A. one
- B. two
- C. three
- D. four
! answer: B
! explain: B fits the tone of the passage.
! source: p.12
! note: keep me
:::

:::q {#Q002 sec=math no=2}
@stem
What is the value of $x$ if $x + 2 = 5$?

- A. 1
- B. 3
- C. 5
- D. 7
! answer: C
:::
"""


def test_round_trip_mini() -> None:
    first = parse(MINI_SATMD)
    second = parse(render(first))
    assert second.meta == first.meta
    assert second.preamble == first.preamble
    assert len(second.questions) == len(first.questions)
    for a, b in zip(first.questions, second.questions):
        assert b.ext_id == a.ext_id
        assert b.sec == a.sec
        assert b.no == a.no
        assert b.stem == a.stem
        assert b.options == a.options
        assert b.material == a.material
        assert b.answer == a.answer


def test_round_trip_rich_document() -> None:
    first = parse(RICH_SATMD)
    second = parse(render(first))

    assert second.meta == first.meta              # includes imported_at, order kept
    assert second.preamble == first.preamble
    assert len(second.questions) == 2

    q1, q2 = first.questions[0], second.questions[0]
    assert q2.ext_id == q1.ext_id
    assert (q2.type, q2.difficulty, q2.no) == (q1.type, q1.difficulty, q1.no)
    assert q2.material == q1.material
    assert q2.stem == q1.stem
    assert q2.options == q1.options
    assert (q2.answer, q2.explain, q2.source_ref) == (q1.answer, q1.explain, q1.source_ref)
    assert q2.meta == q1.meta                     # unknown ! keys preserved

    assert second.questions[1].answer == "C"


def test_render_is_idempotent() -> None:
    once = render(parse(RICH_SATMD))
    twice = render(parse(once))
    assert once == twice                           # byte-stable after the first pass


def test_render_block_parses_back() -> None:
    q = parse(RICH_SATMD).questions[0]
    got = parse(render_block(q))
    assert len(got.questions) == 1
    assert got.questions[0].ext_id == "Q001"
    assert got.questions[0].letter_options == q.letter_options
