"""Persistence for the staged import pipeline (`import_jobs` table)."""

from __future__ import annotations

import json
import uuid

from app.db import execute, one

JOB_ID_PREFIX = "j_"

# columns a caller may update, mapped to their SQL names
_UPDATABLE = {
    "status",
    "stage",
    "kind",
    "import_source",
    "pages_total",
    "pages_done",
    "question_count",
    "used_ai",
    "pages_json",
    "warnings_json",
    "document_id",
    "error",
}


def new_job_id() -> str:
    return f"{JOB_ID_PREFIX}{uuid.uuid4().hex}"


def create(filename: str) -> str:
    job_id = new_job_id()
    execute(
        "INSERT INTO import_jobs (id, filename, status, stage) VALUES (?, ?, 'detecting', 'detect')",
        (job_id, filename),
    )
    return job_id


def get(job_id: str) -> dict | None:
    row = one("SELECT * FROM import_jobs WHERE id = ?", (job_id,))
    if row is None:
        return None
    data = dict(row)
    data["pages"] = json.loads(data.pop("pages_json") or "[]")
    data["warnings"] = json.loads(data.pop("warnings_json") or "[]")
    data["used_ai"] = bool(data["used_ai"])
    return data


def update(job_id: str, **fields) -> None:
    unknown = set(fields) - _UPDATABLE
    if unknown:
        raise ValueError(f"unknown import_jobs column(s): {sorted(unknown)}")
    if not fields:
        return
    assignments = ", ".join(f"{name} = ?" for name in fields)
    execute(
        f"UPDATE import_jobs SET {assignments} WHERE id = ?",
        (*fields.values(), job_id),
    )


def delete(job_id: str) -> bool:
    row = one("SELECT id FROM import_jobs WHERE id = ?", (job_id,))
    if row is None:
        return False
    execute("DELETE FROM import_jobs WHERE id = ?", (job_id,))
    return True