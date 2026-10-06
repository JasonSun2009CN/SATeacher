"""Settings API: masked key storage, validation and connection probe."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import settings as settings_api
from app.db import db

KEY = "sk-proj-abcdef1234567890"


@pytest.fixture(autouse=True)
def clean_settings() -> None:
    """Settings are global app config — isolate every test from the shared DB."""
    with db() as conn:
        conn.execute("DELETE FROM settings")
    yield


def test_defaults(client: TestClient) -> None:
    body = client.get("/api/settings").json()
    assert body["provider"] == "openai"
    assert body["protocol"] == "openai"
    assert body["api_key_set"] is False
    assert body["api_key_masked"] == ""
    assert "base_url" in body and "model" in body


def test_put_stores_and_masks_key(client: TestClient) -> None:
    put = client.put(
        "/api/settings",
        json={"provider": "anthropic", "base_url": "https://proxy.example/v1",
              "api_key": KEY, "model": "claude-sonnet-4-5"},
    )
    assert put.status_code == 200
    body = put.json()
    assert body["provider"] == "anthropic"
    assert body["protocol"] == "anthropic"
    assert body["model"] == "claude-sonnet-4-5"
    assert body["api_key_set"] is True
    assert KEY not in repr(body), "raw key must never be echoed back"
    assert "…" in body["api_key_masked"] and body["api_key_masked"].endswith("7890")

    again = client.get("/api/settings").json()
    assert again["api_key_masked"] == body["api_key_masked"]
    assert KEY not in repr(again)


def test_blank_key_keeps_stored_key(client: TestClient) -> None:
    client.put("/api/settings", json={"api_key": KEY})
    body = client.put("/api/settings", json={"api_key": "", "model": "gpt-4o-mini"}).json()
    assert body["api_key_set"] is True
    assert body["model"] == "gpt-4o-mini"


def test_unknown_provider_rejected(client: TestClient) -> None:
    resp = client.put("/api/settings", json={"provider": "llama"})
    assert resp.status_code == 400


def test_put_provider_derives_protocol(client: TestClient) -> None:
    body = client.put(
        "/api/settings",
        json={"provider": "deepseek", "api_key": KEY, "model": "deepseek-chat"},
    ).json()
    assert body["provider"] == "deepseek"
    assert body["protocol"] == "openai"


def test_put_explicit_protocol_override(client: TestClient) -> None:
    body = client.put(
        "/api/settings",
        json={"provider": "custom", "protocol": "anthropic"},
    ).json()
    assert body["provider"] == "custom"
    assert body["protocol"] == "anthropic"


def test_unknown_protocol_rejected(client: TestClient) -> None:
    resp = client.put("/api/settings", json={"protocol": "grpc"})
    assert resp.status_code == 400


def test_providers_catalog_orcarouter_first(client: TestClient) -> None:
    body = client.get("/api/settings/providers")
    assert body.status_code == 200
    providers = body.json()
    ids = [p["id"] for p in providers]
    assert ids[0] == "orcarouter"
    for wanted in ("openai", "groq", "mistral", "deepseek", "together", "fireworks",
                   "nvidia", "ollama", "moonshot", "minimax", "dashscope",
                   "openrouter", "openpaths", "anthropic", "custom"):
        assert wanted in ids, f"catalog missing {wanted}"
    orca = providers[0]
    assert orca["base_url"] == "https://api.orcarouter.ai/v1"
    assert orca["protocol"] == "openai"
    assert orca["default_model"] == "orcarouter/auto"


def test_probe_uses_catalog_default_base(client: TestClient, monkeypatch) -> None:
    seen: dict = {}

    def fake_get(url, headers=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        return httpx.Response(200, json={"data": [{"id": "grok-3"}]})

    monkeypatch.setattr(settings_api.httpx, "get", fake_get)
    resp = client.post("/api/settings/test", json={"provider": "groq", "api_key": KEY})
    assert seen["url"] == "https://api.groq.com/openai/v1/models"
    assert seen["headers"]["Authorization"] == f"Bearer {KEY}"
    assert resp.json() == {"ok": True, "detail": "connected — 1 models available"}


def test_probe_custom_needs_base_url(client: TestClient) -> None:
    resp = client.post("/api/settings/test", json={"provider": "custom", "api_key": KEY})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert "base URL" in resp.json()["detail"]


def test_probe_without_key(client: TestClient) -> None:
    client.put("/api/settings", json={"clear_key": True})
    resp = client.post("/api/settings/test", json={})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert "API key" in resp.json()["detail"]


def test_probe_success_reports_models(client: TestClient, monkeypatch) -> None:
    def fake_get(url, headers=None, timeout=None):
        assert url.endswith("/models")
        assert headers["x-api-key"] == KEY
        return httpx.Response(200, json={"data": [{"id": "m1"}, {"id": "m2"}]})

    monkeypatch.setattr(settings_api.httpx, "get", fake_get)
    resp = client.post(
        "/api/settings/test",
        json={"provider": "anthropic", "api_key": KEY, "model": "m1"},
    )
    assert resp.json() == {"ok": True, "detail": "connected — 2 models available"}


def test_probe_auth_failure(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        settings_api.httpx, "get",
        lambda url, headers=None, timeout=None: httpx.Response(401, json={}),
    )
    resp = client.post("/api/settings/test", json={"api_key": KEY})
    assert resp.json()["ok"] is False
    assert "authentication" in resp.json()["detail"]


def test_probe_model_not_listed(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        settings_api.httpx, "get",
        lambda url, headers=None, timeout=None: httpx.Response(
            200, json={"data": [{"id": "other"}]}
        ),
    )
    resp = client.post("/api/settings/test", json={"api_key": KEY, "model": "gpt-x"})
    body = resp.json()
    assert body["ok"] is True
    assert "not listed" in body["detail"]
