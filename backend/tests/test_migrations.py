"""DB migration: older databases gain the new columns/tables in place."""

from __future__ import annotations

import sqlite3

from app.db import SCHEMA, _migrate


def test_migrate_adds_missing_document_columns() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, title TEXT)")
    conn.execute("INSERT INTO documents (id, title) VALUES (1, 'old row')")

    _migrate(conn)

    cols = {row["name"] for row in conn.execute("PRAGMA table_info(documents)")}
    assert {"builtin_key", "import_source", "used_ai", "report_json"} <= cols
    row = conn.execute("SELECT * FROM documents WHERE id = 1").fetchone()
    assert row["title"] == "old row"                 # data preserved
    assert row["used_ai"] == 0                        # default backfilled
    conn.close()


def test_migrate_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE documents (id INTEGER PRIMARY KEY, title TEXT)")
    _migrate(conn)
    _migrate(conn)
    assert True
    _migrate(conn)                                    # must not raise
    conn.close()


def test_schema_creates_import_jobs() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert "import_jobs" in tables
    cols = {row[1] for row in conn.execute("PRAGMA table_info(import_jobs)")}
    assert {"id", "status", "stage", "pages_json", "warnings_json", "document_id"} <= cols
    conn.close()