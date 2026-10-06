"""Document import, listing, answer-key entry and asset serving."""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app import repos
from app.convert.pdf import ConvertError, convert_pdf
from app.db import UPLOAD_TMP, assets_dir
from app.repos import words as words_repo
from app.satmd.parser import SatMdError, parse, set_answer
from app.repos import sessions as session_repo

router = APIRouter(prefix="/api/documents", tags=["documents"])

ASSET_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ANSWER_STATUSES = {"inline", "external", "none"}
MAX_UPLOAD = 60 * 1024 * 1024            # 60 MB
EXPORT_FORMATS = {"md", "csv", "json"}
_OPT_PREFIX_RE = re.compile(r"^[A-D][.)]\s*")

MEDIA_TYPES = {
    "md": "text/markdown; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "json": "application/json; charset=utf-8",
}


class AnswersPayload(BaseModel):
    answers: dict[str, str]


class ExplainPayload(BaseModel):
    content: str = ""


class WordsPayload(BaseModel):
    headers: list[str]
    rows: list[list[str]]


def _fail(message: str, status: int = 422) -> None:
    raise HTTPException(status_code=status, detail=message)


def _convert_pdf_upload(filename: str, data: bytes):
    UPLOAD_TMP.mkdir(parents=True, exist_ok=True)
    staged = UPLOAD_TMP / f"{uuid.uuid4().hex}-{Path(filename).name}"
    try:
        staged.write_bytes(data)
        return convert_pdf(staged, title=Path(filename).stem)
    except ConvertError as exc:
        _fail(str(exc))
    finally:
        staged.unlink(missing_ok=True)


def _convert_markdown_upload(filename: str, data: bytes):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        _fail("the file is not valid UTF-8 text", 400)
    warnings: list[str] = []
    try:
        parsed = parse(text)
    except SatMdError as exc:
        _fail(f"line {exc.line}: {exc.message}")
        raise                                          # pragma: no cover
    status = parsed.meta.get("answers", "none")
    if status not in ANSWER_STATUSES:
        status = "none"
    refs = [img for q in parsed.questions for img in q.images]
    if refs:
        warnings.append(
            f"{len(refs)} image reference(s) kept — upload the assets folder to serve them"
        )
    return text, warnings, status, parsed


