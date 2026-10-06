"""SAT-MD -> structured questions. Deterministic state machine, no LLM (PLAN.md §3)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

FORMAT_VERSION = 1
SECTIONS = ("rw", "math")
ANSWERS = ("A", "B", "C", "D")
DIFFICULTIES = ("e", "m", "h")

_FRONT_MATTER_RE = re.compile(r"^---\s*$")
_ATTR_RE = re.compile(r"""(?:#(?P<id>[\w.-]+))|(?P<key>\w+)=(?P<val>"[^"]*"|'[^']*'|\S+)""")
# Bullet is optional; three spellings accepted: "- A. x", "A. x", "(A) x".
_OPTION_RE = re.compile(
    r"^\s*(?:[-*]\s*)?\(?([A-D])\)(?:\s*[.)]\s*|\s+)(?P<in_paren>.*)"
    r"|^\s*(?:[-*]\s*)?([A-D])[.)]\s*(?P<bare>.*)"
)
_META_RE = re.compile(r"^\s*!\s*([A-Za-z_][\w-]*)\s*:\s*(.*)$")
# Any A-Z line-start that the option regex refuses (e.g. "E. ...") is a hard error,
# so unknown letters never silently leak into the stem.
_ANY_LETTER_OPT_RE = re.compile(r"^\s*(?:[-*]\s*)?\(?([A-Z])[.)]\s*")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_QUESTION_START_RE = re.compile(r"^:::q\s*\{(.*)\}\s*$")


class SatMdError(ValueError):
    """Structural error in a SAT-MD document, carrying a 1-based line number."""

    def __init__(self, message: str, line: int):
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


@dataclass
class Question:
    ext_id: str
    sec: str
    stem: str
    options: list[str]                       # exactly 4, "A. text"
    no: int | None = None
    type: str | None = None
    difficulty: str | None = None
    material: str | None = None
    answer: str | None = None
    explain: str | None = None
    source_ref: str | None = None
    images: list[str] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)   # unknown ! keys, preserved
    line: int = 0                             # line of ":::q" in source

    @property
    def letter_options(self) -> dict[str, str]:
        """{'A': 'text', ...} with the leading "A. " stripped."""
        out: dict[str, str] = {}
        for opt in self.options:
            m = re.match(r"^([A-D])[.)]\s*(.*)$", opt)
            if m:
                out[m.group(1)] = m.group(2)
        return out


@dataclass
class ParsedDoc:
    meta: dict[str, str]
    questions: list[Question]
    preamble: str = ""          # free text before the first block (ignored by the app)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_front_matter(lines: list[str]) -> tuple[dict[str, str], int]:
    """Returns (meta, index_of_first_line_after_front_matter)."""
    if not lines or not _FRONT_MATTER_RE.match(lines[0]):
        raise SatMdError("missing front matter opening '---'", 1)
    meta: dict[str, str] = {}
    for i in range(1, len(lines)):
        line = lines[i]
        if _FRONT_MATTER_RE.match(line):
            if "satmd" not in meta:
                raise SatMdError("front matter missing required 'satmd' version", i + 1)
            version = meta["satmd"]
            if not version.isdigit() or int(version) != FORMAT_VERSION:
                raise SatMdError(
                    f"unsupported SAT-MD version {version!r} (expected {FORMAT_VERSION})", i + 1
                )
            return meta, i + 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise SatMdError(f"invalid front matter line: {line.strip()!r}", i + 1)
        key, _, value = line.partition(":")
        meta[key.strip()] = _unquote(value.strip())
    raise SatMdError("front matter closing '---' not found", len(lines))


def _parse_attrs(attr_text: str, line: int) -> dict[str, str]:
    attrs: dict[str, str] = {}
    pos = 0
    while pos < len(attr_text):
        m = _ATTR_RE.match(attr_text, pos)
        if not m:
            if attr_text[pos].isspace():
                pos += 1
                continue
            raise SatMdError(f"cannot parse attribute near: {attr_text[pos:]!r}", line)
        if m.group("id"):
            attrs["id"] = m.group("id")
        else:
            attrs[m.group("key")] = _unquote(m.group("val"))
        pos = m.end()
    return attrs


def _split_body(body_lines: list[str], start_line: int) -> tuple[str | None, str]:
    """Split block body into (material, stem_or_rest) around optional @material/@stem markers."""
    mat_idx = next((i for i, l in enumerate(body_lines) if l.strip() == "@material"), None)
    stem_idx = next((i for i, l in enumerate(body_lines) if l.strip() == "@stem"), None)

    if mat_idx is None and stem_idx is None:
        return None, "\n".join(body_lines).strip()
    if mat_idx is not None and stem_idx is not None:
        if stem_idx <= mat_idx:
            raise SatMdError("@stem must come after @material", start_line + stem_idx)
        material = "\n".join(body_lines[mat_idx + 1 : stem_idx]).strip()
        stem = "\n".join(body_lines[stem_idx + 1 :]).strip()
        return (material or None), stem
    if mat_idx is not None:
        raise SatMdError("@material requires a following @stem", start_line + mat_idx)
    if stem_idx is not None:
        before = "\n".join(body_lines[:stem_idx]).strip()
        stem = "\n".join(body_lines[stem_idx + 1 :]).strip()
        if before:
            # No @material marker: content before @stem is the material.
            return before, stem
        return None, stem
    # @material without @stem: everything after it is material+stem in one go -> treat as stem.
    material = "\n".join(body_lines[mat_idx + 1 :]).strip()
    return None, material


