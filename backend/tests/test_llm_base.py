"""LLM transport harness: settings routing, request shape, error mapping."""

from __future__ import annotations

import httpx
import pytest

from app import llm
from app.repos import settings as settings_repo

OPENAI_OK = {"choices": [{"message": {"content": "openai-says-hi"}}]}
ANTHROPIC_OK = {"content": [{"type": "text", "text": "anthropic-says-hi"}]}


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch):
    """Stub the settings table."""

    def apply(**overrides):
        data = {
            "provider": "openai",
            "base_url": "",
            "api_key": "sk-test-123",
            "model": "gpt-test",
        }
        data.update(overrides)
        monkeypatch.setattr(settings_repo, "get_all", lambda: data)

    return apply


def _capture(monkeypatch: pytest.MonkeyPatch, response: httpx.Response):
    seen: list[dict] = []

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return response

    monkeypatch.setattr("app.llm.base.httpx.post", fake_post)
    return seen


def test_configured_reflects_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings_repo, "get_all", lambda: {})
    assert llm.configured() is False
    monkeypatch.setattr(
        settings_repo, "get_all", lambda: {"api_key": "k", "model": "m"}
    )
    assert llm.configured() is True


def test_unconfigured_raises_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings_repo, "get_all", lambda: {"model": "m"})
    with pytest.raises(llm.LLMError, match="Settings"):
        llm.complete("sys", [{"role": "user", "content": "hi"}])


def test_openai_request_shape(stored, monkeypatch: pytest.MonkeyPatch) -> None:
    stored()
    seen = _capture(monkeypatch, httpx.Response(200, json=OPENAI_OK))

    out = llm.complete("SYS", [{"role": "user", "content": "label this"}])

    assert out == "openai-says-hi"
    req = seen[0]
    assert req["url"] == "https://api.openai.com/v1/chat/completions"
    assert req["headers"]["Authorization"] == "Bearer sk-test-123"
    assert req["json"]["messages"][0] == {"role": "system", "content": "SYS"}
    assert req["json"]["messages"][1]["content"] == "label this"
    assert req["json"]["temperature"] == 0.0
    assert req["timeout"] == llm.base.TIMEOUT


def test_openai_custom_base_url(stored, monkeypatch: pytest.MonkeyPatch) -> None:
    stored(base_url="https://proxy.internal/v1/")
    seen = _capture(monkeypatch, httpx.Response(200, json=OPENAI_OK))

    llm.complete("s", [{"role": "user", "content": "x"}])

    assert seen[0]["url"] == "https://proxy.internal/v1/chat/completions"


def test_anthropic_request_shape(stored, monkeypatch: pytest.MonkeyPatch) -> None:
    stored(provider="anthropic", base_url="", api_key="ak", model="claude-test")
    seen = _capture(monkeypatch, httpx.Response(200, json=ANTHROPIC_OK))

    out = llm.complete("SYS", [{"role": "user", "content": "label"}])

    assert out == "anthropic-says-hi"
    req = seen[0]
    assert req["url"] == "https://api.anthropic.com/v1/messages"
    assert req["headers"]["x-api-key"] == "ak"
    assert req["json"]["system"] == "SYS"
    assert req["json"]["messages"] == [{"role": "user", "content": "label"}]
    assert req["json"]["max_tokens"] > 0


@pytest.mark.parametrize(
    ("status", "expect"),
    [
        (401, "authentication failed"),
        (403, "authentication failed"),
        (404, "base URL"),
        (429, "rate limited"),
        (400, "HTTP 400"),
        (500, "HTTP 500"),
    ],
)
def test_status_errors_are_mapped(
    stored, monkeypatch: pytest.MonkeyPatch, status: int, expect: str
) -> None:
    stored()
    _capture(monkeypatch, httpx.Response(status, json={"error": {"message": "boom"}}))

    with pytest.raises(llm.LLMError, match=expect):
        llm.complete("s", [{"role": "user", "content": "x"}])


def test_network_failure_is_mapped(stored, monkeypatch: pytest.MonkeyPatch) -> None:
    stored()

    def fake_post(url, json=None, headers=None, timeout=None):
        raise httpx.ConnectTimeout("nope")

    monkeypatch.setattr("app.llm.base.httpx.post", fake_post)

    with pytest.raises(llm.LLMError, match="could not reach"):
        llm.complete("s", [{"role": "user", "content": "x"}])


def test_unexpected_response_shape(stored, monkeypatch: pytest.MonkeyPatch) -> None:
    stored()
    _capture(monkeypatch, httpx.Response(200, json={"weird": True}))

    with pytest.raises(llm.LLMError, match="unexpected response shape"):
        llm.complete("s", [{"role": "user", "content": "x"}])
