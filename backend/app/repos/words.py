"""Free-form vocabulary grid (Numbers/Excel-style) per document.

One grid per document. **v2** (batch 10) stores stable per-column/per-row ids,
per-column widths and a view (sort + filter) next to the cell text, so the
front-end can persist layout/preferences without losing data identity. Legacy
**v1** grids (``headers`` + array-of-arrays rows) are read and upgraded
transparently, so pre-existing databases keep working.
"""

from __future__ import annotations

import json
import uuid

from app.db import db, one

GRID_VERSION = 2

#: Default grid shown for a document that has no vocabulary yet.
DEFAULT_COLUMNS = [
    {"id": "c1", "name": "Word", "width": 180},
    {"id": "c2", "name": "Meaning", "width": 260},
    {"id": "c3", "name": "Notes", "width": 220},
]

DEFAULT_WIDTH = 180
MIN_WIDTH = 60
MAX_WIDTH = 800
MAX_HEADERS = 12
MAX_ROWS = 500
MAX_CELL = 2000
MAX_NAME = 200


class GridError(ValueError):
    """Invalid grid payload (columns/rows out of bounds or malformed)."""


def default_grid() -> dict:
    """A fresh, empty v2 grid (deep copy of the defaults)."""
    return {
        "version": GRID_VERSION,
        "columns": [dict(c) for c in DEFAULT_COLUMNS],
        "rows": [],
        "view": {"sort": None, "filter": {}},
    }


def get_grid(doc_id: int) -> dict:
    row = one(
        "SELECT headers, rows_json, columns_json, view_json, version"
        " FROM word_grids WHERE document_id = ?",
        (doc_id,),
    )
    if row is None:
        return default_grid()
    if (row["version"] or 1) >= GRID_VERSION and row["columns_json"]:
        return {
            "version": GRID_VERSION,
            "columns": _loads(row["columns_json"], []),
            "rows": _loads(row["rows_json"], []),
            "view": _loads(row["view_json"], {"sort": None, "filter": {}}),
        }
    return _upgrade_v1(_loads(row["headers"], []), _loads(row["rows_json"], []))


def save_grid(doc_id: int, payload: dict) -> dict:
    """Validate + normalise a v2 (or legacy v1) payload and store it."""
    if not isinstance(payload, dict):
        raise GridError("grid payload must be an object")

    if payload.get("columns") is not None:
        columns = _normalize_columns(payload["columns"])
    elif payload.get("headers") is not None:          # legacy v1 body
        columns = _normalize_columns(payload["headers"])
    else:
        columns = [dict(c) for c in DEFAULT_COLUMNS]

    rows = _normalize_rows(payload.get("rows"), columns)
    view = _normalize_view(payload.get("view"), columns)
    grid = {"version": GRID_VERSION, "columns": columns, "rows": rows, "view": view}

    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO word_grids"
            " (document_id, headers, rows_json, columns_json, view_json, version)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                doc_id,
                json.dumps([c["name"] for c in columns], ensure_ascii=False),
                json.dumps(rows, ensure_ascii=False),
                json.dumps(columns, ensure_ascii=False),
                json.dumps(view, ensure_ascii=False),
                GRID_VERSION,
            ),
        )
    return grid


# --------------------------------------------------------------------------
# normalisation
# --------------------------------------------------------------------------


def _normalize_columns(raw: object) -> list[dict]:
    if not isinstance(raw, list) or not (1 <= len(raw) <= MAX_HEADERS):
        raise GridError(f"columns must be 1-{MAX_HEADERS} columns")

    out: list[dict] = []
    used: set[str] = set()
    for i, item in enumerate(raw):
        if isinstance(item, str):                     # tolerate "Name" shorthand
            item = {"name": item}
        if not isinstance(item, dict):
            raise GridError(f"column {i + 1} must be an object")

        name = _cell(item.get("name"), f"column {i + 1} name")
        if not name:
            raise GridError(f"column {i + 1} name must not be empty")
        if len(name) > MAX_NAME:
            raise GridError(f"column {i + 1} name is too long")

        cid = item.get("id")
        cid = cid.strip() if isinstance(cid, str) else ""
        if not cid or cid in used:
            cid = _next_id("c", i + 1, used)
        used.add(cid)
        out.append({"id": cid, "name": name, "width": _clamp_width(item.get("width"))})
    return out


