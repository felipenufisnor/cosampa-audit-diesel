"""FastAPI app: monta routers, CORS, healthz e exception handlers globais."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from audit_diesel.config import Settings, get_settings
from audit_diesel.ingestion.pipeline import build_engine, init_schema

from .deps import get_app_settings
from .routers import (
    assistente,
    auditorias,
    nfs,
    padroes,
    reconciliacao,
    stats,
    stream,
)
from .schemas import HealthzResponse


@dataclass
class _AssistantHealth:
    status: str
    reason: str
    can_answer_free_text: bool
    has_cached_answers: bool


_AI_PROBE_CACHE: dict[str, tuple[float, bool, str]] = {}
_AI_PROBE_TTL_S = 30.0


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


def create_app() -> FastAPI:
    """Factory do FastAPI app, usado pelo uvicorn e por testes."""
    _configure_logging()
    settings = get_settings()

    app = FastAPI(
        title="audit-diesel API",
        description=(
            "API da POC de auditoria de diesel. Engine deterministica (Dia 1) "
            "+ camada de IA provider-agnostica (OpenAI-compatible)."
        ),
        version="0.2.0",
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(stats.router)
    app.include_router(nfs.router)
    app.include_router(auditorias.router)
    app.include_router(reconciliacao.router)
    app.include_router(stream.router)
    app.include_router(padroes.router)
    app.include_router(assistente.router)

    @app.get("/healthz", response_model=HealthzResponse, tags=["meta"])
    def healthz(s: Settings = Depends(get_app_settings)) -> HealthzResponse:
        engine = build_engine()
        try:
            init_schema(engine)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_state = "connected"
        except Exception:  # noqa: BLE001
            db_state = "error"

        # AI probe.
        from audit_diesel.ai.client import ChatClient  # noqa: PLC0415
        client = ChatClient()
        provider = client.provider.info
        assistant = _assistant_health(s)
        ai_state = assistant.status

        return HealthzResponse(
            status="ok",
            db=db_state,
            ai=ai_state,
            provider=provider.name,
            model=provider.model,
            fallback_model=s.llm_fallback_model,
            offline=provider.offline,
            demo_mode=s.demo_replay,
            assistant_status=assistant.status,
            assistant_reason=assistant.reason,
            assistant_can_answer_free_text=assistant.can_answer_free_text,
            assistant_has_cached_answers=assistant.has_cached_answers,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        log = structlog.get_logger("audit_diesel.api")
        log.error(
            "api.unhandled_error",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            error_type=exc.__class__.__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Erro interno. Veja logs do servidor para detalhes.",
                "type": exc.__class__.__name__,
            },
        )

    return app


app = create_app()


def _assistant_health(settings: Settings) -> _AssistantHealth:
    from audit_diesel.ai.assistente import existe_cache_assistente  # noqa: PLC0415
    from audit_diesel.ai.client import ChatClient, ChatMessage  # noqa: PLC0415

    has_cache = existe_cache_assistente()
    base_local = (
        "localhost" in settings.llm_base_url
        or "127.0.0.1" in settings.llm_base_url
    )

    if settings.audit_ai_offline:
        return _AssistantHealth(
            status="offline_fixture",
            reason="IA offline por configuração (AUDIT_AI_OFFLINE=1).",
            can_answer_free_text=False,
            has_cached_answers=has_cache,
        )
    if not settings.llm_api_key and not base_local:
        return _AssistantHealth(
            status="missing_key",
            reason="LLM_API_KEY não configurada para o provider remoto.",
            can_answer_free_text=False,
            has_cached_answers=has_cache,
        )

    cache_key = "|".join([
        settings.llm_provider,
        settings.llm_base_url,
        settings.llm_model,
        settings.llm_fallback_model or "",
        "key" if settings.llm_api_key else "local",
    ])
    now = time.monotonic()
    cached = _AI_PROBE_CACHE.get(cache_key)
    if cached and now - cached[0] < _AI_PROBE_TTL_S:
        ok, reason = cached[1], cached[2]
    else:
        try:
            probe_settings = settings.model_copy(
                update={
                    "llm_request_timeout_s": min(settings.llm_request_timeout_s, 5.0),
                    "llm_max_retries": 0,
                }
            )
            probe = ChatClient(settings=probe_settings)
            probe.chat(
                messages=[
                    ChatMessage(
                        role="user",
                        content="Responda apenas OK para healthcheck.",
                    )
                ],
                temperature=0,
                max_tokens=4,
            )
            ok = True
            reason = "Provider de IA disponível."
        except Exception as exc:  # noqa: BLE001
            ok = False
            reason = f"Provider de IA indisponível: {exc.__class__.__name__}."
        _AI_PROBE_CACHE[cache_key] = (now, ok, reason)

    if ok:
        return _AssistantHealth(
            status="available",
            reason=reason,
            can_answer_free_text=True,
            has_cached_answers=has_cache,
        )
    return _AssistantHealth(
        status="degraded_cache" if has_cache else "provider_error",
        reason=reason,
        can_answer_free_text=False,
        has_cached_answers=has_cache,
    )
