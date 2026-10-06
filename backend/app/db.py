"""SQLite access layer: single-file DB under ./data (see PLAN.md §5)."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("SATEACHER_DATA", REPO_ROOT / "data"))
DB_PATH = DATA_DIR / "app.db"
DOCS_DIR = DATA_DIR / "docs"          # docs/<doc_id>/doc.sat.md + assets/
UPLOAD_TMP = DATA_DIR / "tmp"         # transient upload staging
EXPORTS_DIR = DATA_DIR / "exports"


def doc_dir(doc_id: int) -> Path:
    return DOCS_DIR / str(doc_id)


def satmd_path(doc_id: int) -> Path:
    return doc_dir(doc_id) / "doc.sat.md"


def assets_dir(doc_id: int) -> Path:
    return doc_dir(doc_id) / "assets"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  title           TEXT NOT NULL,
  source_filename TEXT NOT NULL,
  satmd_path      TEXT NOT NULL,
  answers_status  TEXT NOT NULL DEFAULT 'none',  -- inline|external|none|pending
  question_count  INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questions (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ext_id       TEXT NOT NULL,
  no           INTEGER,
  sec          TEXT NOT NULL CHECK (sec IN ('rw','math')),
  type         TEXT,
  difficulty   TEXT,
  material     TEXT,
  stem         TEXT NOT NULL,
  options_json TEXT NOT NULL,        -- ["A. ...", ...] exactly 4
  answer       TEXT CHECK (answer IS NULL OR answer IN ('A','B','C','D')),
  explain      TEXT,
  source_ref   TEXT,
  images_json  TEXT NOT NULL DEFAULT '[]',
  order_idx    INTEGER NOT NULL,
  UNIQUE (document_id, ext_id)
);

CREATE TABLE IF NOT EXISTS sessions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  started_at  TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT,
  mode        TEXT NOT NULL DEFAULT 'all'   -- all|range
);

CREATE TABLE IF NOT EXISTS session_items (
  session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  question_id  INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  no           INTEGER NOT NULL,
  chosen       TEXT,
  is_correct   INTEGER,
  answered_at  TEXT,
  PRIMARY KEY (session_id, question_id)
);

CREATE TABLE IF NOT EXISTS analyses (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  session_id  INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
  content     TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vocab (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  word         TEXT NOT NULL,
  context      TEXT,
  document_id  INTEGER REFERENCES documents(id) ON DELETE SET NULL,
  question_id  INTEGER REFERENCES questions(id) ON DELETE SET NULL,
  meaning      TEXT,
  ease         REAL NOT NULL DEFAULT 2.5,
  interval     INTEGER NOT NULL DEFAULT 0,
  due_at       TEXT NOT NULL DEFAULT (datetime('now')),
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
  question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
  content     TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS word_grids (
  document_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  headers     TEXT NOT NULL DEFAULT '["Word","Meaning","Notes"]',
  rows_json   TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_logs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  purpose     TEXT NOT NULL,
  provider    TEXT NOT NULL,
  model       TEXT NOT NULL,
  tokens_in   INTEGER,
  tokens_out  INTEGER,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def ensure_dirs() -> None:
    for d in (DATA_DIR, DOCS_DIR, UPLOAD_TMP, EXPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    """One connection per unit of work; commits on success, rolls back on error."""
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(sql, params).fetchall()


def one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    """Run a write; returns lastrowid."""
    with db() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid or 0
