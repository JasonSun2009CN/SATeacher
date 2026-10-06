"""LLM provider settings: read/write config and probe connectivity.

The API key is write-only: GET returns a masked form, never the raw value.
The stored config is read server-side when the LLM layer runs (Phase 2/4).
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.repos import settings as settings_repo

router = APIRouter(prefix="/api/settings", tags=["settings"])

PROVIDERS = ("openai", "anthropic")
DEFAULT_BASE_URL = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}
PROBE_TIMEOUT = 10.0


class SettingsPayload(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None       # write-only; blank means "keep stored key"
    model: str | None = None
    clear_key: bool = False          # explicit wipe; blank alone keeps the key


def _mask(key: str) -> str:
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:4]}…{key[-4:]}"


def _load() -> dict[str, str]:
    stored = settings_repo.get_all()
    return {
        "provider": stored.get("provider", "openai"),
        "base_url": stored.get("base_url", ""),
        "api_key": stored.get("api_key", ""),
        "model": stored.get("model", ""),
    }


def _view(s: dict[str, str]) -> dict:
    return {
        "provider": s["provider"],
        "base_url": s["base_url"],
        "model": s["model"],
        "api_key_masked": _mask(s["api_key"]) if s["api_key"] else "",
        "api_key_set": bool(s["api_key"]),
    }


@router.get("")
def get_settings() -> dict:
    return _view(_load())


@router.put("")
def put_settings(payload: SettingsPayload) -> dict:
    if payload.provider is not None and payload.provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="provider must be 'openai' or 'anthropic'")
    updates: dict[str, str] = {}
    for field in ("provider", "base_url", "model"):
        value = getattr(payload, field)
        if value is not None:
            updates[field] = value.strip()
    if payload.clear_key:
        updates["api_key"] = ""
    elif payload.api_key and payload.api_key.strip():
        updates["api_key"] = payload.api_key.strip()
    settings_repo.set_values(updates)
    return _view(_load())


class TestPayload(SettingsPayload):
    """Probe with unsaved form values; falls back to the stored config."""


@router.post("/test")
def test_connection(payload: TestPayload) -> dict:
    s = _load()
    provider = payload.provider or s["provider"]
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail="provider must be 'openai' or 'anthropic'")
    base_url = (
        payload.base_url.strip() if payload.base_url is not None and payload.base_url.strip()
        else s["base_url"]
    ) or DEFAULT_BASE_URL[provider]
    api_key = payload.api_key.strip() if payload.api_key else s["api_key"]
    if not api_key:
        return {"ok": False, "detail": "no API key yet — paste a key first"}

    base = base_url.rstrip("/")
    url = base if base.endswith("/models") else base + "/models"
    if provider == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    else:
        headers = {"Authorization": f"Bearer {api_key}"}

    try:
        response = httpx.get(url, headers=headers, timeout=PROBE_TIMEOUT)
    except httpx.HTTPError as exc:
        return {"ok": False, "detail": f"could not reach {url}: {type(exc).__name__}"}

    if response.status_code in (401, 403):
        return {"ok": False, "detail": "authentication failed — check the API key"}
    if response.status_code == 404:
        return {"ok": False, "detail": f"404 at {url} — check the base URL"}
    if response.status_code != 200:
        return {"ok": False, "detail": f"HTTP {response.status_code} from {url}"}

    model_ids: list[str] = []
    try:
        model_ids = [m.get("id", "") for m in response.json().get("data", [])]
    except Exception:  # noqa: BLE001 - a non-JSON body still means we connected
        pass
    detail = f"connected — {len(model_ids)} models available" if model_ids else "connected"
    if payload.model and model_ids and payload.model not in model_ids:
        return {"ok": True, "detail": f"{detail}, but model '{payload.model}' is not listed"}
    return {"ok": True, "detail": detail}
