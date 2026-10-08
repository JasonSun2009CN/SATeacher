"""Practice sessions: start, fetch (without answers), grade on submit."""

from __future__ import annotations

from app.db import db, one, query
from app.repos.documents import list_questions


def create_session(doc_id: int) -> int:
    from app.db import execute

    return execute("INSERT INTO sessions (document_id) VALUES (?)", (doc_id,))


def get_session(session_id: int) -> dict | None:
    row = one("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if row is None:
        return None
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def quiz_questions(doc_id: int) -> list[dict]:
    """Questions for the test UI — correct answers never leave the server."""
    return [
        {k: v for k, v in q.items() if k != "answer"}
        for q in list_questions(doc_id, include_answers=False)
    ]


def submit(session_id: int, answers: dict[int, str | None]) -> dict:
    """Grade one attempt; stores every response and returns the review payload."""
    return _grade(session_id, answers)


def regrade(session_id: int) -> dict:
    """Re-grade a submitted attempt against the *current* document answers.

    Used by the post-submit answer-key flow: the attempt is stored without a
    key (graded == 0), the user fills the key, then this re-runs grading using
    the choices already recorded in session_items.
    """
    rows = query(
        "SELECT question_id, chosen FROM session_items WHERE session_id = ? ORDER BY no",
        (session_id,),
    )
    if not rows:
        raise ValueError("session has not been submitted yet")
    chosen = {r["question_id"]: r["chosen"] for r in rows}
    return _grade(session_id, chosen)


def _grade(session_id: int, answers: dict[int, str | None]) -> dict:
    session = get_session(session_id)
    if session is None:
        raise KeyError(f"session {session_id} not found")
    questions = list_questions(session["document_id"])
    if not questions:
        raise KeyError("document has no questions")

    graded = correct = 0
    items: list[dict] = []
    with db() as conn:
        conn.execute("DELETE FROM session_items WHERE session_id = ?", (session_id,))
        for idx, q in enumerate(questions, start=1):
            chosen = answers.get(q["id"]) or answers.get(str(q["id"]))
            if chosen:
                chosen = chosen.upper()
            answer = q["answer"]
            is_correct: int | None = None
            if answer:
                graded += 1
                is_correct = 1 if chosen == answer else 0
                correct += is_correct
            conn.execute(
                "INSERT INTO session_items (session_id, question_id, no, chosen, is_correct,"
                " answered_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (session_id, q["id"], idx, chosen, is_correct),
            )
            items.append(
                {
                    "question_id": q["id"],
                    "no": idx,
                    "source_no": q["no"],
                    "sec": q["sec"],
                    "material": q["material"],
                    "stem": q["stem"],
                    "options": q["options"],
                    "images": q["images"],
                    "source": q["source"],
                    "chosen": chosen,
                    "answer": answer,
                    "is_correct": bool(is_correct) if is_correct is not None else None,
                    "explain": q["explain"],
                }
            )
        conn.execute(
            "UPDATE sessions SET finished_at = datetime('now') WHERE id = ?", (session_id,)
        )

    return {
        "session_id": session_id,
        "total": len(items),
        "graded": graded,
        "correct": correct,
        "items": items,
    }


def history(doc_id: int, limit: int = 20) -> list[dict]:
    rows = query(
        "SELECT s.id, s.started_at, s.finished_at,"
        " SUM(si.is_correct) AS correct, COUNT(si.is_correct) AS graded"
        " FROM sessions s LEFT JOIN session_items si ON si.session_id = s.id"
        " WHERE s.document_id = ? GROUP BY s.id ORDER BY s.id DESC LIMIT ?",
        (doc_id, limit),
    )
    return [
        {
            "session_id": r["id"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
            "correct": r["correct"] or 0,
            "graded": r["graded"] or 0,
        }
        for r in rows
    ]


def get_student_answer(session_id: int, question_id: int) -> str | None:
    """Get the student's chosen answer for a question in a session."""
    row = one(
        "SELECT chosen FROM session_items WHERE session_id = ? AND question_id = ?",
        (session_id, question_id),
    )
    return row["chosen"] if row else None
