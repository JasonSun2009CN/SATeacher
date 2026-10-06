"""Hybrid conversion: deterministic first, LLM labeling fallback on failure."""

from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from app import llm
from app.convert.pdf import ConvertError, convert_pdf
from app.satmd.parser import parse
from tests.fixtures import build_numberless_pdf, build_sat_pdf

# verbatim labels for build_numberless_pdf's page text
GOOD = {
    "segments": [
        {"type": "ignore", "text": "No numbering here"},
        {"type": "question", "no": 1, "text": "Which of the following is true?"},
        {"type": "option", "no": 1, "letter": "A", "text": "A. one"},
        {"type": "option", "no": 1, "letter": "B", "text": "B. two"},
        {"type": "option", "no": 1, "letter": "C", "text": "C. three"},
        {"type": "option", "no": 1, "letter": "D", "text": "D. four"},
    ]
}


def _patch(monkeypatch: pytest.MonkeyPatch, responses: list, configured: bool = True):
    """Patch app.llm; `responses` are literals or callables(messages)->str."""
    calls: list = []

    def fake_complete(system: str, messages: list[dict[str, str]]) -> str:
        calls.append(messages)
        if not responses:
            raise AssertionError(f"unexpected extra LLM call #{len(calls)}")
        reply = responses.pop(0)
        return reply(messages) if callable(reply) else reply

    monkeypatch.setattr(llm, "configured", lambda: configured)
    monkeypatch.setattr(llm, "complete", fake_complete)
    return calls


def test_numberless_pdf_recovered_via_llm(tmp_path: Path, monkeypatch) -> None:
    path = build_numberless_pdf(tmp_path / "no-numbers.pdf")
    calls = _patch(monkeypatch, [json.dumps(GOOD)])

    result = convert_pdf(path)

    assert len(calls) == 1
    assert result.question_count == 1
    doc = parse(result.satmd)
    q = doc.questions[0]
    assert q.no == 1
    assert q.letter_options == {"A": "one", "B": "two", "C": "three", "D": "four"}
    assert q.stem == "Which of the following is true?"
    assert result.answers_status == "none"
    assert any("AI-assisted import" in w for w in result.warnings)


def test_answer_key_entries_flow_through(tmp_path: Path, monkeypatch) -> None:
    path = build_numberless_pdf(tmp_path / "no-numbers.pdf")
    with_answer = {
        "segments": [*GOOD["segments"], {"type": "answer", "no": 1, "letter": "B"}]
    }
    _patch(monkeypatch, [json.dumps(with_answer)])

    result = convert_pdf(path)

    assert result.answers_status == "external"
    assert parse(result.satmd).questions[0].answer == "B"


def test_deterministic_path_skips_llm_entirely(
    tmp_path: Path, monkeypatch
) -> None:
    path = build_sat_pdf(tmp_path / "numbered.pdf")
    calls = _patch(monkeypatch, [])  # configured=True but no replies queued

    result = convert_pdf(path)

    assert result.question_count == 5
    assert calls == []
    assert not any("AI-assisted" in w for w in result.warnings)


def test_without_api_key_error_points_to_settings(tmp_path: Path, monkeypatch) -> None:
    path = build_numberless_pdf(tmp_path / "no-numbers.pdf")
    _patch(monkeypatch, [], configured=False)

    with pytest.raises(ConvertError) as exc:
        convert_pdf(path)

    assert "no numbered questions" in str(exc.value)
    assert "Settings" in str(exc.value)


def test_bad_structure_is_retried_then_accepted(tmp_path: Path, monkeypatch) -> None:
    path = build_numberless_pdf(tmp_path / "no-numbers.pdf")
    broken = {"segments": GOOD["segments"][:-1]}          # missing option D
    calls = _patch(monkeypatch, [json.dumps(broken), json.dumps(GOOD)])

    result = convert_pdf(path)

    assert result.question_count == 1
    assert len(calls) == 2
    retry = calls[1]
    assert any("missing options D" in m["content"] for m in retry)


def test_fabricated_text_is_rejected_and_corrected(
    tmp_path: Path, monkeypatch
) -> None:
    path = build_numberless_pdf(tmp_path / "no-numbers.pdf")
    fabricated = {
        "segments": [
            seg if seg["type"] != "question" else {**seg, "text": "Completely made up stem"}
            for seg in GOOD["segments"]
        ]
    }
    calls = _patch(monkeypatch, [json.dumps(fabricated), json.dumps(GOOD)])

    result = convert_pdf(path)

    assert result.question_count == 1
    assert len(calls) == 2
    assert any("verbatim" in m["content"] for m in calls[1])


def test_gives_up_after_one_retry(tmp_path: Path, monkeypatch) -> None:
    path = build_numberless_pdf(tmp_path / "no-numbers.pdf")
    broken = json.dumps({"segments": GOOD["segments"][:-1]})
    calls = _patch(monkeypatch, [broken, broken])

    with pytest.raises(ConvertError, match="valid structure"):
        convert_pdf(path)

    assert len(calls) == 2


def test_non_json_response_counts_as_invalid(tmp_path: Path, monkeypatch) -> None:
    path = build_numberless_pdf(tmp_path / "no-numbers.pdf")
    calls = _patch(monkeypatch, ["sorry, I cannot help with that", json.dumps(GOOD)])

    result = convert_pdf(path)

    assert result.question_count == 1
    assert len(calls) == 2
    assert any("JSON" in m["content"] for m in calls[1])


def test_empty_pdf_never_reaches_the_llm(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "empty.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    calls = _patch(monkeypatch, [])  # would AssertionError if invoked

    with pytest.raises(ConvertError, match="no text could be extracted"):
        convert_pdf(path)

    assert calls == []


def test_chunking_keeps_pages_intact() -> None:
    from app.convert.llm_fallback import _chunk_pages

    pages = [f"=== page {i} ===\n{'x' * 900}" for i in range(1, 5)]
    chunks = _chunk_pages(pages)
    assert len(chunks) == 1                      # 4 x 917 chars fit one chunk
    assert chunks[0][1] == 1                     # first page number tracked
    assert "=== page 4 ===" in chunks[0][0]

    big = [f"=== page {i} ===\n{'y' * 7000}" for i in range(1, 4)]
    chunks = _chunk_pages(big)
    assert len(chunks) == 3                      # oversized pages split
    assert [start for _text, start in chunks] == [1, 2, 3]
