"""Popula o cache offline da v2 (Features A, B, C).

Rode com:
    AUDIT_AI_OFFLINE=0 LLM_API_KEY=... uv run python scripts/popular_cache_v2.py

O script:
  1. Garante AUDIT_AI_OFFLINE=0 (precisa do provider real para gravar cache).
  2. Para cada par de NFs (8108->8187, 8187->8278, 8278->8328):
     a. Roda o reasoning stream e grava todos os eventos SSE em JSON com
        timestamps relativos -> `data/cache/stream_<nf_ant>_<nf_atual>.json`
     b. Para cada auditoria persistida, simula 4 perguntas-chip do
        Assistente e grava as respostas reais (com tool calls executadas) em
        `data/cache/assistente_<auditoria_id>.json`.
  3. Roda o job de padroes proativos uma vez -> grava resultado em
     `data/cache/padroes_global.json` (alem de persistir em SQLite).
  4. Valida arquivos gerados (>0 bytes) e imprime resumo.

Apos rodar uma vez, o backend pode subir com AUDIT_AI_OFFLINE=1 e respondera
a partir do cache (Feature B) + heuristicas Python (Features A/C).

Idempotente: pode ser rodado quantas vezes quiser (sobrescreve o cache).

NOTA: Features A e C funcionam offline mesmo sem este script (o orquestrador
de streaming usa engine + parecer determinisitico; padroes usam heuristicas
Python diretas). O script existe principalmente para:
  - registrar timings reais do streaming online (auditoria que pode ser
    inspecionada/comparada);
  - popular respostas concretas para os chips do Assistente (que offline
    falham com fallback honesto se o cache nao existir).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# IMPORTANTE: nao force offline aqui. O ponto do script e' justamente
# capturar respostas REAIS do provider para servir como cache no modo
# offline subsequente.
os.environ.setdefault("AUDIT_AI_OFFLINE", "0")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqlmodel import Session  # noqa: E402

from audit_diesel.ai.assistente import (  # noqa: E402
    salvar_cache_chip,
    stream_pergunta,
)
from audit_diesel.ai.client import ChatClient  # noqa: E402
from audit_diesel.ai.padroes import analisar_padroes  # noqa: E402
from audit_diesel.ai.streaming import stream_auditoria  # noqa: E402
from audit_diesel.api.deps import _engine  # noqa: E402
from audit_diesel.ingestion.pipeline import init_schema  # noqa: E402
from audit_diesel.models import Auditoria  # noqa: E402

CACHE_DIR = ROOT / "data" / "cache"

PARES_DEMO: list[tuple[str, str]] = [
    ("8108", "8187"),
    ("8187", "8278"),
    ("8278", "8328"),
]

CHIP_PERGUNTAS = [
    "Quais veiculos nao estao cadastrados nesta NF?",
    "Compare o consumo desta NF com a NF anterior",
    "Qual o impacto financeiro dos alertas desta auditoria?",
    "Existe algum padrao suspeito nesta auditoria?",
]


def _print(*args: object) -> None:
    print(" ".join(str(a) for a in args), flush=True)


async def gravar_stream_cache(
    chat: ChatClient,
    nf_anterior: str,
    nf_atual: str,
) -> tuple[Path, int]:
    """Roda stream_auditoria e grava eventos com timestamps em JSON."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    eventos: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    engine = _engine()
    with Session(engine) as session:
        async for sse_line in stream_auditoria(
            session=session,
            nf_anterior=nf_anterior,
            nf_atual=nf_atual,
            chat=chat,
        ):
            corpo = sse_line.split("data: ", 1)[1].strip()
            try:
                obj = json.loads(corpo)
            except json.JSONDecodeError:
                continue
            eventos.append({
                "t_ms": int((time.perf_counter() - t0) * 1000),
                **obj,
            })
    path = CACHE_DIR / f"stream_{nf_anterior}_{nf_atual}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump({"nf_anterior": nf_anterior, "nf_atual": nf_atual, "eventos": eventos}, fh,
                  ensure_ascii=False, indent=2)
    return path, len(eventos)


async def gravar_chip_cache(
    chat: ChatClient,
    auditoria_id: int,
    pergunta: str,
) -> int:
    """Roda uma pergunta-chip e grava a resposta no cache."""
    resposta_chunks: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    engine = _engine()
    with Session(engine) as session:
        async for sse_line in stream_pergunta(
            session=session,
            auditoria_id=auditoria_id,
            pergunta=pergunta,
            chat=chat,
        ):
            corpo = sse_line.split("data: ", 1)[1].strip()
            try:
                obj = json.loads(corpo)
            except json.JSONDecodeError:
                continue
            ev = obj.get("event")
            pl = obj.get("payload") or {}
            if ev == "assistant_chunk":
                resposta_chunks.append(str(pl.get("texto") or ""))
            elif ev == "tool_call_started":
                tool_calls.append({
                    "nome": pl.get("nome", ""),
                    "argumentos": pl.get("argumentos") or {},
                    "resultado_resumo": "",
                })
            elif ev == "tool_call_completed" and tool_calls:
                # Anexa resumo na ultima tool_call iniciada.
                for tc in reversed(tool_calls):
                    if tc.get("nome") == pl.get("nome") and not tc.get("resultado_resumo"):
                        tc["resultado_resumo"] = str(pl.get("resultado_resumo") or "")
                        break
    resposta = "".join(resposta_chunks).strip()
    if not resposta:
        return 0
    with Session(engine) as session:
        auditoria = session.get(Auditoria, auditoria_id)
    salvar_cache_chip(
        auditoria_id,
        pergunta,
        resposta,
        tool_calls=tool_calls,
        nf_anterior=auditoria.nf_anterior if auditoria else None,
        nf_atual=auditoria.nf_atual if auditoria else None,
    )
    return len(resposta)


