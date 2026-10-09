"""CB-style normalization: LLM rewrites question text with strict validation.

One question per LLM call, then the rewrite is validated against hard
invariants before anything is written:

* the correct answer never changes,
* the material passage never changes,
* exactly four options A-D survive,
* the source citation is never written back (出处不变 by construction),
* the rewritten block must **parse back** unchanged (:func:`_verify_block`) —
  a rewrite that would corrupt the SAT-MD block is rejected, not saved.

Two entry points:

* :func:`normalize_document` — the whole-document run behind the one-click
  UI (M6 UX: no per-question review). Every question that validates is
  applied in a single satmd rewrite; anything that fails validation keeps its
  original text and is reported in ``errors``.
* :func:`apply_normalization` — single question (API compatibility).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from app import llm
from app.convert.normalize import clean_text
from app.satmd.parser import ANSWERS, ParsedDoc, Question, SatMdError
from app.satmd.parser import parse as parse_satmd
from app.satmd.writer import render, render_block

ProgressFn = Callable[[int, int], None]
MAX_ERRORS = 50                          # cap what a job payload carries back


class NormalizeError(ValueError):
    """Validation failure during normalization."""


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------

SYSTEM = """\
You are an SAT question editor. Rewrite the question to match College Board style:
- Fix OCR artifacts, typos, garbled characters, broken line breaks.
- Standardize formatting: stem ends with a clear question, four options A-D on separate lines.
- Preserve mathematical notation exactly (LaTeX where present).
- Do NOT change the correct answer. The answer letter must stay the same.
- Do NOT add, remove, or reorder material passages.
- Output ONLY the JSON object below, no prose, no markdown fences.

