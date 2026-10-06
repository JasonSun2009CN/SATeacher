"""Built-in question banks shipped with the app (offline, 0 token).

Discovers `<bank>/manifest.json` + `<unit>/doc.sat.md` under `app/builtin/`,
built offline by `scripts/build_builtin.py`. Adding a unit reuses the regular
satmd import path (parse -> insert -> write_satmd -> write_assets) and is
idempotent via `documents.builtin_key`.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app import repos
from app.satmd.parser import SatMdError, parse

router = APIRouter(prefix="/api/builtin", tags=["builtin"])

BANKS_DIR = Path(__file__).resolve().parents[1] / "builtin"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ANSWER_STATUSES = {"inline", "external", "none"}


def _fail(message: str, status: int) -> None:
    raise HTTPException(status_code=status, detail=message)


def _load_manifest(bank_id: str) -> dict:
    if not _ID_RE.match(bank_id):
        _fail("bank not found", 404)
    path = BANKS_DIR / bank_id / "manifest.json"
    if not path.is_file():
        _fail("bank not found", 404)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _fail("bank manifest is unreadable", 500)
        raise                                          # pragma: no cover
    if not isinstance(manifest, dict) or not isinstance(manifest.get("units"), list):
        _fail("bank manifest is malformed", 500)
        raise                                          # pragma: no cover
    return manifest


@router.get("")
def list_banks() -> list[dict]:
    """Every installed bank with per-unit "already in the library" status."""
    banks: list[dict] = []
    if BANKS_DIR.is_dir():
        for bank_dir in sorted(BANKS_DIR.iterdir()):
            manifest_path = bank_dir / "manifest.json"
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            units = [u for u in manifest.get("units", []) if isinstance(u, dict) and u.get("id")]
            banks.append(
                {
                    "id": manifest.get("id") or bank_dir.name,
                    "title": manifest.get("title") or bank_dir.name,
                    "source": manifest.get("source") or "",
                    "units": [
                        {
                            "id": u["id"],
                            "title": u.get("title") or u["id"],
                            "module": u.get("module"),
                            "questions": int(u.get("questions") or 0),
                            "assets": int(u.get("assets") or 0),
                            "added": False,
                            "document_id": None,
                        }
                        for u in units
                    ],
                }
            )

    keys = [f"{b['id']}/{u['id']}" for b in banks for u in b["units"]]
    existing = repos.documents.get_builtin_keys(keys)
    for bank in banks:
        for unit in bank["units"]:
            doc_id = existing.get(f"{bank['id']}/{unit['id']}")
            if doc_id is not None:
                unit["added"] = True
                unit["document_id"] = doc_id
    return banks


def _resolve_unit(bank_id: str, unit_id: str) -> tuple[dict, Path]:
    manifest = _load_manifest(bank_id)
    if not _ID_RE.match(unit_id):
        _fail("unit not found", 404)
    unit = next(
        (u for u in manifest["units"] if isinstance(u, dict) and u.get("id") == unit_id),
        None,
    )
    if unit is None:
        _fail("unit not found", 404)
        raise                                          # pragma: no cover
    unit_dir = BANKS_DIR / bank_id / unit_id
    if not (unit_dir / "doc.sat.md").is_file():
        _fail("unit files are missing from this installation", 404)
        raise                                          # pragma: no cover
    return unit, unit_dir


def _import_unit(bank_id: str, unit_id: str, unit: dict, unit_dir: Path) -> tuple[int, bool]:
    """Add one unit as a document; returns (document_id, created)."""
    key = f"{bank_id}/{unit_id}"
    existing = repos.documents.get_by_builtin_key(key)
    if existing is not None:
        return existing, False

    try:
        satmd = (unit_dir / "doc.sat.md").read_text(encoding="utf-8")
        assets: dict[str, bytes] = {}
        assets_path = unit_dir / "assets"
        if assets_path.is_dir():
            for p in sorted(assets_path.iterdir()):
                if p.is_file():
                    assets[p.name] = p.read_bytes()
    except OSError:
        _fail("unit files are unreadable", 500)
        raise                                          # pragma: no cover

    try:
        parsed = parse(satmd)
    except SatMdError as exc:
        _fail(f"built-in unit is invalid (line {exc.line}): {exc.message}", 500)
        raise                                          # pragma: no cover

    status = parsed.meta.get("answers", "none")
    if status not in ANSWER_STATUSES:
        status = "none"
    title = parsed.meta.get("title") or unit.get("title") or unit_id

    try:
        doc_id = repos.documents.create_document(
            title=title,
            source_filename=f"builtin:{key}",
            answers_status=status,
            question_count=len(parsed.questions),
            builtin_key=key,
        )
    except sqlite3.IntegrityError:
        # lost a race with a concurrent add — the other request owns the key
        winner = repos.documents.get_by_builtin_key(key)
        if winner is None:
            _fail("could not register the built-in unit", 500)
            raise                                      # pragma: no cover
        return winner, False

    repos.documents.set_satmd_path(doc_id)
    repos.documents.write_satmd(doc_id, satmd)
    repos.documents.write_assets(doc_id, assets)
    repos.documents.insert_questions(doc_id, parsed.questions)
    return doc_id, True


@router.post("/{bank_id}/units/{unit_id}")
def add_unit(bank_id: str, unit_id: str) -> dict:
    unit, unit_dir = _resolve_unit(bank_id, unit_id)
    doc_id, created = _import_unit(bank_id, unit_id, unit, unit_dir)
    return {"document_id": doc_id, "added": created}


@router.post("/{bank_id}/add-all")
def add_all(bank_id: str) -> dict:
    manifest = _load_manifest(bank_id)
    added = 0
    already = 0
    doc_ids: list[int] = []
    for unit in manifest["units"]:
        if not isinstance(unit, dict) or not unit.get("id"):
            continue
        unit_id = str(unit["id"])
        _, unit_dir = _resolve_unit(bank_id, unit_id)
        doc_id, created = _import_unit(bank_id, unit_id, unit, unit_dir)
        doc_ids.append(doc_id)
        added += int(created)
        already += int(not created)
    return {"added": added, "already": already, "document_ids": doc_ids}