def _normalize_rows(raw: object, columns: list[dict]) -> list[dict]:
    if raw is None:
        raw = []
    if not isinstance(raw, list) or len(raw) > MAX_ROWS:
        raise GridError(f"rows must be at most {MAX_ROWS}")

    col_ids = [c["id"] for c in columns]
    out: list[dict] = []
    used: set[str] = set()
    for r, row in enumerate(raw):
        if isinstance(row, list):                     # tolerate array rows (v1)
            src: object = {col_ids[i]: row[i] for i in range(min(len(row), len(col_ids)))}
            rid = None
        elif isinstance(row, dict):
            src = row.get("cells")
            rid = row.get("id")
        else:
            raise GridError(f"row {r + 1} must be an object")
        if src is None:
            src = {}
        if not isinstance(src, dict):
            raise GridError(f"row {r + 1} cells must be an object")

        cells: dict[str, str] = {}
        for cid in col_ids:
            cells[cid] = _cell(src.get(cid), f"row {r + 1}")

        rid = rid.strip() if isinstance(rid, str) else ""
        if not rid or rid in used:
            rid = _next_id("r", r + 1, used)
        used.add(rid)
        out.append({"id": rid, "cells": cells})
    return out


def _normalize_view(raw: object, columns: list[dict]) -> dict:
    col_ids = {c["id"] for c in columns}
    if not isinstance(raw, dict):
        return {"sort": None, "filter": {}}

    sort = raw.get("sort")
    if not (
        isinstance(sort, dict)
        and sort.get("columnId") in col_ids
        and sort.get("direction") in ("asc", "desc")
    ):
        sort = None

    filt: dict[str, str] = {}
    raw_filter = raw.get("filter")
    if isinstance(raw_filter, dict):
        for key, value in raw_filter.items():
            if key in col_ids and isinstance(value, str) and value.strip():
                filt[key] = value.strip()

    return {"sort": sort, "filter": filt}


def _upgrade_v1(headers: object, rows: object) -> dict:
    names = [h for h in headers if isinstance(h, str)] if isinstance(headers, list) else []
    if not (1 <= len(names) <= MAX_HEADERS):
        names = [c["name"] for c in DEFAULT_COLUMNS]
    columns = [
        {"id": f"c{i + 1}", "name": name or f"Column {i + 1}", "width": DEFAULT_WIDTH}
        for i, name in enumerate(names)
    ]
    col_ids = [c["id"] for c in columns]

    out_rows: list[dict] = []
    if isinstance(rows, list):
        for r, row in enumerate(rows):
            if not isinstance(row, list):
                continue
            cells = {
                cid: (row[i].strip() if i < len(row) and isinstance(row[i], str) else "")
                for i, cid in enumerate(col_ids)
            }
            out_rows.append({"id": f"r{r + 1}", "cells": cells})

    return {
        "version": GRID_VERSION,
        "columns": columns,
        "rows": out_rows,
        "view": {"sort": None, "filter": {}},
    }


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _clamp_width(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return DEFAULT_WIDTH
    return max(MIN_WIDTH, min(MAX_WIDTH, int(value)))


def _cell(value: object, what: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise GridError(f"{what} must be text")
    text = value.strip()
    if len(text) > MAX_CELL:
        raise GridError(f"{what} is longer than {MAX_CELL} characters")
    return text


def _next_id(prefix: str, index: int, used: set[str]) -> str:
    """Prefer the deterministic ``c3``/``r7`` form, fall back to a random id."""
    candidate = f"{prefix}{index}"
    if candidate not in used:
        return candidate
    return _gen_id(prefix, used)


def _gen_id(prefix: str, used: set[str]) -> str:
    while True:
        candidate = f"{prefix}{uuid.uuid4().hex[:8]}"
        if candidate not in used:
            used.add(candidate)
            return candidate


def _loads(value: object, default: object) -> object:
    if not value:
        return default
    try:
        return json.loads(value)                       # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default