def parse(text: str) -> ParsedDoc:
    lines = text.splitlines()
    meta, start = _parse_front_matter(lines)

    questions: list[Question] = []
    preamble_lines: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        m = _QUESTION_START_RE.match(line)
        if not m:
            if lines and not questions:
                preamble_lines.append(line)
            i += 1
            continue

        block_start = i + 1                     # 1-based line number of ":::q"
        attrs = _parse_attrs(m.group(1), i + 1)
        if "id" not in attrs:
            raise SatMdError("question block missing #id", block_start)
        if "sec" not in attrs:
            raise SatMdError("question block missing sec= (rw|math)", block_start)
        if attrs["sec"] not in SECTIONS:
            raise SatMdError(f"invalid sec={attrs['sec']!r} (expected rw|math)", block_start)

        body: list[str] = []
        i += 1
        closed = False
        while i < len(lines):
            if lines[i].strip() == ":::":
                closed = True
                i += 1
                break
            if _QUESTION_START_RE.match(lines[i]):
                raise SatMdError("nested ':::q' block", i + 1)
            body.append(lines[i])
            i += 1
        if not closed:
            raise SatMdError("unterminated question block (missing ':::')", block_start)

        options: list[str] = []
        meta_kv: dict[str, str] = {}
        unknown_kv: dict[str, str] = {}
        body_wo_opts: list[str] = []
        for offset, bline in enumerate(body):
            bline_no = block_start + 1 + offset
            om = _OPTION_RE.match(bline)
            if om:
                letter = om.group(1) or om.group(3)
                content = (om.group("in_paren") if om.group(1) else om.group("bare")) or ""
                if len(options) == 4:
                    raise SatMdError("question has more than 4 options", bline_no)
                expected = "ABCD"[len(options)]
                if letter != expected:
                    raise SatMdError(
                        f"expected option {expected}., got {letter}.", bline_no
                    )
                options.append(f"{letter}. {content.strip()}")
                continue
            # Only once options have started: prose/material may legitimately begin
            # lines with "T. S. Eliot" or "Q. What ..." and must not be flagged.
            bm = _ANY_LETTER_OPT_RE.match(bline) if options else None
            if bm:
                raise SatMdError(
                    f"unexpected option letter {bm.group(1)!r} (only A-D are allowed)", bline_no
                )
            km = _META_RE.match(bline)
            if km:
                key, value = km.group(1).lower(), km.group(2).strip()
                if key in ("answer", "explain", "source"):
                    meta_kv[key] = value
                else:
                    unknown_kv[key] = value     # preserved verbatim, see SAT-MD §3.3
                continue
            body_wo_opts.append(bline)

        if len(options) != 4:
            raise SatMdError(
                f"question must have exactly 4 options, found {len(options)}", block_start
            )

        answer = meta_kv.get("answer")
        if answer is not None:
            answer = answer.strip().upper()
            if answer not in ANSWERS:
                raise SatMdError(f"invalid answer {answer!r} (expected A-D)", block_start)

        material, stem = _split_body(body_wo_opts, block_start + 1)
        if not stem:
            raise SatMdError("question has empty stem", block_start)

        no_raw = attrs.get("no")
        no: int | None = None
        if no_raw is not None:
            if not no_raw.isdigit():
                raise SatMdError(f"invalid no={no_raw!r} (expected integer)", block_start)
            no = int(no_raw)

        difficulty = attrs.get("difficulty")
        if difficulty is not None and difficulty not in DIFFICULTIES:
            raise SatMdError(
                f"invalid difficulty={difficulty!r} (expected e|m|h)", block_start
            )

        images = _IMAGE_RE.findall(material or "") + _IMAGE_RE.findall(stem)
        for opt in options:
            images += _IMAGE_RE.findall(opt)

        questions.append(
            Question(
                ext_id=attrs["id"],
                sec=attrs["sec"],
                stem=stem.strip(),
                options=options,
                no=no,
                type=attrs.get("type"),
                difficulty=difficulty,
                material=(material.strip() or None) if material else None,
                answer=answer,
                explain=meta_kv.get("explain"),
                source_ref=meta_kv.get("source"),
                images=images,
                meta=dict(unknown_kv),
                line=block_start,
            )
        )

    seen: set[str] = set()
    for q in questions:
        if q.ext_id in seen:
            raise SatMdError(f"duplicate question id #{q.ext_id}", q.line)
        seen.add(q.ext_id)
    if not questions:
        raise SatMdError("document contains no ':::q' blocks", start + 1)

    return ParsedDoc(meta=meta, questions=questions, preamble="\n".join(preamble_lines).strip())


def set_answer(text: str, ext_id: str, answer: str) -> str:
    """Insert or replace `! answer:` for one question, preserving the rest of the file."""
    answer = answer.strip().upper()
    if answer not in ANSWERS:
        raise ValueError(f"invalid answer {answer!r}")
    lines = text.splitlines()
    pending = f"! answer: {answer}"
    out: list[str] = []
    block_start: int | None = None     # index in `out` of the target ":::q" line
    inserted = False

    for line in lines:
        m = _QUESTION_START_RE.match(line)
        if m:
            attrs = _parse_attrs(m.group(1), 0)
            block_start = len(out) if attrs.get("id") == ext_id else None
            out.append(line)
            continue
        if block_start is not None and line.strip() == ":::":
            # Replace an existing `! answer:` inside this block, otherwise append one.
            existing = next(
                (
                    j
                    for j in range(len(out) - 1, block_start, -1)
                    if (km := _META_RE.match(out[j])) and km.group(1).lower() == "answer"
                ),
                None,
            )
            if existing is not None:
                out[existing] = pending
            else:
                out.insert(len(out), pending)
            inserted = True
            block_start = None
            out.append(line)
            continue
        out.append(line)

    if not inserted:
        raise KeyError(f"question #{ext_id} not found")
    return "\n".join(out) + "\n"
