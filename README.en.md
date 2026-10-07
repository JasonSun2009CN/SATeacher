# SATeacher

> A local-first SAT practice helper: **import a PDF/DOCX question bank → fill in the answer key → Bluebook-style fullscreen practice → review wrong answers / build a vocabulary list → export to PDF/DOCX**.

![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-4-38B2AC?logo=tailwindcss&logoColor=white)
![Tests](https://img.shields.io/badge/pytest-164%20passed-2E7D32)

**中文**: [README.md](README.md)

---

## Table of contents

- [What is this](#what-is-this)
- [Features](#features)
- [Two iron rules](#two-iron-rules)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [How to use](#how-to-use)
  - [1. Import a question bank](#1-import-a-question-bank)
  - [2. Enter the answer key](#2-enter-the-answer-key)
  - [3. Fullscreen practice](#3-fullscreen-practice)
  - [4. Results & review](#4-results--review)
  - [5. Export](#5-export)
  - [6. LLM settings (optional)](#6-llm-settings-optional)
- [Optional features](#optional-features)
- [Configuration & environment variables](#configuration--environment-variables)
- [Development & tests](#development--tests)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [License](#license)

---

## What is this

SATeacher is a **web app that runs on your own machine** (FastAPI backend + React frontend + a single SQLite file).
Drop an SAT question-bank PDF/Word file into it; it parses the questions **locally — zero tokens spent**,
then gives you a Bluebook-style fullscreen practice session. Submissions are graded automatically, and the
review sidebar lets you write explanations, collect vocabulary, (only on an explicit click) ask an AI to explain
a question, and finally export everything to PDF/DOCX.

```
Import PDF / DOCX / .md ──► local parsing (0 tokens) ──► fill in answer key
        ──► Bluebook fullscreen practice ──► grading + 3-pane review ──► vocabulary / explanations ──► export PDF·DOCX·xlsx
```

## Features

| Area | What it does |
|---|---|
| **Import** | PDF (deterministic PyMuPDF conversion: columns / numbering / options / **answer-key backfill** / images), DOCX (paragraphs, tables, images + zip safety checks), `.md` / `.sat.md`, **scanned PDFs via OCR** (macOS Vision or system `tesseract`), import pipeline with per-page reports and cancel, 60 MB limit |
| **Built-in bank** | `SAT机考25年语文合集（下）1.4` (2025 Aug–Dec, US + International) — **44 modules / 1186 questions**, offline one-click **Add** / **Add all**, 0 tokens, idempotent |
| **Library** | Document list (question count, answered count, answer status), practice history, cascade delete |
| **Answer key** | Per-question A–D grid + **bulk paste** (`1-A 2-C` / `1. A` / `ACBDA`) + validation + preview, written back to the source file |
| **Practice** | Bluebook-style fullscreen, timer, one-question-at-a-time view, question palette, flagging, keyboard `A–D` / `← →`, submit confirmation |
| **Results & review** | Score / per-section / time stats, `All · Correct · Wrong` filters, three-pane master–detail, regrade after filling in the key |
| **Sidebar** | Hand-written explanations (saved locally), vocabulary table `Word \| Meaning \| Notes` (+ `.xlsx` export), **AI Answer** (explicit opt-in), export entry |
| **Export** | **PDF** (WeasyPrint: page numbers, images, MathJax SVG formulas), **DOCX** (python-docx), vocabulary **.xlsx** |
| **Settings** | Catalog of 16 LLM providers, protocol (openai/anthropic), Base URL, masked API key, model, connectivity test |

## Two iron rules

1. **No LLM in the main path**: import/parsing/grading/exporting are deterministic local computation, **0 tokens**.
   An external API is called only when you explicitly click **AI Answer** in the review sidebar (or run a connectivity test).
2. **Local-first**: all data lives in the repo's `data/` directory (`app.db` + per-document `doc.sat.md` and images). Nothing is uploaded anywhere.

## Prerequisites

| Dependency | Version | Used for |
|---|---|---|
| Python | **3.11+** (tested on 3.13) | backend |
| Node.js | **18+** | frontend build / dev server; (optional) math rendering in exports |
| `pip install -r backend/requirements.txt` | — | fastapi · uvicorn · pymupdf · httpx · weasyprint · python-docx · openpyxl · cairosvg … |
| `npm install` (in `frontend/`) | — | React 19 + Vite 7 + Tailwind 4 |

<details>
<summary><b>System libraries needed by WeasyPrint (PDF export)</b></summary>

```bash
# macOS
brew install pango cairo gdk-pixbuf harfbuzz

# Debian / Ubuntu
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libharfbuzz0b
```

Without them **only PDF export fails**; everything else keeps working.
</details>

## Quick start

```bash
git clone https://github.com/JasonSun2009CN/SATeacher.git
cd SATeacher

./scripts/dev.sh
```

`scripts/dev.sh` creates `.venv`, installs backend deps, runs `npm install`, and starts both servers.
You should see:

- API: <http://localhost:8000> (health check: <http://localhost:8000/api/health>)
- App: <http://localhost:5173> ← **open this one in your browser**

`Ctrl-C` stops both.

<details>
<summary><b>Manual start (without dev.sh)</b></summary>

```bash
# 1) backend (terminal A)
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload --port 8000

# 2) frontend (terminal B)
cd frontend
npm install
npm run dev
```

> The app is currently served by the Vite dev server (the backend only serves `/api`).
> `npm run build` produces `frontend/dist/` for type checking and build verification.
</details>

## How to use

> Button and page names below are quoted verbatim so you can match them on screen.

### 1. Import a question bank

Open <http://localhost:5173> (the Import page, i.e. the home page).

1. **Upload a file**: drop it onto *Drag a file here*, or click **choose a file**.
   Supported: `PDF · DOCX · .md · .markdown · .sat.md` (≤ 60 MB; questions must be numbered `1.` `2.` … with four options each).
2. **Watch the pipeline**: `detect → convert → review`, with a **per-page report** (text / OCR / low confidence / no engine).
   - Clean conversion → committed automatically;
   - Anything suspicious → it stops for review; click **Commit** to save or **Cancel** to discard (0 tokens either way).
3. **(Optional) Use the built-in bank**: expand the bank card on the Import page to see 44 date-grouped modules; click **Add** per module or **Add all** for the whole bank. Added modules show **✓ In library** and link straight to practice.
4. **Check the Library**: the list below shows every document with **Practice** / **Answers** / **Delete**.

<details>
<summary>No question bank file? Write your own SAT-MD</summary>

The *SatMdTemplate* on the Import page gives you a `.sat.md` template (copy or download), write questions by hand, then upload it.
</details>

### 2. Enter the answer key

If the imported document has a missing/partial answer key (the list flags it), click **Answers** (`/doc/:id/answers`):

- **Per-question grid**: click A/B/C/D for each question;
- **Bulk entry**: paste `1-A 2-C 3-D`, `1. A`, `12B`, or a bare letter string `ACBDA`, then **Apply to grid**;
- Saving validates A–D only and writes the key back to `doc.sat.md`; use **Preview** to double-check first.

> You can also practice without a key: after submitting you are sent here, and saving triggers an automatic regrade.

### 3. Fullscreen practice

Click **Practice** in the Library:

1. The start screen shows *Ready to begin* plus the question count — click **Begin — enter fullscreen**; **the timer starts now** (or click *Enter answers first (optional)* to fill in the key first);
2. Answering:
   - click an option, or press **`A` `B` `C` `D`**;
   - **`←` `→`** move to the previous/next question;
   - the question palette at the bottom jumps to any question;
   - **Mark for review** flags the current question (shown in the palette; click again to unflag);
3. When done, click **Submit** → confirm → **Submit** to be graded.

### 4. Results & review

Submitting takes you to `/session/:sid/result`:

- **Stats panel**: Score, Reading & Writing, Math, Time, plus **Wrong answers** chips (click to jump to that question);
- **Filter tabs**: `All` / `Correct` / `Wrong`;
- **Three panes**: question index (left) → single question with `←` `→` keyboard navigation (center) → sticky **ReviewSidebar** (right);
- Top buttons: **Practice again** / **Back to library** / **Hide panel · Show panel**;
- Documents without an answer key route you through key entry first, then regrade.

**ReviewSidebar (right workspace)**:

| Section | How to use |
|---|---|
| **Explanation** | Write your own explanation for the current question; save stores it locally (0 token) |
| **Vocabulary** | A `Word \| Meaning \| Notes` table: add/remove rows & columns, edit, save; **Export .xlsx** (openpyxl; opens in Numbers/Excel) |
| **AI Answer** | Calls the LLM only when you click it (context = stem + correct option); gives a clear message if no key or no API key configured |
| **Export** | **Export .pdf** / **Export .docx** — questions, answers and explanations (no AI involved) |

### 5. Export

- **Whole document**: ReviewSidebar → **Export** → `Export .pdf` or `Export .docx`;
  - PDF: A4, footer page numbers, embedded images, formulas via MathJax SVG;
  - DOCX: headings/paragraphs/answer key/explanations/vocabulary, formulas converted to PNG via cairosvg.
- **Vocabulary**: **Export .xlsx** in the Vocabulary section.

### 6. LLM settings (optional)

Open **⚙ Settings** (top-right of the Import page, `/settings`) — **the app works fully without it**; AI Answer is the only feature that needs it:

1. Pick a **Provider** from the built-in catalog of 16 (Base URL and default model included);
2. **Base URL** is overridable (switching providers only auto-fills it if you have not customized it);
3. **API Key** is write-only and shown masked;
4. **Model** takes any model id (gateway providers auto-fill a default);
5. Click **Save settings**, then **Test connection**; the protocol (openai / anthropic) is derived from the provider but can be set explicitly.

## Optional features

| Feature | What it does | Install |
|---|---|---|
| **Scanned PDF OCR** | Per-page text-density detection; low-density pages are rasterized and recognized, coordinates normalized back into the same pipeline | Either system `tesseract` (`brew install tesseract` / `sudo apt install tesseract-ocr`, zero Python deps), or on macOS `pip install pyobjc-framework-Vision`. Without one, the Import page shows a hint — it never crashes |
| **Math in exports** | TeX → SVG (inline in PDF / PNG in DOCX) | `cd backend/app/export/mathjax && npm install` (needs Node; without it formulas **degrade to plain text** and export still succeeds) |

The Import page shows the currently available OCR engines (from the `ocr` field of `/api/health`).

## Configuration & environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SATEACHER_DATA` | `./data` | Data root (`app.db`, `docs/<id>/`, `tmp/`, `exports/`, `jobs/`). Tests use isolated temp dirs |
| `SATEACHER_API` | `http://localhost:8000` | Vite dev-proxy target (change it when the backend is elsewhere) |

Ports: backend `8000`, frontend `5173`.

> ⚠️ `data/` holds your real data (gitignored) — back it up before wiping it.

## Development & tests

```bash
# Backend tests (baseline: 164 passed; temp data dir, your data untouched)
cd backend && ../.venv/bin/python -m pytest -q

# Frontend type check + build (0 errors)
cd frontend && npm run build

# Local dev (backend :8000 + frontend :5173)
./scripts/dev.sh
```

## Project structure

```
SATeacher/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app (/api/health, 6 routers)
│   │   ├── api/               documents · imports · builtin · sessions · settings · ai
│   │   ├── convert/           pdf · docx · bluebook · normalize · ocr/ · llm_fallback
│   │   ├── satmd/             SAT-MD parser (deterministic state machine)
│   │   ├── export/            pdf (WeasyPrint) · docx · math_render (+ MathJax bridge)
│   │   ├── repos/ · llm/      persistence · LLM transports
│   │   ├── providers.py       catalog of 16 providers
│   │   └── builtin/           built-in bank (44 modules shipped in-repo)
│   ├── tests/                 pytest (164)
│   └── requirements.txt
├── frontend/                  Vite + React 19 + TS + Tailwind 4
│   └── src/pages/             Import · AnswerKey · Practice · Result · Settings
├── scripts/dev.sh             start both servers
├── data/                      runtime data (gitignored)
└── docs/                      ARCHITECTURE · PLAN · SAT-MD · RENOVATION_PLAN
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `dev.sh` reports a port already in use | `lsof -i :8000` / `:5173`, stop that process, or start on another port |
| Page stuck on Loading / cannot reach backend | Check <http://localhost:8000/api/health> returns `{"status":"ok",...}`; if the backend is elsewhere set `SATEACHER_API=http://host:port` and restart vite |
| Importing a scanned PDF asks for OCR | Install `tesseract` (any OS) or, on macOS, `pip install pyobjc-framework-Vision`, then restart the backend and re-import |
| DOCX import rejected | Uploads are zip-safety-checked (entry count / uncompressed size / compression ratio / macros); broken or encrypted files are rejected — use a normally exported `.docx` |
| PDF export fails | Install the WeasyPrint system libraries (see the collapsible block in [Prerequisites](#prerequisites)) |
| Formulas come out as plain text in exports | `cd backend/app/export/mathjax && npm install` and retry (needs Node) |
| `npm run build` reports type errors | `cd frontend && npm install` and rerun; otherwise follow the TS error |
| Start from scratch | Back up, then delete `data/` (or point `SATEACHER_DATA` at a new directory); the backend recreates the DB on start |

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture, data model, full API surface (27 endpoints)
- [`docs/PLAN.md`](docs/PLAN.md) — product goals, confirmed decisions, delivery log
- [`docs/SAT-MD.md`](docs/SAT-MD.md) — SAT-MD format specification
- [`docs/RENOVATION_PLAN.md`](docs/RENOVATION_PLAN.md) — 12-chapter renovation plan (batches 7–16)
- [`ROADMAP.md`](ROADMAP.md) — roadmap and known gaps
- [`HANDOFF.md`](HANDOFF.md) — handover status (for maintainers / AI agents; in Chinese)

## License

[Apache License 2.0](LICENSE)
