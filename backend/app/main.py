"""SATeacher API server — FastAPI entry point (PLAN.md §4)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, builtin, documents, imports, sessions, settings
from app.convert import ocr
from app.db import init_db

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="SATeacher", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # local-only app; the Vite dev server proxies /api anyway
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(documents.router)
app.include_router(imports.router)
app.include_router(builtin.router)
app.include_router(sessions.router)
app.include_router(settings.router)
app.include_router(ai.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": VERSION, "ocr": ocr.available_engines()}
