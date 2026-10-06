"""Built-in question bank API (batch 5B): discovery, add, idempotency."""

from __future__ import annotations

import json
import uuid

import pytest

from tests.conftest import MINI_SATMD


def _make_bank(root, units: dict[str, str]) -> str:
    """Materialise a tiny bank (manifest + units + assets) under `root`."""
    bank_id = f"bank-{uuid.uuid4().hex[:8]}"
    bank_dir = root / bank_id
    entries = []
    for unit_id, title in units.items():
        unit_dir = bank_dir / unit_id
        unit_dir.mkdir(parents=True)
        (unit_dir / "doc.sat.md").write_text(
            MINI_SATMD.replace('title: "Mini Bank"', f'title: "{title}"'),
            encoding="utf-8",
        )
        (unit_dir / "assets").mkdir()
        (unit_dir / "assets" / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\n fake")
        entries.append(
            {"id": unit_id, "title": title, "module": 1, "questions": 2, "assets": 1}
        )
    (bank_dir / "manifest.json").write_text(
        json.dumps(
            {"id": bank_id, "title": "Mini bank", "source": "mini.md", "units": entries},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return bank_id


@pytest.fixture()
def bank_factory(tmp_path, monkeypatch):
    """Point the builtin router at a temp banks dir; clean up added docs."""
    from app.api import builtin as builtin_api

    monkeypatch.setattr(builtin_api, "BANKS_DIR", tmp_path)
    created_banks: list[str] = []

    def make(units: dict[str, str]) -> str:
        bank_id = _make_bank(tmp_path, units)
        created_banks.append(bank_id)
        return bank_id

    yield make

    from app import repos
    from app.db import query

    for bank_id in created_banks:
        for row in query(
            "SELECT id FROM documents WHERE builtin_key LIKE ?", (f"{bank_id}/%",)
        ):
            repos.documents.delete_document(row["id"])


def test_list_banks_empty_dir(client, tmp_path, monkeypatch):
    from app.api import builtin as builtin_api

    monkeypatch.setattr(builtin_api, "BANKS_DIR", tmp_path / "does-not-exist")
    assert client.get("/api/builtin").json() == []


def test_list_and_add_single_unit(client, bank_factory):
    bank_id = bank_factory({"2501-us-routing-a": "25年1月北美 · Routing A"})

    body = client.get("/api/builtin").json()
    assert len(body) == 1
    bank = body[0]
    assert bank["id"] == bank_id
    unit = bank["units"][0]
    assert unit["title"] == "25年1月北美 · Routing A"
    assert unit["questions"] == 2
    assert unit["added"] is False and unit["document_id"] is None

    res = client.post(f"/api/builtin/{bank_id}/units/2501-us-routing-a")
    assert res.status_code == 200
    doc_id = res.json()["document_id"]
    assert res.json()["added"] is True

    doc = client.get(f"/api/documents/{doc_id}").json()
    assert doc["title"] == "25年1月北美 · Routing A"
    assert doc["question_count"] == 2
    assert doc["source_filename"] == f"builtin:{bank_id}/2501-us-routing-a"

    from app.db import assets_dir

    assert (assets_dir(doc_id) / "pic.png").is_file()

    unit = client.get("/api/builtin").json()[0]["units"][0]
    assert unit["added"] is True and unit["document_id"] == doc_id


def test_add_is_idempotent(client, bank_factory):
    bank_id = bank_factory({"u1": "Unit One"})

    first = client.post(f"/api/builtin/{bank_id}/units/u1").json()
    second = client.post(f"/api/builtin/{bank_id}/units/u1").json()
    assert first["added"] is True
    assert second["added"] is False
    assert second["document_id"] == first["document_id"]

    from app.db import query

    rows = query("SELECT id FROM documents WHERE builtin_key = ?", (f"{bank_id}/u1",))
    assert len(rows) == 1


def test_add_all_counts_added_and_already(client, bank_factory):
    bank_id = bank_factory({"u1": "Unit One", "u2": "Unit Two"})

    first = client.post(f"/api/builtin/{bank_id}/add-all")
    assert first.status_code == 200
    body = first.json()
    assert body["added"] == 2 and body["already"] == 0
    assert len(body["document_ids"]) == 2

    again = client.post(f"/api/builtin/{bank_id}/add-all").json()
    assert again["added"] == 0 and again["already"] == 2
    assert sorted(again["document_ids"]) == sorted(body["document_ids"])


def test_unknown_bank_and_unit_404(client, bank_factory):
    bank_id = bank_factory({"u1": "Unit One"})

    assert client.post("/api/builtin/no-such-bank/units/u1").status_code == 404
    assert client.post(f"/api/builtin/{bank_id}/units/nope").status_code == 404
    assert client.post(f"/api/builtin/{bank_id}/add-all/../u1").status_code in (404, 405)
    # path-traversal-ish ids are rejected by the id allowlist
    assert client.post(f"/api/builtin/{bank_id}/units/bad id").status_code == 404


def test_shipped_bank_is_complete(client):
    """Guards the offline build: 44 units, 1186 questions, answers included."""
    banks = client.get("/api/builtin").json()
    bank = next((b for b in banks if b["id"] == "sat2025-rw-b"), None)
    if bank is None:
        pytest.skip("shipped bank not built")
    assert len(bank["units"]) == 44
    assert sum(u["questions"] for u in bank["units"]) == 1186
    # the one known-incomplete source module still ships (25 questions)
    short = [u for u in bank["units"] if u["questions"] != 27]
    assert [u["id"] for u in short] == ["2512-apac-harder-a"]
    assert all(u["added"] is False for u in bank["units"])
