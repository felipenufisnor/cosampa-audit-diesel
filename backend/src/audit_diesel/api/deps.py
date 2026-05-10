"""Dependencias compartilhadas (Session, ChatClient, settings)."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends
from sqlmodel import Session

from audit_diesel.ai.client import ChatClient
from audit_diesel.config import Settings, get_settings
from audit_diesel.ingestion.pipeline import build_engine, init_schema


@lru_cache(maxsize=1)
def _engine():
    e = build_engine()
    init_schema(e)
    return e


@lru_cache(maxsize=1)
def _chat_client() -> ChatClient:
    """ChatClient singleton; respeita config atual via get_settings()."""
    return ChatClient()


def get_session() -> Iterator[Session]:
    """Yields uma Session ligada ao SQLite em DB_PATH."""
    with Session(_engine()) as session:
        yield session


def get_chat_client() -> ChatClient:
    return _chat_client()


def get_app_settings() -> Settings:
    return get_settings()


SessionDep = Depends(get_session)
ChatClientDep = Depends(get_chat_client)
SettingsDep = Depends(get_app_settings)
