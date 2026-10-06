"""Documents and questions persistence (PLAN.md §5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.db import assets_dir, db, satmd_path
from app.satmd.parser import Question


def _question_dict(row: Any, include_answer: bool = True) -> dict:
    data = {
        "id": row["id"],
        "ext_id": row["ext_id"],
        "no": row["no"],
        "sec": row["sec"],
        "type": row["type"],
        "difficulty": row["difficulty"],
        "material": row["material"],
        "stem": row["stem"],
        "options": json.loads(row["options_json"]),
        "images": json.loads(row["images_json"]),
        "source": row["source_ref"],
        "explain": row["explain"],
        "answer": row["answer"] if include_answer else None,
    }
    return data


def create_document(
    title: str,
    source_filename: str,
    answers_status: str,
    question_count: int,
    builtin_key: str | None = None,
) -> int:
    from app.db import execute

    return execute(
        "INSERT INTO documents (title, source_filename, satmd_path, answers_status,"
        " question_count, builtin_key) VALUES (?, ?, ?, ?, ?, ?)",
        (
            title,
            source_filename,
            str(satmd_path(0)),
            answers_status,
            question_count,
            builtin_key,
        ),
    )


def get_by_builtin_key(key: str) -> int | None:
    """Document id registered for a built-in unit ("bank_id/unit_id"), if any."""
    from app.db import one

    row = one("SELECT id FROM documents WHERE builtin_key = ?", (key,))
    return int(row["id"]) if row else None


def get_builtin_keys(keys: list[str]) -> dict[str, int]:
    """Map of builtin_key -> document id for every key that exists."""
    from app.db import query

    if not keys:
        return {}
    marks = ",".join("?" * len(keys))
    rows = query(
        f"SELECT builtin_key, id FROM documents WHERE builtin_key IN ({marks})",
        tuple(keys),
    )
    return {row["builtin_key"]: int(row["id"]) for row in rows}


def set_satmd_path(doc_id: int) -> None:
    from app.db import execute

    execute("UPDATE documents SET satmd_path = ? WHERE id = ?", (str(satmd_path(doc_id)), doc_id))


def insert_questions(doc_id: int, questions: list[Question]) -> None:
    with db() as conn:
        for idx, q in enumerate(questions):
            conn.execute(
                "INSERT INTO questions (document_id, ext_id, no, sec, type, difficulty,"
                " material, stem, options_json, answer, explain, source_ref, images_json, order_idx)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    doc_id,
                    q.ext_id,
                    q.no,
                    q.sec,
                    q.type,
                    q.difficulty,
                    q.material,
                    q.stem,
                    json.dumps(q.options, ensure_ascii=False),
                    q.answer,
                    q.explain,
                    q.source_ref,
                    json.dumps(q.images, ensure_ascii=False),
                    idx,
                ),
            )


def get_document(doc_id: int) -> dict | None:
    from app.db import one

    row = one("SELECT * FROM documents WHERE id = ?", (doc_id,))
    if row is None:
        return None
    counts = one(
        "SELECT COUNT(*) AS total, SUM(answer IS NOT NULL) AS answered"
        " FROM questions WHERE document_id = ?",
        (doc_id,),
    )
    total = counts["total"] or 0
    answered = counts["answered"] or 0
    return {
        "id": row["id"],
        "title": row["title"],
        "source_filename": row["source_filename"],
        "answers_status": row["answers_status"],
        "question_count": row["question_count"],
        "answered_count": answered,
        "needs_answers": answered < total,
        "created_at": row["created_at"],
    }


def list_documents() -> list[dict]:
    from app.db import query

    rows = query("SELECT id FROM documents ORDER BY id DESC")
    return [d for r in rows if (d := get_document(r["id"])) is not None]


def delete_document(doc_id: int) -> bool:
    from app.db import execute, query

    exists = query("SELECT id FROM documents WHERE id = ?", (doc_id,))
    if not exists:
        return False
    execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    return True


def list_questions(doc_id: int, include_answers: bool = True) -> list[dict]:
    from app.db import query

    rows = query(
        "SELECT * FROM questions WHERE document_id = ? ORDER BY order_idx", (doc_id,)
    )
    return [_question_dict(r, include_answer=include_answers) for r in rows]


def set_answers(doc_id: int, answers: dict[str, str]) -> int:
    """Write user-entered answers by ext_id; returns how many rows changed."""
    with db() as conn:
        changed = 0
        for ext_id, letter in answers.items():
            cur = conn.execute(
                "UPDATE questions SET answer = ? WHERE document_id = ? AND ext_id = ?",
                (letter.upper(), doc_id, ext_id),
            )
            changed += cur.rowcount
    return changed


def set_explain(doc_id: int, question_id: int, content: str | None) -> bool:
    """Save the user's hand-written explanation for one question."""
    with db() as conn:
        cur = conn.execute(
            "UPDATE questions SET explain = ? WHERE id = ? AND document_id = ?",
            (content, question_id, doc_id),
        )
        return cur.rowcount > 0


def get_question(doc_id: int, question_id: int) -> dict | None:
    from app.db import one

    row = one(
        "SELECT * FROM questions WHERE id = ? AND document_id = ?", (question_id, doc_id)
    )
    return None if row is None else _question_dict(row)


def write_satmd(doc_id: int, text: str) -> Path:
    path = satmd_path(doc_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def read_satmd(doc_id: int) -> str:
    return satmd_path(doc_id).read_text(encoding="utf-8")


def write_assets(doc_id: int, assets: dict[str, bytes]) -> None:
    if not assets:
        return
    target = assets_dir(doc_id)
    target.mkdir(parents=True, exist_ok=True)
    for name, data in assets.items():
        (target / name).write_bytes(data)
