"""Practice session endpoints: start a run, submit it for grading."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.repos import documents as doc_repo
from app.repos import sessions as session_repo

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class StartPayload(BaseModel):
    document_id: int


class SubmitPayload(BaseModel):
    answers: dict[str, str | None] = {}


def _fail(message: str, status: int) -> None:
    raise HTTPException(status_code=status, detail=message)


@router.post("")
def start_session(payload: StartPayload) -> dict:
    doc = doc_repo.get_document(payload.document_id)
    if doc is None:
        _fail("document not found", 404)
        raise                                          # pragma: no cover
    questions = session_repo.quiz_questions(payload.document_id)
    if not questions:
        _fail("document has no questions", 409)
        raise                                          # pragma: no cover
    session_id = session_repo.create_session(payload.document_id)
    return {
        "session_id": session_id,
        "document": doc,
        "questions": questions,
    }


@router.get("/{session_id}")
def get_session(session_id: int) -> dict:
    session = session_repo.get_session(session_id)
    if session is None:
        _fail("session not found", 404)
        raise                                          # pragma: no cover
    doc = doc_repo.get_document(session["document_id"])
    return {**session, "document": doc, "questions": session_repo.quiz_questions(session["document_id"])}


@router.post("/{session_id}/submit")
def submit_session(session_id: int, payload: SubmitPayload) -> dict:
    if session_repo.get_session(session_id) is None:
        _fail("session not found", 404)
        raise                                          # pragma: no cover
    try:
        answers = {int(k): v for k, v in payload.answers.items()}
    except ValueError:
        _fail("answers must be keyed by question id", 400)
        raise                                          # pragma: no cover
    return session_repo.submit(session_id, answers)


@router.post("/{session_id}/regrade")
def regrade_session(session_id: int) -> dict:
    """Re-grade stored choices — the answer key may have been filled in after
    the attempt was submitted (post-submit key entry flow)."""
    if session_repo.get_session(session_id) is None:
        _fail("session not found", 404)
        raise                                          # pragma: no cover
    try:
        return session_repo.regrade(session_id)
    except ValueError as exc:
        _fail(str(exc), 409)
        raise                                          # pragma: no cover
