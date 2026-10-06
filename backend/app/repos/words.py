"""Free-form vocabulary grid (Numbers/Excel-style) per document.

One grid per document: default headers Word | Meaning | Notes, rows and
columns are user-editable; exported to .xlsx (PLAN.md §3 — batch 3).
"""

from __future__ import annotations

import json

from app.db import db, one

DEFAULT_HEADERS = ["Word", "Meaning", "Notes"]
MAX_HEADERS = 12
MAX_ROWS = 500
MAX_CELL = 2000


class GridError(ValueError):
    """Invalid grid payload (headers/rows out of bounds or malformed)."""


def get_grid(doc_id: int) -> dict:
    row = one("SELECT headers, rows_json FROM word_grids WHERE document_id = ?", (doc_id,))
    if row is None:
        return {"headers": list(DEFAULT_HEADERS), "rows": []}
    return {
        "headers": json.loads(row["headers"]),
        "rows": json.loads(row["rows_json"]),
    }


def save_grid(doc_id: int, headers: list, rows: list) -> dict:
    """Validate and store the grid; returns the normalized grid."""
    if not isinstance(headers, list) or not (1 <= len(headers) <= MAX_HEADERS):
        raise GridError(f"headers must be 1-{MAX_HEADERS} columns")
    clean_headers = [_cell(h, f"header {i + 1}") for i, h in enumerate(headers)]
    if any(not h for h in clean_headers):
        raise GridError("headers must not be empty")

    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise GridError(f"rows must be at most {MAX_ROWS}")
    width = len(clean_headers)
    clean_rows: list[list[str]] = []
    for r, row in enumerate(rows):
        if not isinstance(row, list):
            raise GridError(f"row {r + 1} must be a list")
        cells = [_cell(row[c] if c < len(row) else "", f"row {r + 1}") for c in range(width)]
        clean_rows.append(cells)

    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO word_grids (document_id, headers, rows_json)"
            " VALUES (?, ?, ?)",
            (doc_id, json.dumps(clean_headers, ensure_ascii=False),
             json.dumps(clean_rows, ensure_ascii=False)),
        )
    return {"headers": clean_headers, "rows": clean_rows}


def _cell(value: object, what: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise GridError(f"{what} must be text")
    if len(value) > MAX_CELL:
        raise GridError(f"{what} is longer than {MAX_CELL} characters")
    return value.strip()