def gravar_padroes_cache() -> tuple[Path, int]:
    """Roda o job de padroes e exporta o resultado para JSON."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    engine = _engine()
    with Session(engine) as session:
        resultado = analisar_padroes(session)
        export = {
            "atualizado_em": resultado.padroes[0].criado_em.isoformat() if resultado.padroes else None,
            "n_candidatos": resultado.n_candidatos,
            "provider": resultado.provider,
            "modelo": resultado.modelo,
            "offline": resultado.offline,
            "padroes": [
                {
                    "id": p.id,
                    "tipo": p.tipo,
                    "titulo": p.titulo,
                    "descricao": p.descricao,
                    "severidade": p.severidade,
                    "dados_json": p.dados_json,
                    "criado_em": p.criado_em.isoformat(),
                }
                for p in resultado.padroes
            ],
        }
    path = CACHE_DIR / "padroes_global.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(export, fh, ensure_ascii=False, indent=2)
    return path, len(export["padroes"])


async def main() -> int:
    init_schema(_engine())
    chat = ChatClient()
    online = not chat.provider.info.offline
    _print(f"[v2-cache] provider: {chat.provider.info.name} (offline={chat.provider.info.offline})")
    _print(f"[v2-cache] cache dir: {CACHE_DIR}")
    if not online:
        _print(
            "[v2-cache] AVISO: provider esta em modo offline. O cache vai "
            "gravar respostas determinisitcas (mesmas que offline ja geraria). "
            "Para capturar respostas reais do LLM, rode com "
            "AUDIT_AI_OFFLINE=0 + LLM_API_KEY=...",
        )

    erros: list[str] = []
    t_global = time.perf_counter()

    # 1) Reasoning stream para cada par de NFs (Feature A).
    for nf_anterior, nf_atual in PARES_DEMO:
        _print(f"\n[v2-cache] streaming {nf_anterior} -> {nf_atual}")
        try:
            path, n = await gravar_stream_cache(chat, nf_anterior, nf_atual)
            _print(f"  ok ({n} eventos) -> {path.relative_to(ROOT)}")
        except Exception as exc:  # noqa: BLE001
            erros.append(f"stream {nf_anterior}->{nf_atual}: {exc}")
            _print(f"  ERRO: {exc}")

    # 2) Chip Q&A para cada auditoria recem-criada (Feature B).
    engine = _engine()
    with Session(engine) as session:
        audits = list(session.exec(
            __import__("sqlmodel").select(Auditoria).order_by(Auditoria.id.desc())  # type: ignore[attr-defined]
        ).all())
    audits_relevantes = audits[: len(PARES_DEMO)]
    for a in audits_relevantes:
        if a.id is None:
            continue
        _print(f"\n[v2-cache] chips para auditoria {a.id} (NF {a.nf_atual})")
        for pergunta in CHIP_PERGUNTAS:
            try:
                tam = await gravar_chip_cache(chat, a.id, pergunta)
                _print(f"  ok ({tam} chars) - {pergunta[:50]}")
            except Exception as exc:  # noqa: BLE001
                erros.append(f"chip {a.id}/{pergunta[:30]}: {exc}")
                _print(f"  ERRO: {exc}")

    # 3) Padroes proativos (Feature C).
    _print("\n[v2-cache] padroes proativos")
    try:
        path, n = gravar_padroes_cache()
        _print(f"  ok ({n} padroes) -> {path.relative_to(ROOT)}")
    except Exception as exc:  # noqa: BLE001
        erros.append(f"padroes: {exc}")
        _print(f"  ERRO: {exc}")

    # 4) Validacao final.
    _print("\n[v2-cache] validando arquivos gerados:")
    arquivos_esperados = (
        [CACHE_DIR / f"stream_{a}_{b}.json" for a, b in PARES_DEMO]
        + [CACHE_DIR / f"assistente_{a.id}.json" for a in audits_relevantes if a.id]
        + [CACHE_DIR / "padroes_global.json"]
    )
    for p in arquivos_esperados:
        if p.exists() and p.stat().st_size > 0:
            _print(f"  ok {p.relative_to(ROOT)} ({p.stat().st_size} bytes)")
        else:
            erros.append(f"arquivo faltando/vazio: {p}")
            _print(f"  FALTA {p}")

    dt = time.perf_counter() - t_global
    _print(f"\n[v2-cache] concluido em {dt:.1f}s. erros: {len(erros)}")
    for e in erros:
        _print(f"  - {e}")
    return 0 if not erros else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
