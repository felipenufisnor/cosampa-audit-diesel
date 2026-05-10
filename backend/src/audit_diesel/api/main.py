"""FastAPI app: monta routers, CORS, healthz e exception handlers globais."""

from __future__ import annotations

import logging

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from audit_diesel.config import Settings, get_settings
from audit_diesel.ingestion.pipeline import build_engine, init_schema

from .deps import get_app_settings
from .routers import auditorias, nfs, reconciliacao, stats
from .schemas import HealthzResponse


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
        if provider.offline:
            ai_state = "offline_fixture"
        elif s.llm_api_key:
            ai_state = "configured"
        else:
            ai_state = "missing_key"

        return HealthzResponse(
            status="ok",
            db=db_state,
            ai=ai_state,
            provider=provider.name,
            model=provider.model,
            fallback_model=s.llm_fallback_model,
            offline=provider.offline,
            demo_mode=s.demo_replay,
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
