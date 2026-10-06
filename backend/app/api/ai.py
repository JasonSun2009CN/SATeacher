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

    # context engineering decision: question stem + correct option ONLY
    # (no material, no user's choice, no hand-written explanation)
    user = (
        f"Question:\n{q['stem']}\n\n"
        f"Correct answer: {q['answer']}. {_correct_option(q['options'], q['answer'])}"
    )
    try:
        text = llm.complete(SYSTEM, [{"role": "user", "content": user}])
    except llm.LLMError as exc:
        _fail(str(exc), 502)
        raise                                          # pragma: no cover
    return {"text": text.strip()}
