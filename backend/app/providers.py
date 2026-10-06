"""Model-service-provider catalog.

A *provider* is the service that hosts models and exposes them at a base
URL (Groq, DeepSeek, OrcaRouter, …). A *protocol* is the wire format the
service speaks — OpenAI's ``chat/completions`` (Bearer auth) or Anthropic's
``messages`` (``x-api-key`` auth). "OpenAI" and "Anthropic" are therefore
protocols, not providers, and one protocol-compatible provider generally
works with any service that exposes it.

Base URLs below were verified against each provider's official docs on
2026-10-06:

- OrcaRouter     https://api.orcarouter.ai/v1        (orcarouter.ai)
- OpenAI         https://api.openai.com/v1           (standard)
- Groq           https://api.groq.com/openai/v1      (GroqDocs)
- Mistral AI     https://api.mistral.ai/v1           (standard)
- DeepSeek       https://api.deepseek.com/v1         (standard)
- Together AI    https://api.together.xyz/v1         (standard)
- Fireworks AI   https://api.fireworks.ai/inference/v1  (official)
- NVIDIA NIM     https://integrate.api.nvidia.com/v1    (docs.api.nvidia.com)
- Ollama local   http://127.0.0.1:11434/v1          (standard)
- Moonshot (Kimi) https://api.moonshot.cn/v1         (platform.moonshot.cn)
- MiniMax        https://api.minimaxi.com/v1         (CN; api.minimax.io/v1 is the intl endpoint)
- DashScope intl https://dashscope-us.aliyuncs.com/compatible-mode/v1 (Aliyun docs)
- OpenRouter     https://openrouter.ai/api/v1        (standard; auto: openrouter/auto)
- OpenPaths      https://openpaths.io/v1             (openpaths.io; auto: openpaths/auto)
- Anthropic      https://api.anthropic.com/v1        (standard; Messages protocol)
- Custom         no default URL (user-provided, OpenAI-compatible)
"""

from __future__ import annotations

PROTOCOL_OPENAI = "openai"
PROTOCOL_ANTHROPIC = "anthropic"
PROTOCOLS = (PROTOCOL_OPENAI, PROTOCOL_ANTHROPIC)

PROVIDERS: list[dict] = [
    {
        "id": "orcarouter",
        "name": "OrcaRouter",
        "base_url": "https://api.orcarouter.ai/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": "orcarouter/auto",
        "note": "Routes every request to the cheapest live model — use model orcarouter/auto.",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "",
    },
    {
        "id": "groq",
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "",
    },
    {
        "id": "mistral",
        "name": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "",
    },
    {
        "id": "together",
        "name": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "",
    },
    {
        "id": "fireworks",
        "name": "Fireworks AI",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "",
    },
    {
        "id": "nvidia",
        "name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "",
    },
    {
        "id": "ollama",
        "name": "Ollama (local)",
        "base_url": "http://127.0.0.1:11434/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "Runs fully offline on this machine — no API key needed.",
    },
    {
        "id": "moonshot",
        "name": "Moonshot (Kimi)",
        "base_url": "https://api.moonshot.cn/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "",
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "base_url": "https://api.minimaxi.com/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "China endpoint — international accounts use api.minimax.io/v1.",
    },
    {
        "id": "dashscope",
        "name": "DashScope (international)",
        "base_url": "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "Aliyun Model Studio US region, OpenAI-compatible mode.",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": "openrouter/auto",
        "note": "Gateway with auto-routing — use model openrouter/auto.",
    },
    {
        "id": "openpaths",
        "name": "OpenPaths",
        "base_url": "https://openpaths.io/v1",
        "protocol": PROTOCOL_OPENAI,
        "default_model": "openpaths/auto",
        "note": "Open-source model router — use model openpaths/auto.",
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "protocol": PROTOCOL_ANTHROPIC,
        "default_model": None,
        "note": "Speaks the Anthropic Messages protocol (x-api-key auth).",
    },
    {
        "id": "custom",
        "name": "Custom (OpenAI-compatible)",
        "base_url": "",
        "protocol": PROTOCOL_OPENAI,
        "default_model": None,
        "note": "Enter any OpenAI-compatible base URL.",
    },
]


def get_provider(provider_id: str) -> dict | None:
    """Look up a provider preset by id, or None when unknown."""
    return next((p for p in PROVIDERS if p["id"] == provider_id), None)


def provider_ids() -> tuple[str, ...]:
    return tuple(p["id"] for p in PROVIDERS)


def default_base_url(provider_id: str) -> str:
    """The official base URL for a provider preset ('' for unknown/custom)."""
    p = get_provider(provider_id)
    return p["base_url"] if p else ""


def default_protocol(provider_id: str) -> str:
    """The wire protocol a provider preset speaks (OpenAI by default)."""
    p = get_provider(provider_id)
    return p["protocol"] if p else PROTOCOL_OPENAI