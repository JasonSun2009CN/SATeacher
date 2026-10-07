"""Renderer-neutral representation of a document for PDF / DOCX export."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app import repos
from app.db import assets_dir
from app.repos import documents as documents_repo
from app.repos import words as words_repo

_SECTION_LABEL = {"rw": "Reading & Writing", "math": "Math"}


def section_label(sec: str | None) -> str:
    return _SECTION_LABEL.get(sec or "", sec or "")


def option_map(options: list[str]) -> dict[str, str]:
    """Map option letters to their text: ``{'A': 'one', ...}``."""
    out: dict[str, str] = {}
    for i, opt in enumerate(options or []):
        text = (opt or "").strip()
        match = re.match(r"^([A-D])[.)]\s*([\s\S]*)$", text)
        letter = match.group(1) if match else ("ABCD"[i] if i < 4 else "?")
        out[letter] = (match.group(2) if match else text).strip()
    return out


@dataclass
class ExportQuestion:
    no: int
    sec: str
    source: str | None
    material: str | None
    stem: str
    options: dict[str, str]
    images: list
    answer: str | None
    explain: str | None


@dataclass
class ExportDoc:
    title: str
    source_filename: str
    created_at: str
    questions: list[ExportQuestion]
    vocab_headers: list[str]
    vocab_rows: list[list[str]]

    @property
    def answered(self) -> int:
        return sum(1 for q in self.questions if q.answer)


def build_export(doc_id: int) -> ExportDoc | None:
    """Gather a document + its questions + vocabulary for rendering."""
    doc = repos.documents.get_document(doc_id)
    if doc is None:
        return None
    adir = assets_dir(doc_id)
    questions: list[ExportQuestion] = []
    for i, q in enumerate(documents_repo.list_questions(doc_id), start=1):
        images = []
        for ref in q.get("images") or []:
            path = adir / ref.split("/")[-1]
            if path.is_file():
                images.append(path)
        questions.append(
            ExportQuestion(
                no=q["no"] if q["no"] is not None else i,
                sec=q["sec"] or "",
                source=q["source"],
                material=q["material"],
                stem=q["stem"],
                options=option_map(q["options"]),
                images=images,
                answer=q["answer"],
                explain=q["explain"],
            )
        )
    grid = words_repo.get_grid(doc_id)
    columns = grid["columns"]
    return ExportDoc(
        title=doc["title"],
        source_filename=doc.get("source_filename", ""),
        created_at=doc.get("created_at", ""),
        questions=questions,
        vocab_headers=[c["name"] for c in columns],
        vocab_rows=[
            [row["cells"].get(c["id"], "") for c in columns] for row in grid["rows"]
        ],
    )