"""Cache de respostas da IA para o modo demonstração.

Motivação: durante a apresentação, latência da API externa, falha de rede
ou variação da resposta do LLM são riscos inaceitáveis. Este módulo grava
em disco as respostas do parecer e da reconciliação indexadas pelos inputs
estáveis (par de NFs, id da auditoria) e devolve-as instantaneamente quando
`DEMO_MODE=true`.

Comportamento por modo:
  - off (default): no-op; tudo passa direto.
  - record: chama o provider normalmente e GRAVA o resultado no cache.
  - true: tenta LER do cache; se não tiver, chama o provider e grava (mais
    flexivel que strict-replay, mantem o sistema funcional fora da demo).

Os arquivos sao JSON simples e legiveis para que o time consiga revisar e
ajustar manualmente o conteudo do cache antes da apresentacao se preciso.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import structlog

from audit_diesel.config import Settings, get_settings

log = structlog.get_logger("audit_diesel.ai.cache")


def _cache_dir(settings: Settings | None = None) -> Path:
    s = settings or get_settings()
    p = s.demo_cache_path
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("demo_cache.invalid_json", path=str(path))
        return None


def _write(path: Path, payload: Any) -> None:
    if is_dataclass(payload):
        data = asdict(payload)
    else:
        data = payload
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


# ----------------------------- Parecer ----------------------------- #


def _parecer_filename(nf_anterior: str, nf_atual: str) -> str:
    return f"parecer_NF_{nf_atual}_anterior_{nf_anterior}.json"


def parecer_path(nf_anterior: str, nf_atual: str, settings: Settings | None = None) -> Path:
    return _cache_dir(settings) / _parecer_filename(nf_anterior, nf_atual)


def get_cached_parecer(
    nf_anterior: str,
    nf_atual: str,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    """Retorna o dict serializado do `ParecerResult` se existir no cache."""
    s = settings or get_settings()
    if not s.demo_replay:
        return None
    cached = _read(parecer_path(nf_anterior, nf_atual, s))
    if cached:
        log.info("demo_cache.hit", kind="parecer", nf_atual=nf_atual)
    return cached


def save_cached_parecer(
    nf_anterior: str,
    nf_atual: str,
    payload: Any,
    settings: Settings | None = None,
) -> None:
    """Persiste o resultado do parecer (sempre que record OU replay-miss)."""
    s = settings or get_settings()
    if not (s.demo_record or s.demo_replay):
        return
    path = parecer_path(nf_anterior, nf_atual, s)
    _write(path, payload)
    log.info("demo_cache.write", kind="parecer", path=str(path.name))


# -------------------------- Reconciliacao ------------------------- #


def _reconciliacao_filename(auditoria_id: int) -> str:
    return f"reconciliacao_auditoria_{auditoria_id}.json"


def reconciliacao_path(auditoria_id: int, settings: Settings | None = None) -> Path:
    return _cache_dir(settings) / _reconciliacao_filename(auditoria_id)


def get_cached_reconciliacao(
    auditoria_id: int,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    s = settings or get_settings()
    if not s.demo_replay:
        return None
    cached = _read(reconciliacao_path(auditoria_id, s))
    if cached:
        log.info("demo_cache.hit", kind="reconciliacao", auditoria_id=auditoria_id)
    return cached


def save_cached_reconciliacao(
    auditoria_id: int,
    payload: Any,
    settings: Settings | None = None,
) -> None:
    s = settings or get_settings()
    if not (s.demo_record or s.demo_replay):
        return
    path = reconciliacao_path(auditoria_id, s)
    _write(path, payload)
    log.info("demo_cache.write", kind="reconciliacao", path=str(path.name))


# Reconciliacao tambem pode ser endereçada por (par de NFs) para o caso
# de a auditoria ter um id diferente entre execucoes (apaga + recria).
def _reconciliacao_par_filename(nf_anterior: str, nf_atual: str) -> str:
    return f"reconciliacao_par_{nf_atual}_anterior_{nf_anterior}.json"


def reconciliacao_par_path(
    nf_anterior: str,
    nf_atual: str,
    settings: Settings | None = None,
) -> Path:
    return _cache_dir(settings) / _reconciliacao_par_filename(nf_anterior, nf_atual)


def get_cached_reconciliacao_par(
    nf_anterior: str,
    nf_atual: str,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    s = settings or get_settings()
    if not s.demo_replay:
        return None
    cached = _read(reconciliacao_par_path(nf_anterior, nf_atual, s))
    if cached:
        log.info(
            "demo_cache.hit",
            kind="reconciliacao_par",
            nf_anterior=nf_anterior,
            nf_atual=nf_atual,
        )
    return cached


def save_cached_reconciliacao_par(
    nf_anterior: str,
    nf_atual: str,
    payload: Any,
    settings: Settings | None = None,
) -> None:
    s = settings or get_settings()
    if not (s.demo_record or s.demo_replay):
        return
    path = reconciliacao_par_path(nf_anterior, nf_atual, s)
    _write(path, payload)
    log.info("demo_cache.write", kind="reconciliacao_par", path=str(path.name))
