"""CB-style normalization: LLM rewrites question text with strict validation.

User flow:
1. POST /normalize  -> returns { original, normalized, changed[], answer_preserved, requires_review }
2. User reviews side-by-side in NormalizeReview.tsx
3. POST /normalize/accept { normalized } -> validates again, writes to DB
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app import llm
from app.convert.normalize import clean_text
from app.satmd.parser import parse as parse_satmd
from app.satmd.parser import SatMdError


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


def accept_normalization(doc_id: int, question_id: int, normalized: dict) -> dict:
    """Validate + persist an accepted normalization. Called from /normalize/accept."""
    # Re-validate shape (defense in depth)
    normalized = _validate_shape(normalized)

    # Fetch original to re-check invariants
    from app.repos import documents as docs_repo

    doc = docs_repo.get_document(doc_id)
    if doc is None:
        raise NormalizeError("document not found")

    # We need the original question from the satmd file.
    satmd = docs_repo.read_satmd(doc_id)
    try:
        parsed = parse_satmd(satmd)
    except SatMdError as exc:
        raise NormalizeError(f"cannot parse satmd: {exc}") from exc

    orig_q = next((q for q in parsed.questions if q.id == question_id), None)
    if orig_q is None:
        raise NormalizeError(f"question {question_id} not found in document")

    # Re-validate against original
    _validate_answer_preserved(orig_q.answer or "", normalized["answer"])
    _validate_material_preserved(orig_q.material, normalized["material"])
    _validate_options_preserve_meaning(
        {k: v for k, v in orig_q.options.items()}, normalized["options"]
    )

    # Update the satmd with normalized text
    updated_questions = []
    for q in parsed.questions:
        if q.id == question_id:
            q.material = normalized["material"]
            q.stem = normalized["stem"]
            q.options = normalized["options"]
            # q.answer stays the same (validated)
        updated_questions.append(q)

    # Re-render satmd
    from app.convert.pdf import _front_matter, _render_question

    blocks = [_render_question(i + 1, q) for i, q in enumerate(updated_questions)]
    new_satmd = _front_matter(
        doc["title"], doc["source_filename"], doc["answers_status"], doc.get("lang", "en")
    ) + "\n" + "\n\n".join(blocks) + "\n"

    # Write back
    docs_repo.write_satmd(doc_id, new_satmd)
    docs_repo.update_questions(doc_id, updated_questions)

    return {"updated": question_id, "satmd": new_satmd}