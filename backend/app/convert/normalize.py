"""Text cleanup and line-level classification used by the PDF -> SAT-MD converter.

Everything here is deterministic: no LLM, no guessing beyond the documented heuristics.
"""

from __future__ import annotations

import re

LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\u2010": "-",
    "\u2011": "-",
    "\u00ad": "",
    "\u200b": "",
}

# "12." / "(12)" / "12)" / "12、" at the very start of a line.
_QNUM_RE = re.compile(r"^\s*\(?\s*(\d{1,3})\s*[.、)．]\s*(?=\S)")
# "Question 12:" / "Q12."
_QWORD_RE = re.compile(r"^\s*(?:question|Q)\s*#?\s*(\d{1,3})\s*[.):：]?\s*", re.IGNORECASE)
# A marker letter such as "A." "(A)" "B)" "C:" — must be followed by space/end.
_OPT_MARKER_RE = re.compile(r"([A-D])[.、:：)]")
# Answer-key style entries: "12. B" / "12) (B)" / "12 - B"
_ANSWER_ENTRY_RE = re.compile(r"(\d{1,3})\s*[.、)．\-–—:]?\s*[\(]?\s*([A-D])\s*[\)]?")
_ANSWER_KEY_HEADING_RE = re.compile(
    r"(?i)^\s{0,20}(?:answer\s*key|answers?\b|key\s+to\s+(?:the\s+)?(?:test|questions)?"
    r"|scoring\s+guide|答案|参考答案|标准答案)\s*$"
)
_SECTION_HEADING_RE = re.compile(
    r"(?i)^\s{0,20}(?:section\s*\d+|module\s*\d+|reading\s+and\s+writing|math(?:ematics)?"
    r"|数学|语文|阅读|语法)\b[^A-Za-z0-9]{0,5}$"
)
_MATH_HEADING_RE = re.compile(r"(?i)^\s{0,20}(?:math|mathematics|数学)\s*$")

# Chrome (headers/footers/page numbers) that must never enter a question.
_CHROME_RE = re.compile(
    r"(?i)^\s*(?:page\s+\d+(?:\s+of\s+\d+)?|\d+\s*/\s*\d+|\d+|turn\s+over\b|continue\s+on\b"
    r"|-[ ]?\d+[ ]?-|©.*|sat\s+practice\s+test.*)$"
)

_MATH_SIGNALS = re.compile(
    r"(?:"
    r"[\d)]\s*[=<>±×÷⋅∙]\s*[\d(]|"
    r"[√πθ²³½¼]\s*[\d(]|"
    r"\^\{?\d|"
    r"\b(?:triangle|angle|circumference|radius|diameter|slope|y-intercept|equation"
    r"|inequality|function\s*\(|absolute value|integer|prime|percent|probability"
    r"|ratio|proportion|median|mean|volume|area|perimeter|coordinate|quadratic"
    r"|polynomial|exponent|fraction|system of equations|graph of)\b|"
    r"-\s*\d+\s*[+\-*/]\s*\d+|"
    r"\bwhat is the (?:value|total|average|number|cost|length)\b|"
    r"if\s+\w+\s*[=+\-*/]\s*\w+.*what\s+(?:is|are)\b"
    r")",
    re.IGNORECASE,
)

_RW_SIGNALS = re.compile(
    r"(?i)\b(?:which choice|best describes|the author|the passage|as used in|functioned"
    r"|conveys|implies|tone|transition|comma|semicolon|which of the following most"
    r"|according to|context|word|phrase|sentence)\b"
)


