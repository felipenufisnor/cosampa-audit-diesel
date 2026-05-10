"""ChatClient: camada de orquestracao sobre LLMProvider.

Adiciona:
- Retries com backoff exponencial (tenacity) para falhas transientes.
- Logging estruturado (tokens, latencia, modelo, provider).
- Fallback de modelo quando o primario retorna erro 5xx ou 429.
- Tipos pequenos (`ChatMessage`, `ChatResponse`) sem expor SDK pra dominio.

Mantemos a interface generica: domain code passa lista de mensagens + tools
opcionais; recebe resposta com tool_calls + content + metricas de uso.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from audit_diesel.config import Settings, get_settings

from .provider import LLMProvider, ProviderInfo, get_provider

log = structlog.get_logger("audit_diesel.ai.client")


@dataclass
class ChatMessage:
    """Mensagem trocada com o modelo (compativel com OpenAI Chat)."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        return d


@dataclass
class ToolCall:
    """Chamada de ferramenta retornada pelo modelo."""

    id: str
    name: str
    arguments_json: str


@dataclass
class ChatUsage:
    """Tokens consumidos na chamada (best-effort: nem todos providers reportam)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatResponse:
    """Resposta normalizada da chamada de chat."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: ChatUsage = field(default_factory=ChatUsage)
    model: str | None = None
    latency_s: float = 0.0
    provider: ProviderInfo | None = None


class _RetryableError(Exception):
    """Marker para excecoes que valem retry."""


class ChatClient:
    """Cliente de alto nivel para chat completions.

    Use uma instancia por processo (pequena, thread-safe).
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._provider = provider or get_provider(self._settings)

    @property
    def provider(self) -> LLMProvider:
        return self._provider

    def chat(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Executa chat com retry/fallback. Levanta apos esgotar tentativas."""
        primary = self._settings.llm_model
        fallback = self._settings.llm_fallback_model

        try:
            return self._chat_with_retry(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
                model=primary,
            )
        except _RetryableError as exc:
            if not fallback:
                raise
            log.warning(
                "ai.fallback.activated",
                primary=primary,
                fallback=fallback,
                error=str(exc),
            )
            return self._chat_with_retry(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
                model=fallback,
            )

    def _chat_with_retry(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
        temperature: float,
        max_tokens: int | None,
        model: str,
    ) -> ChatResponse:
        retries = max(0, self._settings.llm_max_retries)

        @retry(
            stop=stop_after_attempt(retries + 1),
            wait=wait_exponential_jitter(initial=0.5, max=8.0),
            retry=retry_if_exception_type(_RetryableError),
            before_sleep=before_sleep_log(log, "WARNING"),  # type: ignore[arg-type]
            reraise=True,
        )
        def _call() -> ChatResponse:
            return self._do_chat(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )

        return _call()

    def _do_chat(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
        temperature: float,
        max_tokens: int | None,
        model: str,
    ) -> ChatResponse:
        t0 = time.perf_counter()
        try:
            raw = self._provider.chat(
                messages=[m.to_dict() for m in messages],
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - t0
            transient = _is_transient(exc)
            log.error(
                "ai.chat.error",
                model=model,
                elapsed_s=round(elapsed, 3),
                transient=transient,
                error=str(exc),
                error_type=exc.__class__.__name__,
            )
            if transient:
                raise _RetryableError(str(exc)) from exc
            raise

        elapsed = time.perf_counter() - t0
        response = _parse_response(raw, latency_s=elapsed, provider=self._provider.info)
        log.info(
            "ai.chat.ok",
            model=response.model or model,
            provider=response.provider.name if response.provider else "?",
            elapsed_s=round(elapsed, 3),
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            n_tool_calls=len(response.tool_calls),
            finish_reason=response.finish_reason,
        )
        return response


def _is_transient(exc: BaseException) -> bool:
    """Heuristica para detectar erros que vale a pena retry."""
    name = exc.__class__.__name__.lower()
    transient_names = {
        "apitimeouterror", "timeoutexception", "ratelimiterror",
        "internalservererror", "apiconnectionerror", "connectionerror",
        "readtimeout", "remotedisconnected",
    }
    if name in transient_names:
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    return status in {408, 425, 429, 500, 502, 503, 504}


def _parse_response(
    raw: dict[str, Any],
    *,
    latency_s: float,
    provider: ProviderInfo,
) -> ChatResponse:
    """Converte dict OpenAI-compatible em ChatResponse normalizada."""
    choices = raw.get("choices") or []
    msg: dict[str, Any] = {}
    finish_reason: str | None = None
    if choices:
        choice = choices[0]
        msg = choice.get("message") or {}
        finish_reason = choice.get("finish_reason")

    content = msg.get("content") or ""
    tool_calls: list[ToolCall] = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        tool_calls.append(
            ToolCall(
                id=str(tc.get("id") or ""),
                name=str(fn.get("name") or ""),
                arguments_json=str(fn.get("arguments") or "{}"),
            )
        )

    usage_raw = raw.get("usage") or {}
    usage = ChatUsage(
        prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
        completion_tokens=int(usage_raw.get("completion_tokens") or 0),
        total_tokens=int(usage_raw.get("total_tokens") or 0),
    )

    return ChatResponse(
        content=content,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=usage,
        model=raw.get("model"),
        latency_s=latency_s,
        provider=provider,
    )
