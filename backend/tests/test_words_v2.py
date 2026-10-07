"""Vocabulary grid v2 (batch 10): ids, widths, view + v1 upgrade."""

from __future__ import annotations

from app.db import db
from app.repos import words as words_repo
from tests.conftest import MINI_SATMD, upload


def _doc(client) -> int:
    resp = upload(client, "mini.sat.md", MINI_SATMD)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _seed_v1(doc_id: int, headers: str, rows: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO word_grids (document_id, headers, rows_json, version)"
            " VALUES (?, ?, ?, 1)",
            (doc_id, headers, rows),
        )


def test_upgrade_v1_rows_preserve_data_and_gain_ids(client) -> None:
    doc_id = _doc(client)
    _seed_v1(doc_id, '["Word","Meaning","Notes"]', '[["elate","make happy","verb"],["cadence","rhythm"]]')

    grid = words_repo.get_grid(doc_id)

    assert grid["version"] == 2
    assert [c["name"] for c in grid["columns"]] == ["Word", "Meaning", "Notes"]
    assert [c["id"] for c in grid["columns"]] == ["c1", "c2", "c3"]
    assert [r["id"] for r in grid["rows"]] == ["r1", "r2"]
    assert grid["rows"][0]["cells"] == {"c1": "elate", "c2": "make happy", "c3": "verb"}
    # short legacy rows are padded with empty cells
    assert grid["rows"][1]["cells"] == {"c1": "cadence", "c2": "rhythm", "c3": ""}
    assert grid["view"] == {"sort": None, "filter": {}}


def test_v1_to_v2_roundtrip_via_api_is_lossless(client) -> None:
    doc_id = _doc(client)
    _seed_v1(
        doc_id,
        '["Word","Meaning","Notes"]',
        '[["elate","make happy","verb"],["cadence","rhythm","noun"]]',
    )

    upgraded = client.get(f"/api/documents/{doc_id}/words").json()
    assert words_repo.GRID_VERSION == 2 == upgraded["version"]

    # persist the upgraded grid, then read it back: data is unchanged
    saved = client.put(f"/api/documents/{doc_id}/words", json=upgraded)
    assert saved.status_code == 200, saved.text
    again = client.get(f"/api/documents/{doc_id}/words").json()
    assert [c["name"] for c in again["columns"]] == ["Word", "Meaning", "Notes"]
    assert [r["cells"]["c1"] for r in again["rows"]] == ["elate", "cadence"]
    assert again["rows"][0]["cells"] == {"c1": "elate", "c2": "make happy", "c3": "verb"}


def test_view_validation(client) -> None:
    doc_id = _doc(client)
    saved = client.put(
        f"/api/documents/{doc_id}/words",
        json={
            "columns": [{"id": "c1", "name": "Word", "width": 300}],
            "rows": [{"id": "r1", "cells": {"c1": "alpha"}}],
            "view": {
                "sort": {"columnId": "c1", "direction": "asc"},
                "filter": {"c1": "a", "nope": "dropped"},
            },
        },
    ).json()
    assert saved["view"] == {"sort": {"columnId": "c1", "direction": "asc"}, "filter": {"c1": "a"}}

    # an unknown sort column / bad direction is dropped, not rejected
    bad = client.put(
        f"/api/documents/{doc_id}/words",
        json={"columns": [{"name": "Word"}], "rows": [], "view": {"sort": {"columnId": "zzz", "direction": "up"}}},
    ).json()
    assert bad["view"] == {"sort": None, "filter": {}}


def test_missing_and_duplicate_ids_are_regenerated(client) -> None:
    doc_id = _doc(client)
    saved = client.put(
        f"/api/documents/{doc_id}/words",
        json={
            "columns": [{"id": "x", "name": "A"}, {"id": "x", "name": "B"}],
            "rows": [{"id": "y", "cells": {"x": "1"}}, {"id": "y", "cells": {"x": "2"}}],
        },
    ).json()

    col_ids = [c["id"] for c in saved["columns"]]
    assert len(set(col_ids)) == 2 and col_ids[0] == "x"      # first kept, dup regenerated
    row_ids = [r["id"] for r in saved["rows"]]
    assert len(set(row_ids)) == 2 and row_ids[0] == "y"
    # cells are keyed by the canonical column ids
    assert saved["rows"][0]["cells"][col_ids[0]] == "1"
    assert saved["rows"][0]["cells"][col_ids[1]] == ""


def test_widths_are_clamped(client) -> None:
    doc_id = _doc(client)
    saved = client.put(
        f"/api/documents/{doc_id}/words",
        json={
            "columns": [{"name": "A", "width": 5}, {"name": "B", "width": 9999}],
            "rows": [],
        },
    ).json()
    assert saved["columns"][0]["width"] == words_repo.MIN_WIDTH
    assert saved["columns"][1]["width"] == words_repo.MAX_WIDTH


def test_legacy_v1_body_still_accepted(client) -> None:
    """A v1 ``{headers, rows}`` PUT is upgraded rather than rejected."""
    doc_id = _doc(client)
    saved = client.put(
        f"/api/documents/{doc_id}/words",
        json={"headers": ["Word", "Meaning"], "rows": [["elate", "make happy"]]},
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert [c["name"] for c in body["columns"]] == ["Word", "Meaning"]
    assert body["rows"][0]["cells"]["c1"] == "elate"