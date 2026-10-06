"""Key-value settings persistence (LLM API configuration, PLAN.md §6)."""

from __future__ import annotations

from app.db import db

ALLOWED_KEYS = ("provider", "base_url", "api_key", "model")


def get_all() -> dict[str, str]:
    with db() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def set_values(values: dict[str, str]) -> None:
    with db() as conn:
        for key, value in values.items():
            if key not in ALLOWED_KEYS:
                continue
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