@router.post("")
async def import_document(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    if not data:
        _fail("the uploaded file is empty", 400)
    if len(data) > MAX_UPLOAD:
        _fail("the file is larger than 60 MB", 413)
    filename = Path(file.filename or "upload").name
    lower = filename.lower()

    if lower.endswith(".pdf"):
        converted = _convert_pdf_upload(filename, data)
        satmd, warnings, status = converted.satmd, converted.warnings, converted.answers_status
        assets = converted.assets
    elif lower.endswith((".md", ".markdown", ".sat.md")):
        satmd, warnings, status, _ = _convert_markdown_upload(filename, data)
        assets = {}
    else:
        _fail("unsupported file type — upload a PDF or a .sat.md file", 415)
        raise                                          # pragma: no cover

    try:
        parsed = parse(satmd)
    except SatMdError as exc:                          # pragma: no cover - converter self-checks
        _fail(f"line {exc.line}: {exc.message}")
        raise

    title = parsed.meta.get("title") or Path(filename).stem
    doc_id = repos.documents.create_document(
        title=title,
        source_filename=filename,
        answers_status=status,
        question_count=len(parsed.questions),
    )
    repos.documents.set_satmd_path(doc_id)
    repos.documents.write_satmd(doc_id, satmd)
    repos.documents.write_assets(doc_id, assets)
    repos.documents.insert_questions(doc_id, parsed.questions)

    detail = repos.documents.get_document(doc_id)
    return {**detail, "warnings": warnings}


@router.get("")
def list_documents() -> list[dict]:
    return repos.documents.list_documents()


@router.get("/{doc_id}")
def get_document(doc_id: int) -> dict:
    doc = repos.documents.get_document(doc_id)
    if doc is None:
        _fail("document not found", 404)
        raise                                          # pragma: no cover
    return doc


@router.get("/{doc_id}/questions")
def document_questions(doc_id: int) -> list[dict]:
    if repos.documents.get_document(doc_id) is None:
        _fail("document not found", 404)
        raise                                          # pragma: no cover
    return repos.documents.list_questions(doc_id)


@router.get("/{doc_id}/history")
def document_history(doc_id: int) -> list[dict]:
    return session_repo.history(doc_id)


@router.put("/{doc_id}/answers")
def put_answers(doc_id: int, payload: AnswersPayload) -> dict:
    doc = repos.documents.get_document(doc_id)
    if doc is None:
        _fail("document not found", 404)
        raise                                          # pragma: no cover

    cleaned: dict[str, str] = {}
    for ext_id, letter in payload.answers.items():
        letter = (letter or "").strip().upper()
        if letter not in {"A", "B", "C", "D"}:
            _fail(f"invalid answer {letter!r} for {ext_id} (expected A-D)", 400)
        cleaned[ext_id] = letter
    if not cleaned:
        _fail("no answers supplied", 400)

    changed = repos.documents.set_answers(doc_id, cleaned)
    if changed == 0:
        _fail("no matching questions", 404)

    # keep the on-disk SAT-MD in sync (source of truth for export/debug)
    try:
        text = repos.documents.read_satmd(doc_id)
        for ext_id, letter in cleaned.items():
            text = set_answer(text, ext_id, letter)
        text = re.sub(r"(?m)^answers:\s*\S+\s*$", "answers: external", text, count=1)
        repos.documents.write_satmd(doc_id, text)
    except (KeyError, OSError):
        pass                                            # DB already updated

    return repos.documents.get_document(doc_id)


@router.put("/{doc_id}/questions/{question_id}/explain")
def put_explain(doc_id: int, question_id: int, payload: ExplainPayload) -> dict:
    """Hand-written explanation — saved straight to the DB (0 token)."""
    if repos.documents.get_document(doc_id) is None:
        _fail("document not found", 404)
        raise                                          # pragma: no cover
    content = payload.content.strip() or None
    if not repos.documents.set_explain(doc_id, question_id, content):
        _fail("question not found", 404)
        raise                                          # pragma: no cover
    return {"question_id": question_id, "explain": content}


@router.get("/{doc_id}/words")
def get_words(doc_id: int) -> dict:
    if repos.documents.get_document(doc_id) is None:
        _fail("document not found", 404)
        raise                                          # pragma: no cover
    return words_repo.get_grid(doc_id)


@router.put("/{doc_id}/words")
def put_words(doc_id: int, payload: WordsPayload) -> dict:
    if repos.documents.get_document(doc_id) is None:
        _fail("document not found", 404)
        raise                                          # pragma: no cover
    try:
        return words_repo.save_grid(doc_id, payload.headers, payload.rows)
    except words_repo.GridError as exc:
        _fail(str(exc), 400)
        raise                                          # pragma: no cover


@router.get("/{doc_id}/words/export")
def export_words(doc_id: int) -> Response:
    """Vocabulary grid as .xlsx (openpyxl; Numbers opens it too)."""
    doc = repos.documents.get_document(doc_id)
    if doc is None:
        _fail("document not found", 404)
        raise                                          # pragma: no cover

    from openpyxl import Workbook
    from openpyxl.styles import Font

    grid = words_repo.get_grid(doc_id)
    wb = Workbook()
    ws = wb.active
    ws.title = "Vocabulary"
    ws.append(grid["headers"])
    for row in grid["rows"]:
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    buf = BytesIO()
    wb.save(buf)

    filename = f"{_slugify(doc['title'])}-vocabulary.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _slugify(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-.")[:60]
    return slug or "document"


