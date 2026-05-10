"""LLMProvider: interface unica sobre qualquer endpoint OpenAI-compatible.

Suporta OpenRouter, Together, Groq, Ollama, vLLM e equivalentes ao trocar
`LLM_BASE_URL` + `LLM_API_KEY`. O provider retorna sempre dicts JSON do
formato OpenAI Chat Completions; nao expomos tipos especificos do SDK pra fora.

Modo offline: se `AUDIT_AI_OFFLINE=1` ou se nao houver chave, devolve um
provider local (`OfflineProvider`) que casa requisicoes com fixtures
determinisicas (ver `audit_diesel.ai.fixtures`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import structlog

from audit_diesel.config import Settings, get_settings

log = structlog.get_logger("audit_diesel.ai.provider")


@dataclass
class ProviderInfo:
    """Identificacao do provider em uso, exposta em /healthz."""

    name: str
    base_url: str
    model: str
    offline: bool


@runtime_checkable
class LLMProvider(Protocol):
    """Interface minima para qualquer backend OpenAI-compatible.

    Implementacoes devem ser thread-safe e idempotentes em relacao ao input.
    """

    info: ProviderInfo

    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Executa uma chamada de chat completion. Retorna dict no formato OpenAI."""
        ...


class OpenAICompatibleProvider:
    """Provider real apoiado pelo SDK `openai` apontando para qualquer base_url."""

    def __init__(self, settings: Settings) -> None:
        from openai import OpenAI

        self._settings = settings
        self._client = OpenAI(
            api_key=settings.llm_api_key or "no-key",
            base_url=settings.llm_base_url,
            timeout=settings.llm_request_timeout_s,
            max_retries=0,  # retries cuidados pelo ChatClient via tenacity.
        )
        self.info = ProviderInfo(
            name=settings.llm_provider,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            offline=False,
        )

    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model or self._settings.llm_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = self._client.chat.completions.create(**kwargs)
        # SDK >=1.40 retorna pydantic model; serializa para dict puro.
        return response.model_dump()


class OfflineProvider:
    """Provider determinisitico que dispara fixtures locais por tipo de tarefa.

    Identifica a tarefa via primeira system message (cada prompt tem um marker
    `[task:<name>]` no inicio do system prompt). Isso mantem o offline robusto
    mesmo conforme prompts evoluem.
    """

    def __init__(self, settings: Settings) -> None:
        from . import fixtures

        self._fixtures = fixtures
        self.info = ProviderInfo(
            name="offline",
            base_url="local://fixtures",
            model=settings.llm_model + " (mocked)",
            offline=True,
        )

    def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        return self._fixtures.responder(
            messages=messages,
            tools=tools,
        )


def get_provider(settings: Settings | None = None) -> LLMProvider:
    """Factory que escolhe entre OpenAI-compatible real ou OfflineProvider.

    Decisao: offline se `AUDIT_AI_OFFLINE=1` ou se `LLM_API_KEY` esta vazio
    *e* o base_url nao aponta para servidor local (Ollama/vLLM).
    """
    settings = settings or get_settings()
    forca_offline = settings.audit_ai_offline
    chave_disponivel = bool(settings.llm_api_key)
    base_local = "localhost" in settings.llm_base_url or "127.0.0.1" in settings.llm_base_url
    if forca_offline or (not chave_disponivel and not base_local):
        log.info("ai.provider.selected", mode="offline", reason="no_key_or_forced")
        return OfflineProvider(settings)
    log.info(
        "ai.provider.selected",
        mode="online",
        provider=settings.llm_provider,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    )
    return OpenAICompatibleProvider(settings)
