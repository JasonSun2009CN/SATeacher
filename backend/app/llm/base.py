"""Unified LLM invocation — settings-driven routing with bounded failure modes.

Harness rules (one transport for import fallback AND the in-app AI panel):
- config comes from the SQLite settings table (provider, base_url, api_key, model);
- temperature 0 for reproducible, testable outputs;
- a single bounded timeout, no hidden retries (callers own their retry loops);
- every failure surfaces as a typed LLMError with an actionable message.
"""

from __future__ import annotations

import httpx

from app.repos import settings as settings_repo

TIMEOUT = 60.0
TEMPERATURE = 0.0
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_BASE = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}


class LLMError(Exception):
    """A user-facing LLM failure (bad config, network, provider error)."""


def _config() -> dict[str, str]:
    stored = settings_repo.get_all()
    provider = stored.get("provider", "openai")
    if provider not in DEFAULT_BASE:
        raise LLMError(f"unknown provider {provider!r} — fix it in Settings")
    key = stored.get("api_key", "")
    model = stored.get("model", "")
    if not key or not model:
        raise LLMError("no API key or model configured — set them in Settings")
    base = (stored.get("base_url") or DEFAULT_BASE[provider]).rstrip("/")
    return {"provider": provider, "key": key, "model": model, "base": base}


def configured() -> bool:
    """True when an API key and a model are stored — i.e. AI paths may run."""
    stored = settings_repo.get_all()
    return bool(stored.get("api_key") and stored.get("model"))


def complete(system: str, messages: list[dict[str, str]]) -> str:
    """One chat completion. `messages` is a list of {role, content} dicts.

    Raises LLMError on configuration, network, or provider failures.
    """
    cfg = _config()
    if cfg["provider"] == "anthropic":
        return _anthropic(cfg, system, messages)
    return _openai(cfg, system, messages)


def _post(url: str, headers: dict[str, str], payload: dict) -> httpx.Response:
    try:
        return httpx.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise LLMError(f"could not reach {url}: {type(exc).__name__}") from exc


def _raise_for_status(response: httpx.Response, url: str) -> None:
    if response.status_code in (401, 403):
        raise LLMError("authentication failed — check the API key in Settings")
    if response.status_code == 404:
        raise LLMError(f"404 from {url} — check the base URL in Settings")
    if response.status_code == 429:
        raise LLMError("rate limited by the provider — try again shortly")
    if response.status_code == 400:
        detail = ""
        try:
            detail = str(response.json().get("error", ""))[:200]
        except Exception:  # noqa: BLE001 - body may not be JSON
            pass
        raise LLMError(f"provider rejected the request (HTTP 400): {detail}")
    if response.status_code >= 500:
        raise LLMError(f"provider error (HTTP {response.status_code}) — try again")
    raise LLMError(f"unexpected HTTP {response.status_code} from {url}")


def _anthropic(cfg: dict[str, str], system: str,
               messages: list[dict[str, str]]) -> str:
    url = cfg["base"] + "/messages"
    headers = {"x-api-key": cfg["key"], "anthropic-version": ANTHROPIC_VERSION}
    payload = {
        "model": cfg["model"],
        "system": system,
        "messages": messages,
        "max_tokens": 8192,
        "temperature": TEMPERATURE,
    }
    response = _post(url, headers, payload)
    if response.status_code != 200:
        _raise_for_status(response, url)
    try:
        blocks = response.json()["content"]
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    except (KeyError, TypeError, ValueError) as exc:
        raise LLMError("unexpected response shape from the provider") from exc


def _openai(cfg: dict[str, str], system: str,
            messages: list[dict[str, str]]) -> str:
    url = cfg["base"] + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['key']}"}
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": system}, *messages],
        "temperature": TEMPERATURE,
    }
    response = _post(url, headers, payload)
    if response.status_code != 200:
        _raise_for_status(response, url)
    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMError("unexpected response shape from the provider") from exc