{
  "material": "string or null",
  "stem": "string",
  "options": {"A": "string", "B": "string", "C": "string", "D": "string"},
  "answer": "A|B|C|D",
  "source_ref": "string"
}
"""

# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

_OPTION_RE = re.compile(r"^[A-D]\.[ \t]*(.+)$", re.MULTILINE)


def _validate_shape(obj: Any) -> dict:
    if not isinstance(obj, dict):
        raise NormalizeError("response is not a JSON object")
    required = ("material", "stem", "options", "answer", "source_ref")
    for k in required:
        if k not in obj:
            raise NormalizeError(f"missing required field: {k}")
    if not isinstance(obj["options"], dict) or set(obj["options"].keys()) != {"A", "B", "C", "D"}:
        raise NormalizeError("options must be an object with exactly keys A, B, C, D")
    for k, v in obj["options"].items():
        if not isinstance(v, str) or not v.strip():
            raise NormalizeError(f"option {k} must be a non-empty string")
        if "\n" in v or "\r" in v:
            raise NormalizeError(f"option {k} must stay on a single line")
    if obj["answer"] not in ("A", "B", "C", "D"):
        raise NormalizeError("answer must be A, B, C, or D")
    if obj["material"] is not None and not isinstance(obj["material"], str):
        raise NormalizeError("material must be string or null")
    if not isinstance(obj["stem"], str) or not obj["stem"].strip():
        raise NormalizeError("stem must be a non-empty string")
    return obj


def _validate_answer_preserved(original_answer: str, normalized_answer: str) -> None:
    if original_answer != normalized_answer:
        raise NormalizeError(
            f"answer changed during normalization: was {original_answer!r}, became {normalized_answer!r}"
        )


def _validate_material_preserved(original_material: str | None, normalized_material: str | None) -> None:
    """Allow minor whitespace normalization but no content change."""
    orig = clean_text(original_material or "")
    norm = clean_text(normalized_material or "")
    if orig != norm:
        raise NormalizeError("material passage was modified during normalization")


def _validate_options_preserve_meaning(
    original_opts: dict[str, str], normalized_opts: dict[str, str]
) -> list[str]:
    """Heuristic: option text should not be empty and should roughly correspond."""
    changed: list[str] = []
    for k in "ABCD":
        if clean_text(original_opts[k]) != clean_text(normalized_opts[k]):
            changed.append(k)
    return changed


# --------------------------------------------------------------------------
# Shape bridging: the DB/satmd store options as ["A. text", ...], the LLM and
# the validators speak {"A": "text", ...}. Never mix the two up.
# --------------------------------------------------------------------------


def to_lettered(options: Any) -> dict[str, str]:
    """Options as ``{A: text, ...}`` from either a list or an already-keyed dict."""
    if isinstance(options, dict):
        return {str(k): str(v) for k, v in options.items()}
    out: dict[str, str] = {}
    for opt in options or []:
        m = re.match(r"^\s*([A-D])[.)]\s*(.*)$", str(opt))
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def _option_list(lettered: dict[str, str]) -> list[str]:
    """``{A: text, ...}`` -> ``["A. text", ...]`` (the parser's storage shape)."""
    return [f"{k}. {lettered[k]}" for k in "ABCD"]


def _identical(original: dict, normalized: dict) -> bool:
    """True when the rewrite changed no visible text."""
    if clean_text(original.get("material") or "") != clean_text(normalized.get("material") or ""):
        return False
    if clean_text(original.get("stem") or "") != clean_text(normalized.get("stem") or ""):
        return False
    before = to_lettered(original.get("options"))
    after = to_lettered(normalized.get("options"))
    return all(clean_text(before.get(k, "")) == clean_text(after.get(k, "")) for k in "ABCD")


def _verify_block(before: Question, after: Question) -> None:
    """Re-parse the rewritten block and reject it if it would not survive.

    This is the last gate before a write: options that look like prose, a stem
    that swallows the option list, an id that shifts — all of them surface here
    as a :class:`NormalizeError`, and the question keeps its original text.
    """
    try:
        reparsed = parse_satmd(render_block(after)).questions
    except SatMdError as exc:
        raise NormalizeError(f"rewrite would not parse back: {exc}") from exc
    if len(reparsed) != 1:
        raise NormalizeError("rewrite did not round-trip to exactly one question")
    got = reparsed[0]
    if got.ext_id != before.ext_id:
        raise NormalizeError("question id changed during normalization")
    if (got.answer or "") != (before.answer or ""):
        raise NormalizeError("answer changed during normalization")
    if got.letter_options != after.letter_options:
        raise NormalizeError("options did not survive the rewrite")
    if clean_text(got.material or "") != clean_text(after.material or ""):
        raise NormalizeError("material did not survive the rewrite")
    if clean_text(got.stem or "") != clean_text(after.stem or ""):
        # a smuggled parser-significant line (e.g. "! answer: D") silently
        # vanishes from the stem on re-parse — refuse the write instead
        raise NormalizeError("stem did not survive the rewrite")
    if not got.stem.strip():
        raise NormalizeError("stem became empty after the rewrite")


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


@dataclass
class NormalizeResult:
    original: dict
    normalized: dict
    changed: list[str]          # which option letters changed text
    answer_preserved: bool
    requires_review: bool       # always true; caller decides to accept


def normalize_question(
    material: str | None,
    stem: str,
    options: dict[str, str],
    answer: str,
    source_ref: str,
) -> NormalizeResult:
    """Call LLM to normalize a single question; validate strictly."""
    if not llm.configured():
        raise NormalizeError("no LLM configured — set API key and model in Settings")

    user = json.dumps(
        {
            "material": material,
            "stem": stem,
            "options": options,
            "answer": answer,
            "source_ref": source_ref,
        },
        ensure_ascii=False,
    )

    raw = llm.complete(SYSTEM, [{"role": "user", "content": user}])

    # Extract JSON from response (tolerate stray text)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise NormalizeError("LLM response contained no JSON object")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise NormalizeError(f"LLM response was not valid JSON: {exc}") from exc

    normalized = _validate_shape(parsed)

    # Strict invariants
    _validate_answer_preserved(answer, normalized["answer"])
    _validate_material_preserved(material, normalized["material"])
    changed = _validate_options_preserve_meaning(options, normalized["options"])

    original = {
        "material": material,
        "stem": stem,
        "options": options,
        "answer": answer,
        "source_ref": source_ref,
    }

    return NormalizeResult(
        original=original,
        normalized={
            "material": normalized["material"],
            "stem": normalized["stem"],
            "options": normalized["options"],
            "answer": normalized["answer"],
            "source_ref": normalized["source_ref"],
        },
        changed=changed,
        answer_preserved=True,
        requires_review=True,
    )


def _load(doc_id: int) -> tuple[dict, ParsedDoc]:
    """Document row + parsed satmd, with user-facing errors."""
    from app.repos import documents as docs_repo

    doc = docs_repo.get_document(doc_id)
    if doc is None:
        raise NormalizeError("document not found")
    try:
        parsed = parse_satmd(docs_repo.read_satmd(doc_id))
    except SatMdError as exc:
        raise NormalizeError(f"cannot parse satmd: {exc}") from exc
    return doc, parsed


def _write(doc_id: int, parsed: ParsedDoc, changed: list[Question]) -> str:
    """Persist rewritten questions: satmd file first, then the DB rows."""
    from app.repos import documents as docs_repo

    text = render(parsed)
    docs_repo.write_satmd(doc_id, text)
    docs_repo.update_questions(doc_id, changed)
    return text


def apply_normalization(doc_id: int, ext_id: str, normalized: dict) -> dict:
    """Validate + persist one question's normalization (single-question API).

    ``ext_id`` is the ``#Q001`` id from the satmd block — not the numeric row
    id; the API layer translates.
    """
    normalized = _validate_shape(normalized)
    _, parsed = _load(doc_id)

    idx = next((i for i, q in enumerate(parsed.questions) if q.ext_id == ext_id), None)
    if idx is None:
        raise NormalizeError(f"question {ext_id} not found in document")
    before = parsed.questions[idx]
    if before.answer not in ANSWERS:
        raise NormalizeError(f"question {ext_id} has no answer key")

    _validate_answer_preserved(before.answer, normalized["answer"])
    _validate_material_preserved(before.material, normalized["material"])
    _validate_options_preserve_meaning(before.letter_options, to_lettered(normalized["options"]))

    candidate = replace(
        before,
        material=normalized["material"],
        stem=normalized["stem"],
        options=_option_list(to_lettered(normalized["options"])),
    )
    _verify_block(before, candidate)
    parsed.questions[idx] = candidate

    text = _write(doc_id, parsed, [candidate])
    return {"updated": ext_id, "satmd": text}


def normalize_document(doc_id: int, progress: ProgressFn | None = None) -> dict:
    """Rewrite **every** question in CB style and apply it in one pass.

    No per-question review: each rewrite that passes all invariants is applied
    immediately, everything else keeps its original text. Returns counters
    ``{total, applied, unchanged, kept, errors}`` where ``errors`` explains
    each ``kept`` question (capped at :data:`MAX_ERRORS`).
    """
    _, parsed = _load(doc_id)
    total = len(parsed.questions)
    applied = unchanged = kept = 0
    errors: list[str] = []
    changed: list[Question] = []

    for index, before in enumerate(parsed.questions, start=1):
        if before.answer not in ANSWERS:
            kept += 1
            errors.append(f"#{before.ext_id}: no answer key — skipped")
        elif len(before.letter_options) != 4:
            kept += 1
            errors.append(f"#{before.ext_id}: expected four options A-D — skipped")
        else:
            try:
                result = normalize_question(
                    material=before.material,
                    stem=before.stem,
                    options=before.letter_options,
                    answer=before.answer,
                    source_ref=before.source_ref or "",
                )
            except NormalizeError as exc:
                kept += 1
                errors.append(f"#{before.ext_id}: {exc}")
            except llm.LLMError as exc:
                kept += 1
                errors.append(f"#{before.ext_id}: LLM request failed: {exc}")
            else:
                if _identical(result.original, result.normalized):
                    unchanged += 1
                else:
                    candidate = replace(
                        before,
                        material=result.normalized["material"],
                        stem=result.normalized["stem"],
                        options=_option_list(to_lettered(result.normalized["options"])),
                    )
                    try:
                        _verify_block(before, candidate)
                    except NormalizeError as exc:
                        kept += 1
                        errors.append(f"#{before.ext_id}: {exc}")
                    else:
                        parsed.questions[index - 1] = candidate
                        changed.append(candidate)
                        applied += 1

        if progress is not None:
            progress(index, total)

    if changed:
        _write(doc_id, parsed, changed)

    return {
        "doc_id": doc_id,
        "total": total,
        "applied": applied,
        "unchanged": unchanged,
        "kept": kept,
        "errors": errors[:MAX_ERRORS],
    }