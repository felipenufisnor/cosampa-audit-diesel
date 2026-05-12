"""ChatClient: camada de orquestracao sobre LLMProvider.

Adiciona:
- Retries com backoff exponencial (tenacity) para falhas transientes.
- Logging estruturado (tokens, latencia, modelo, provider).
- Fallback de modelo quando o primario retorna erro 5xx ou 429.
- Tipos pequenos (`ChatMessage`, `ChatResponse`) sem expor SDK pra dominio.
- `stream_completion` async para emitir chunks de texto (usado pelo
  reasoning stream da Feature A da v2). O modo offline replay determinisitico.

Mantemos a interface generica: domain code passa lista de mensagens + tools
opcionais; recebe resposta com tool_calls + content + metricas de uso.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from audit_diesel.config import BACKEND_DIR, Settings, get_settings

from .provider import LLMProvider, ProviderInfo, get_provider

log = structlog.get_logger("audit_diesel.ai.client")


@dataclass
class ChatMessage:
    """Mensagem trocada com o modelo (compativel com OpenAI Chat).

    Quando `role == "assistant"` e o modelo emitiu `tool_calls`, o caller
    deve preservar essas chamadas no historico para que a proxima request
    case `tool_call_id` corretamente. Por isso o campo `tool_calls` opcional.
    """

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
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

    @property
    def settings(self) -> Settings:
        return self._settings

    def chat(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        model_override: str | None = None,
    ) -> ChatResponse:
        """Executa chat com retry/fallback. Levanta apos esgotar tentativas."""
        primary = model_override or self._settings.llm_model
        fallback = None if model_override else self._settings.llm_fallback_model

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
        _audit_llm_call(
            feature="chat",
            model=response.model or model,
            provider=response.provider.name if response.provider else "?",
            offline=bool(response.provider and response.provider.offline),
            latency_s=elapsed,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            fallback_used=False,
            extra={"n_tool_calls": len(response.tool_calls)},
        )
        return response

    async def stream_completion(
        self,
        *,
        messages: list[ChatMessage],
        feature: str = "stream",
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        timeout_s: float | None = None,
    ) -> AsyncIterator[str]:
        """Emite chunks de texto do modelo em modo streaming.

        Implementacao:
        - Online (provider real): usa `AsyncOpenAI` apontando para o mesmo
          base_url/api_key do provider sincrono. Retorna chunks crus.
        - Offline (provider mocked): sintetiza chunks a partir das fixtures
          deterministicas, mantendo a UX da Feature A reproduzivel sem rede.

        Fallback: em erro transiente no primario, espera backoff exponencial
        ate `LLM_MAX_RETRIES`, depois tenta o `LLM_FALLBACK_MODEL` uma vez.
        Se ainda falhar, levanta a excecao para o orquestrador SSE decidir.
        """
        primary = model or self._settings.llm_model
        fallback = self._settings.llm_fallback_model if model is None else None
        timeout = timeout_s if timeout_s is not None else self._settings.llm_request_timeout_s

        if self._provider.info.offline:
            async for chunk in _offline_stream(messages):
                yield chunk
            _audit_llm_call(
                feature=feature,
                model=self._provider.info.model,
                provider="offline",
                offline=True,
                latency_s=0.0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                fallback_used=False,
                extra={"streaming": True},
            )
            return

        attempts = max(0, self._settings.llm_max_retries) + 1
        last_exc: Exception | None = None
        used_model: str = primary
        fallback_used = False

        for current_model in [primary] + ([fallback] if fallback else []):
            if current_model is None:
                continue
            used_model = current_model
            for attempt_idx in range(attempts):
                t0 = time.perf_counter()
                try:
                    chunks_total = 0
                    async for chunk in _real_stream(
                        settings=self._settings,
                        messages=[m.to_dict() for m in messages],
                        model=current_model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout_s=timeout,
                    ):
                        chunks_total += 1
                        yield chunk
                    elapsed = time.perf_counter() - t0
                    _audit_llm_call(
                        feature=feature,
                        model=current_model,
                        provider=self._provider.info.name,
                        offline=False,
                        latency_s=elapsed,
                        prompt_tokens=0,
                        completion_tokens=chunks_total,
                        total_tokens=chunks_total,
                        fallback_used=fallback_used,
                        extra={"streaming": True, "chunks": chunks_total},
                    )
                    return
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    transient = _is_transient(exc)
                    elapsed = time.perf_counter() - t0
                    log.warning(
                        "ai.stream.error",
                        model=current_model,
                        attempt=attempt_idx + 1,
                        transient=transient,
                        elapsed_s=round(elapsed, 3),
                        error=str(exc),
                        error_type=exc.__class__.__name__,
                    )
                    if not transient:
                        break
                    await asyncio.sleep(min(1.0 * (2 ** attempt_idx), 8.0))
            # esgotou retries no primario; vai pro fallback se ainda nao foi.
            fallback_used = True

        _audit_llm_call(
            feature=feature,
            model=used_model,
            provider=self._provider.info.name,
            offline=False,
            latency_s=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            fallback_used=fallback_used,
            extra={"streaming": True, "error": str(last_exc) if last_exc else "unknown"},
        )
        assert last_exc is not None
        raise last_exc


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


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

_LLM_LOG_PATH = BACKEND_DIR / "logs" / "llm_calls.jsonl"


async def _real_stream(
    *,
    settings: Settings,
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int,
    temperature: float,
    timeout_s: float,
) -> AsyncIterator[str]:
    """Streaming real via AsyncOpenAI apontando para o base_url do provider."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.llm_api_key or "no-key",
        base_url=settings.llm_base_url,
        timeout=timeout_s,
        max_retries=0,
        default_headers={
            "HTTP-Referer": "audit-diesel-poc",
            "X-Title": "Audit Diesel POC",
        },
    )
    stream = await client.chat.completions.create(  # type: ignore[call-overload]
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        stream_options={"include_usage": True},
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        text = getattr(delta, "content", None)
        if text:
            yield text


async def _offline_stream(messages: list[ChatMessage]) -> AsyncIterator[str]:
    """Replay determinisitico para AUDIT_AI_OFFLINE=1.

    Encontra a primeira system message com `[task:<name>]` e gera chunks a
    partir de um texto generico curto. O caller (orquestrador) tipicamente ja
    tem o conteudo final cacheado e usa esse stream apenas para narrar.
    """
    task = "stream"
    for m in messages:
        if m.role == "system" and "[task:" in m.content:
            idx = m.content.find("[task:")
            end = m.content.find("]", idx)
            if end > idx:
                task = m.content[idx + 6 : end]
            break
    canned = _OFFLINE_TEXTS.get(task, _OFFLINE_TEXTS["stream"])
    # Quebra em pedacos pequenos (5-10 chars) para simular tipagem natural.
    chunk_size = 6
    for i in range(0, len(canned), chunk_size):
        yield canned[i : i + chunk_size]
        await asyncio.sleep(0.025)


_OFFLINE_TEXTS: dict[str, str] = {
    "stream": (
        "Análise determinística em modo offline. Indicadores carregados, "
        "alertas processados conforme regras §4 do escopo. Sem chamada de "
        "rede ao provider externo."
    ),
    "parecer": (
        "**Resultado**\nResultado calculado a partir dos indicadores §4 do "
        "escopo.\n\n**Causa mais provável**\nAvaliação baseada nos alertas "
        "disparados pelo engine determinístico.\n\n**Recomendação ao "
        "auditor**\nRevise os alertas listados e proceda conforme procedimento "
        "operacional padrão.\n\n**Risco financeiro associado**\nValor "
        "consolidado conforme campo `impacto_total_alertas_brl`."
    ),
    "reconciliacao_narrativa": (
        "Padrões de placa não cadastrada identificados. Os candidatos mais "
        "próximos no GP serão listados a seguir."
    ),
    "outlier_narrativa": (
        "Outlier de consumo detectado. Contexto operacional será avaliado "
        "antes de classificar como anomalia real."
    ),
}


def _audit_llm_call(
    *,
    feature: str,
    model: str,
    provider: str,
    offline: bool,
    latency_s: float,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    fallback_used: bool,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append uma linha jsonl em backend/logs/llm_calls.jsonl.

    Falhas de escrita sao silenciosas - log de auditoria nao deve quebrar o
    fluxo. Diretorio e' criado on-demand.
    """
    try:
        _LLM_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "feature": feature,
            "model": model,
            "provider": provider,
            "offline": offline,
            "latency_s": round(latency_s, 4),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "fallback_used": fallback_used,
        }
        if extra:
            entry["extra"] = extra
        with _LLM_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:  # noqa: BLE001
        log.warning("ai.audit_log.write_failed", error=str(exc))
