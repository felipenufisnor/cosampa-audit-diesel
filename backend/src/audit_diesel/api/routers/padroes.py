"""GET /padroes e POST /padroes/recalcular (Feature C da v2)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from audit_diesel.ai.client import ChatClient
from audit_diesel.ai.padroes import analisar_padroes, gerar_padroes_em_memoria
from audit_diesel.models import Abastecimento, Auditoria, Checklist, PadraoDetectado

from ..deps import get_chat_client, get_session

router = APIRouter(prefix="/padroes", tags=["padroes"])


class PadraoItem(BaseModel):
    """Padrao serializado para o frontend."""

    id: int
    tipo: str
    titulo: str
    descricao: str
    severidade: str
    dados: dict[str, Any] = Field(default_factory=dict)
    criado_em: datetime
    auditoria_alvo_id: int | None = None
    auditoria_alvo_nf: str | None = None


class PadroesResponse(BaseModel):
    """GET /padroes."""

    padroes: list[PadraoItem]
    atualizado_em: datetime | None


class RecalcularResponse(BaseModel):
    """POST /padroes/recalcular."""

    n_candidatos: int
    n_padroes: int
    provider: str
    modelo: str | None
    offline: bool


@router.get("", response_model=PadroesResponse)
def listar_padroes(session: Session = Depends(get_session)) -> PadroesResponse:
    """Retorna o snapshot persistido ou calcula padrões reais sob demanda."""
    rows = list(session.exec(
        select(PadraoDetectado).order_by(PadraoDetectado.criado_em.desc())
    ).all())
    if not rows:
        rows = gerar_padroes_em_memoria(session)
    itens = [_to_item(r, session) for r in rows]
    atualizado = rows[0].criado_em if rows else None
    return PadroesResponse(padroes=itens, atualizado_em=atualizado)


@router.post("/recalcular", response_model=RecalcularResponse)
def recalcular_padroes(
    session: Session = Depends(get_session),
    chat: ChatClient = Depends(get_chat_client),
) -> RecalcularResponse:
    """Reroda a analise proativa: coleta candidatos, narra via LLM, persiste."""
    resultado = analisar_padroes(session, chat=chat)
    return RecalcularResponse(
        n_candidatos=resultado.n_candidatos,
        n_padroes=len(resultado.padroes),
        provider=resultado.provider,
        modelo=resultado.modelo,
        offline=resultado.offline,
    )


def _to_item(r: PadraoDetectado, session: Session) -> PadraoItem:
    try:
        dados = json.loads(r.dados_json) if r.dados_json else {}
    except json.JSONDecodeError:
        dados = {}
    auditoria_alvo = _resolver_auditoria_alvo(session, r.tipo, dados)
    return PadraoItem(
        id=r.id or 0,
        tipo=r.tipo,
        titulo=r.titulo,
        descricao=r.descricao,
        severidade=r.severidade,
        dados=dados,
        criado_em=r.criado_em,
        auditoria_alvo_id=int(auditoria_alvo.id) if auditoria_alvo and auditoria_alvo.id else None,
        auditoria_alvo_nf=auditoria_alvo.nf_atual if auditoria_alvo else None,
    )


def _resolver_auditoria_alvo(
    session: Session,
    tipo: str,
    dados: dict[str, Any],
) -> Auditoria | None:
    """Escolhe a auditoria que o Assistente deve abrir para investigar um padrão."""
    direto = _int_or_none(dados.get("auditoria_id"))
    if direto is not None:
        return session.get(Auditoria, direto)

    top_diferencas = dados.get("top_diferencas")
    if isinstance(top_diferencas, list):
        for item in top_diferencas:
            if not isinstance(item, dict):
                continue
            auditoria = session.get(Auditoria, _int_or_none(item.get("auditoria_id")))
            if auditoria is not None:
                return auditoria

    evidencia_ids = _ids_de_evidencia(dados)
    if not evidencia_ids:
        return None

    if tipo in {"nao_cadastrado_recorrente", "diferenca_saidas_alta"}:
        for eid in evidencia_ids:
            auditoria = session.get(Auditoria, eid)
            if auditoria is not None:
                return auditoria
        return None

    return _auditoria_por_abastecimentos(session, evidencia_ids)


def _ids_de_evidencia(dados: dict[str, Any]) -> list[int]:
    ids: list[int] = []
    for key in ("abastecimento_ids", "evidencia_ids"):
        value = dados.get(key)
        if isinstance(value, list):
            ids.extend(i for i in (_int_or_none(v) for v in value) if i is not None)
    return ids


def _auditoria_por_abastecimentos(
    session: Session,
    abastecimento_ids: list[int],
) -> Auditoria | None:
    abastecimentos = [
        a
        for a in (session.get(Abastecimento, aid) for aid in abastecimento_ids)
        if a is not None
    ]
    if not abastecimentos:
        return None

    checklists = {
        c.nota_fiscal: c
        for c in session.exec(select(Checklist)).all()
    }
    melhor: tuple[int, datetime, int, Auditoria] | None = None
    for auditoria in session.exec(select(Auditoria)).all():
        ck_ant = checklists.get(auditoria.nf_anterior)
        ck_atual = checklists.get(auditoria.nf_atual)
        if ck_ant is None or ck_atual is None:
            continue
        count = sum(
            1
            for ab in abastecimentos
            if ck_ant.datetime_fim_descarga <= ab.data < ck_atual.datetime_fim_descarga
        )
        if count <= 0:
            continue
        candidato = (count, auditoria.criada_em, int(auditoria.id or 0), auditoria)
        if melhor is None or candidato[:3] > melhor[:3]:
            melhor = candidato
    return melhor[3] if melhor else None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
