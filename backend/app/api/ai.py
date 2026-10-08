"""AI assist endpoints — explicit, user-triggered LLM calls only.

The import path never reaches this module (PLAN.md §3: 0 token on import);
the only entry point here is the AI-answer panel on the results page.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import llm, repos

router = APIRouter(prefix="/api/ai", tags=["ai"])

_OPT_RE = re.compile(r"^([A-D])[.)]\s*([\s\S]*)$")

SYSTEM = (
    "You are an SAT tutor. The user gives you one question and its correct "
    "answer. Explain concisely (at most 120 words), step by step, why that "
    "answer is correct. Write in the same language as the question. Plain "
    "text only: no headings, no markdown, no restating the question."
)


class AnswerPayload(BaseModel):
    document_id: int
    question_id: int
    session_id: int | None = None


def _fail(message: str, status: int) -> None:
    raise HTTPException(status_code=status, detail=message)


def _correct_option(options: list[str], letter: str) -> str:
    for option in options:
        m = _OPT_RE.match(option.strip())
        if m and m.group(1) == letter:
            return m.group(2).strip()
    return ""


@router.post("/answer")
def ai_answer(payload: AnswerPayload) -> dict:
    q = repos.documents.get_question(payload.document_id, payload.question_id)
    if q is None:
        _fail("question not found", 404)
        raise                                          # pragma: no cover
    if not q["answer"]:
        _fail("this question has no answer key yet — enter the answers first", 409)
    if not llm.configured():
        _fail("no LLM API configured — add an API key and a model in Settings", 409)

    # Get student's chosen answer if session_id provided
    student_answer = None
    if payload.session_id:
        student_answer = repos.sessions.get_student_answer(payload.session_id, payload.question_id)

    # Expanded context: material + stem + all options + correct answer + student's choice + section
    opts_list = q["options"]  # list of 4 strings like ["A. one", "B. two", "C. three", "D. four"]
    opts = {opt[0]: opt[3:].strip() for opt in opts_list if opt and opt[1] in ".．"}  # {"A": "one", "B": "two", ...}
    correct_letter = q["answer"]
    correct_text = _correct_option(opts_list, correct_letter)
    student_letter = student_answer
    student_text = _correct_option(opts_list, student_letter) if student_letter else None

    user_parts = []
    if q.get("material"):
        user_parts.append(f"Material:\n{q['material']}")
    user_parts.append(f"Question:\n{q['stem']}")
    user_parts.append("Options:")
    for letter in "ABCD":
        if letter in opts:
            prefix = "✓" if letter == correct_letter else ("→" if letter == student_letter else " ")
            user_parts.append(f"  {prefix} {letter}. {opts[letter]}")
    user_parts.append(f"\nCorrect answer: {correct_letter}. {correct_text}")
    if student_letter and student_text:
        user_parts.append(f"Your answer: {student_letter}. {student_text}")
    user_parts.append(f"Section: {q['sec'].upper()} ({'Reading & Writing' if q['sec'] == 'rw' else 'Math'})")

    user = "\n\n".join(user_parts)
    try:
        text = llm.complete(SYSTEM, [{"role": "user", "content": user}])
    except llm.LLMError as exc:
        _fail(str(exc), 502)
        raise                                          # pragma: no cover
    return {"text": text.strip()}
