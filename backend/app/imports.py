"""Import pipeline service: detect -> convert -> (review) -> commit.

Deterministic and 0-token: the LLM is never part of the main path. Both the
one-shot ``POST /api/documents`` endpoint and the staged ``/api/imports`` job
flow call :func:`convert_upload` / :func:`commit` so there is a single code
path for PDF, DOCX and SAT-MD imports.

The conversion result of a job is staged on disk under ``jobs/<job_id>/``
(``result.json`` + ``doc.sat.md`` + ``assets/``) so it survives between the
create/commit requests and after a process restart.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from app import repos
from app.convert.docx import convert_docx
from app.convert.pdf import ConvertError, convert_pdf
from app.db import UPLOAD_TMP, jobs_dir
from app.satmd.parser import SatMdError, parse

ANSWER_STATUSES = {"inline", "external", "none"}
MAX_UPLOAD = 60 * 1024 * 1024            # 60 MB

KINDS = ("pdf", "docx", "satmd")
# documents.import_source value per kind
IMPORT_SOURCES = {"pdf": "pdf", "docx": "docx", "satmd": "sat.md"}


class ImportProblem(Exception):
    """A user-facing import failure.

    ``status`` is the HTTP status the API layer should use. Validation
    problems (empty/too large/unsupported) fail fast; conversion problems are
    reported through the job so the import UI can render them.
    """

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


class ImportResult:
    """Everything needed to preview and commit one import."""

    def __init__(
        self,
        *,
        filename: str,
        kind: str,
        import_source: str,
        title: str,
        satmd: str,
        warnings: list[str],
        answers_status: str,
        pages: list,
        question_count: int,
        assets: dict[str, bytes] | None = None,
        used_ai: bool = False,
    ):
        self.filename = filename
        self.kind = kind
        self.import_source = import_source
        self.title = title
        self.satmd = satmd
        self.warnings = warnings
        self.answers_status = answers_status
        self.pages = pages
        self.question_count = question_count
        self.assets = assets or {}
        self.used_ai = used_ai


def detect_kind(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".docx"):
        return "docx"
    if lower.endswith((".md", ".markdown", ".sat.md")):
        return "satmd"
    raise ImportProblem(
        "unsupported file type — upload a PDF, DOCX, or .sat.md file", 415
    )


def validate_upload(filename: str, data: bytes) -> str:
    """Cheap checks before any conversion; returns the kind."""
    if not data:
        raise ImportProblem("the uploaded file is empty", 400)
    if len(data) > MAX_UPLOAD:
        raise ImportProblem("the file is larger than 60 MB", 413)
    return detect_kind(filename)


def _stage(filename: str, data: bytes) -> Path:
    UPLOAD_TMP.mkdir(parents=True, exist_ok=True)
    staged = UPLOAD_TMP / f"{uuid.uuid4().hex}-{Path(filename).name}"
    staged.write_bytes(data)
    return staged


def pages_to_json(pages: list) -> list[dict]:
    out: list[dict] = []
    for page in pages:
        if isinstance(page, dict):
            out.append(page)
        else:
            out.append(
                {
                    "no": page.no,
                    "status": page.status,
                    "source": page.source,
                    "confidence": page.confidence,
                    "reason": page.reason,
                }
            )
    return out


def convert_upload(filename: str, data: bytes) -> ImportResult:
    """Run the deterministic conversion for a validated upload."""
    kind = detect_kind(filename)

    if kind in ("pdf", "docx"):
        staged = _stage(filename, data)
        try:
            if kind == "pdf":
                converted = convert_pdf(staged, title=Path(filename).stem)
            else:
                converted = convert_docx(staged, title=Path(filename).stem)
        except ConvertError as exc:
            raise ImportProblem(str(exc)) from exc
        finally:
            staged.unlink(missing_ok=True)

        return ImportResult(
            filename=filename,
            kind=kind,
            import_source=IMPORT_SOURCES[kind],
            title=_title_of(converted.satmd) or Path(filename).stem,
            satmd=converted.satmd,
            warnings=list(converted.warnings),
            answers_status=converted.answers_status,
            pages=list(converted.pages),
            question_count=converted.question_count,
            assets=dict(converted.assets),
        )

    # markdown / .sat.md
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportProblem("the file is not valid UTF-8 text", 400) from exc
    warnings: list[str] = []
    try:
        parsed = parse(text)
    except SatMdError as exc:
        raise ImportProblem(f"line {exc.line}: {exc.message}") from exc
    status = parsed.meta.get("answers", "none")
    if status not in ANSWER_STATUSES:
        status = "none"
    refs = [img for q in parsed.questions for img in q.images]
    if refs:
        warnings.append(
            f"{len(refs)} image reference(s) kept — upload the assets folder to serve them"
        )
    from app.convert.model import PageReport

    return ImportResult(
        filename=filename,
        kind="satmd",
        import_source=IMPORT_SOURCES["satmd"],
        title=parsed.meta.get("title") or Path(filename).stem,
        satmd=text,
        warnings=warnings,
        answers_status=status,
        pages=[PageReport(1, "text", source="sat.md")],
        question_count=len(parsed.questions),
    )


def _title_of(satmd: str) -> str:
    try:
        return parse(satmd).meta.get("title") or ""
    except SatMdError:
        return ""


def commit(result: ImportResult, builtin_key: str | None = None) -> int:
    """Persist a converted result as a document; returns the new document id."""
    try:
        parsed = parse(result.satmd)
    except SatMdError as exc:  # pragma: no cover - converters self-validate
        raise ImportProblem(f"line {exc.line}: {exc.message}") from exc

    title = parsed.meta.get("title") or result.title or Path(result.filename).stem
    doc_id = repos.documents.create_document(
        title=title,
        source_filename=result.filename,
        answers_status=result.answers_status,
        question_count=len(parsed.questions),
        builtin_key=builtin_key,
        import_source=result.import_source,
        used_ai=result.used_ai,
        report_json=json.dumps(pages_to_json(result.pages)),
    )
    repos.documents.set_satmd_path(doc_id)
    repos.documents.write_satmd(doc_id, result.satmd)
    repos.documents.write_assets(doc_id, result.assets)
    repos.documents.insert_questions(doc_id, parsed.questions)
    return doc_id


# --------------------------------------------------------------------------
# staged result persistence (used by the import_jobs pipeline)
# --------------------------------------------------------------------------


# Pages whose OCR status suggests the LLM might help.
_AI_FALLBACK_STATUSES = {"ocr_unavailable", "ocr_failed", "low_confidence", "empty"}


def _has_ai_fallback_pages(pages: list) -> bool:
    return any(
        getattr(p, "status", None) in _AI_FALLBACK_STATUSES for p in pages
    )


def save_result(job_id: str, result: ImportResult, original_pdf: Path | None = None) -> None:
    job_dir = jobs_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "doc.sat.md").write_text(result.satmd, encoding="utf-8")
    if result.assets:
        assets = job_dir / "assets"
        assets.mkdir(exist_ok=True)
        for name, blob in result.assets.items():
            (assets / name).write_bytes(blob)

    # Keep the original PDF for AI fallback if there are pages that might need it.
    if original_pdf and original_pdf.is_file() and _has_ai_fallback_pages(result.pages):
        target = job_dir / "original.pdf"
        if not target.is_file():
            shutil.copy2(original_pdf, target)

    meta = {
        "filename": result.filename,
        "kind": result.kind,
        "import_source": result.import_source,
        "title": result.title,
        "warnings": result.warnings,
        "answers_status": result.answers_status,
        "pages": pages_to_json(result.pages),
        "question_count": result.question_count,
        "used_ai": result.used_ai,
        "assets": sorted(result.assets),
    }
    (job_dir / "result.json").write_text(json.dumps(meta), encoding="utf-8")


def load_result(job_id: str) -> ImportResult | None:
    from app.convert.model import PageReport

    job_dir = jobs_dir(job_id)
    meta_path = job_dir / "result.json"
    if not meta_path.is_file():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    satmd = (job_dir / "doc.sat.md").read_text(encoding="utf-8")
    assets: dict[str, bytes] = {}
    for name in meta.get("assets", []):
        blob = job_dir / "assets" / name
        if blob.is_file():
            assets[name] = blob.read_bytes()
    pages = [PageReport(**p) for p in meta.get("pages", [])]
    return ImportResult(
        filename=meta["filename"],
        kind=meta["kind"],
        import_source=meta.get("import_source") or "sat.md",
        title=meta.get("title") or "",
        satmd=satmd,
        warnings=list(meta.get("warnings", [])),
        answers_status=meta.get("answers_status", "none"),
        pages=pages,
        question_count=meta.get("question_count", 0),
        assets=assets,
        used_ai=bool(meta.get("used_ai", False)),
    )


def clear_result(job_id: str) -> None:
    shutil.rmtree(jobs_dir(job_id), ignore_errors=True)


# --------------------------------------------------------------------------
# AI fallback for specific pages
# --------------------------------------------------------------------------


def run_ai_fallback(job_id: str) -> ImportResult:
    """Run LLM on pages that had OCR issues; merge results back into the job."""
    result = load_result(job_id)
    if result is None:
        raise ImportProblem("staged result not found", 404)

    job_dir = jobs_dir(job_id)
    pdf_path = job_dir / "original.pdf"
    if not pdf_path.is_file():
        raise ImportProblem("no original PDF stored for AI fallback", 409)

    # Identify pages that need AI help.
    page_numbers = [p.no for p in result.pages if p.status in _AI_FALLBACK_STATUSES]
    if not page_numbers:
        return result  # nothing to do

    # Use the LLM fallback to extract questions from those specific pages.
    from app.convert import llm_fallback

    warnings: list[str] = []
    ai_result = llm_fallback.convert(pdf_path, result.title, warnings, page_numbers=page_numbers)

    # Merge: replace the AI-processed pages' questions with the new ones.
    # The ai_result already has questions from all pages it processed (only the
    # requested ones). We need to merge with the deterministic result.
    # Strategy: keep deterministic questions, add AI questions that don't duplicate.
    # Since ai_result only processed specific pages, its questions are from those pages.
    existing_nos = {q.no for q in result.pages if q.no is not None}
    # Actually, ImportResult.pages is PageReport, not BuiltQuestion.
    # The questions are in the satmd. We need to re-parse and merge satmd.

    # Simpler: re-parse both satmds and merge questions by number.
    from app.satmd.parser import parse as parse_satmd

    deterministic_parsed = parse_satmd(result.satmd)
    ai_parsed = parse_satmd(ai_result.satmd)

    # Build a map of AI questions by number.
    ai_q_map = {q.no: q for q in ai_parsed.questions if q.no is not None}

    # Replace deterministic questions for the AI-processed pages with AI questions.
    merged_questions: list = []
    for q in deterministic_parsed.questions:
        if q.no in ai_q_map:
            merged_questions.append(ai_q_map.pop(q.no))
        else:
            merged_questions.append(q)
    # Add any remaining AI questions (new numbers).
    merged_questions.extend(ai_q_map.values())

    # Re-assemble the merged satmd.
    from app.convert.pdf import _assemble, _front_matter

    all_assets = {**result.assets, **ai_result.assets}
    merged = _assemble(
        result.title,
        result.filename,
        merged_questions,
        {**deterministic_parsed.answers, **ai_parsed.answers},
        ai_result.used_ai or result.used_ai,
        all_assets,
        result.warnings + warnings + ["AI fallback processed pages: " + ", ".join(map(str, page_numbers))],
    )

    # Save updated result.
    merged.used_ai = True
    save_result(job_id, merged)
    return merged