def clean_text(s: str) -> str:
    """Unicode tidy-up: ligatures, soft hyphens, collapsed whitespace."""
    for src, dst in LIGATURES.items():
        s = s.replace(src, dst)
    s = s.replace("\u2018", "'").replace("\u2019", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return s.strip()


def join_lines(prev: str, nxt: str) -> str:
    """Re-join a line that was wrapped in the source PDF."""
    if not prev:
        return nxt
    if prev.endswith("-") and nxt[:1].islower():
        return prev[:-1] + nxt
    if nxt[:1] in ",.;:)]}%\u2019\"'":
        return prev + nxt
    if prev.endswith(('"', "'", "\u201d")):
        return prev + nxt
    return prev + " " + nxt


def match_question_start(line: str) -> int | None:
    """Return the question number if the line starts a numbered question."""
    m = _QNUM_RE.match(line) or _QWORD_RE.match(line)
    if not m:
        return None
    return int(m.group(1))


def option_markers(line: str) -> list[tuple[int, str, int]]:
    """Find option markers `(index, letter, end_index)`; empty for prose lines.

    A leading prefix is accepted only when it looks like a lead-in — a question
    number, a colon, or sentence-ending punctuation — so prose such as
    "The answer is D. ..." is never read as an option list.
    """
    found = [(m.start(), m.group(1), m.end()) for m in _OPT_MARKER_RE.finditer(line)]
    if not found:
        return []
    first_idx = found[0][2]
    if first_idx < len(line) and not line[first_idx].isspace():
        return []                      # "D-Day", "A.very" -> not an option marker
    # strip a wrapping paren so "(A) 3 ..." is not mistaken for prose
    prefix = line[: found[0][0]].strip().lstrip("([{【")
    if prefix and not (
        re.match(r"^\(?\d{1,3}[.、)．]", prefix)
        or prefix.endswith((":", "：", ".", "。", "?", "？", "!", "！"))
    ):
        return []
    return [(i, letter, end) for i, letter, end in found if _has_space_after(line, end)]


def _has_space_after(line: str, end: int) -> bool:
    return end >= len(line) or line[end].isspace()


def split_option_segments(line: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a line into (lead-in text, [(letter, text), ...])."""
    marks = option_markers(line)
    if not marks:
        return line, []
    lead = line[: marks[0][0]].strip().lstrip("([{【")
    segments: list[tuple[str, str]] = []
    for n, (_, letter, end) in enumerate(marks):
        seg_end = marks[n + 1][0] if n + 1 < len(marks) else len(line)
        seg = line[end:seg_end].rstrip()
        # a "(" before the next marker belongs to that marker, not to this option
        if n + 1 < len(marks) and seg.endswith("("):
            seg = seg[:-1].rstrip()
        segments.append((letter, clean_text(seg)))
    return lead, segments


def is_answer_key_heading(line: str) -> bool:
    return bool(_ANSWER_KEY_HEADING_RE.match(line.strip())) and len(line.strip()) <= 40


def parse_answer_entries(lines: list[str]) -> dict[int, str]:
    """Extract `{question_number: letter}` from answer-key style text."""
    out: dict[int, str] = {}
    for line in lines:
        for m in _ANSWER_ENTRY_RE.finditer(line):
            no, letter = int(m.group(1)), m.group(2)
            if 1 <= no <= 200 and no not in out:
                out[no] = letter
    return out


def is_chrome(text: str, y0: float, y1: float, page_height: float) -> bool:
    """True for headers/footers/page numbers that must not reach the questions."""
    t = text.strip()
    if not t or len(t) > 80:
        return False
    if _CHROME_RE.match(t):
        return True
    near_edge = y0 < page_height * 0.06 or y1 > page_height * 0.94
    return near_edge and (t.isdigit() or len(t) <= 30 and t.isupper())


def match_section_heading(line: str) -> str | None:
    """Return 'rw' | 'math' when the line is a section heading, else None."""
    t = line.strip()
    if _MATH_HEADING_RE.match(t):
        return "math"
    if not _SECTION_HEADING_RE.match(t):
        return None
    return "math" if re.search(r"(?i)math|数学", t) else "rw"


def guess_sec(text: str) -> str:
    """Per-question fallback when no section heading was seen: 'rw' or 'math'."""
    math_score = len(_MATH_SIGNALS.findall(text))
    rw_score = len(_RW_SIGNALS.findall(text))
    if math_score and math_score >= rw_score:
        return "math"
    return "rw"


def split_paragraphs(lines: list[str]) -> list[str]:
    """Group consecutive lines into paragraphs (input is already gap-split)."""
    return [p.strip() for p in lines if p.strip()]