def _option_map(options: list[str]) -> dict[str, str]:
    """Map option letters to their text: {'A': 'one', ...}."""
    out: dict[str, str] = {}
    for i, opt in enumerate(options or []):
        text = (opt or "").strip()
        m = re.match(r"^([A-D])[.)]\s*([\s\S]*)$", text)
        letter = m.group(1) if m else ("ABCD"[i] if i < 4 else "?")
        out[letter] = (m.group(2) if m else text).strip()
    return out


def _export_rows(doc_id: int) -> list[dict]:
    rows: list[dict] = []
    for i, q in enumerate(repos.documents.list_questions(doc_id), start=1):
        rows.append(
            {
                "no": q["no"] if q["no"] is not None else i,
                "sec": q["sec"],
                "source": q["source"],
                "material": q["material"],
                "stem": q["stem"],
                "options": _option_map(q["options"]),
                "answer": q["answer"],
                "explain": q["explain"],
            }
        )
    return rows


def _export_md(doc: dict, rows: list[dict]) -> str:
    lines = [f"# {doc['title']}", "", f"Source: {doc['source_filename']}", ""]
    for idx, r in enumerate(rows):
        sec = "Reading & Writing" if r["sec"] == "rw" else "Math"
        head = f"## Question {r['no']} · {sec}"
        if r["source"]:
            head += f" · {r['source']}"
        lines += [head, ""]
        if r["material"]:
            lines += [r["material"], ""]
        lines += [r["stem"], ""]
        for letter in "ABCD":
            if letter in r["options"]:
                lines.append(f"- {letter}. {r['options'][letter]}")
        lines.append("")
        if r["answer"]:
            lines += [f"**Answer:** {r['answer']}", ""]
        if r["explain"]:
            lines += ["**Explanation:**", "", r["explain"], ""]
        if idx < len(rows) - 1:
            lines += ["---", ""]
    return "\n".join(lines).rstrip() + "\n"


def _export_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["no", "sec", "source", "material", "stem", "A", "B", "C", "D", "answer", "explain"]
    )
    for r in rows:
        opts = r["options"]
        writer.writerow(
            [
                r["no"],
                r["sec"],
                r["source"] or "",
                r["material"] or "",
                r["stem"],
                opts.get("A", ""),
                opts.get("B", ""),
                opts.get("C", ""),
                opts.get("D", ""),
                r["answer"] or "",
                r["explain"] or "",
            ]
        )
    return buf.getvalue()


@router.get("/{doc_id}/export/{fmt}")
def export_document(doc_id: int, fmt: str) -> Response:
    """Export questions + answers + hand-written explanations (0 token)."""
    doc = repos.documents.get_document(doc_id)
    if doc is None:
        _fail("document not found", 404)
        raise                                          # pragma: no cover
    if fmt not in EXPORT_FORMATS:
        _fail("format must be md, csv or json", 400)
        raise                                          # pragma: no cover

    rows = _export_rows(doc_id)
    if fmt == "json":
        content = json.dumps(
            {
                "title": doc["title"],
                "source": doc["source_filename"],
                "questions": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    elif fmt == "csv":
        content = _export_csv(rows)
    else:
        content = _export_md(doc, rows)

    return Response(
        content=content,
        media_type=MEDIA_TYPES[fmt],
        headers={
            "Content-Disposition": f'attachment; filename="{_slugify(doc["title"])}.{fmt}"'
        },
    )


@router.delete("/{doc_id}")
def delete_document(doc_id: int) -> dict:
    if not repos.documents.delete_document(doc_id):
        _fail("document not found", 404)
        raise                                          # pragma: no cover
    return {"deleted": doc_id}


@router.get("/{doc_id}/assets/{name}")
def document_asset(doc_id: int, name: str) -> FileResponse:
    if not ASSET_NAME_RE.match(name) or ".." in name:
        _fail("invalid asset name", 400)
        raise                                          # pragma: no cover
    path = assets_dir(doc_id) / name
    if not path.is_file():
        _fail("asset not found", 404)
        raise                                          # pragma: no cover
    media = "image/png" if name.lower().endswith(".png") else "application/octet-stream"
    return FileResponse(path, media_type=media)
