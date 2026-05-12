"""POST /auditorias/{id}/perguntar (SSE) + GET /auditorias/{id}/mensagens.

Feature B da v2 - Assistente de Investigacao.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from audit_diesel.ai.assistente import perguntas_cacheadas_para_auditoria, stream_pergunta
from audit_diesel.ai.client import ChatClient
from audit_diesel.models import Auditoria, MensagemAssistente

from ..deps import get_chat_client, get_session

router = APIRouter(tags=["assistente"])


class PerguntarRequest(BaseModel):
    pergunta: str


class MensagemItem(BaseModel):
    id: int
    papel: str
    conteudo: str
    criada_em: datetime


class HistoricoResponse(BaseModel):
    auditoria_id: int
    mensagens: list[MensagemItem]


class PerguntaSugerida(BaseModel):
    """Pergunta que tem resposta disponivel sem precisar do servico de IA."""

    pergunta: str
    cacheada: bool


class PerguntasSugeridasResponse(BaseModel):
    auditoria_id: int
    perguntas: list[PerguntaSugerida]


@router.post("/auditorias/{auditoria_id}/perguntar")
def perguntar(
    auditoria_id: int,
    body: PerguntarRequest,
    session: Session = Depends(get_session),
    chat: ChatClient = Depends(get_chat_client),
) -> StreamingResponse:
    """Stream SSE com a resposta + tool calls."""
    if session.get(Auditoria, auditoria_id) is None:
        raise HTTPException(status_code=404, detail=f"Auditoria {auditoria_id} nao encontrada.")
    return StreamingResponse(
        stream_pergunta(
            session=session,
            auditoria_id=auditoria_id,
            pergunta=body.pergunta,
            chat=chat,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/auditorias/{auditoria_id}/perguntas-sugeridas",
    response_model=PerguntasSugeridasResponse,
)
def listar_perguntas_sugeridas(
    auditoria_id: int,
    session: Session = Depends(get_session),
) -> PerguntasSugeridasResponse:
    """Perguntas que tem resposta pre-cacheada para esta auditoria.

    O frontend usa isso para mostrar chips "respondem mesmo offline" no
    rodape do drawer. Quando o cache nao existe, a lista vem vazia — a UI
    deve degradar para texto informando que o assistente exige IA ativa.
    """
    auditoria = session.get(Auditoria, auditoria_id)
    if auditoria is None:
        raise HTTPException(
            status_code=404, detail=f"Auditoria {auditoria_id} nao encontrada."
        )

    perguntas = [
        PerguntaSugerida(pergunta=p, cacheada=True)
        for p in perguntas_cacheadas_para_auditoria(auditoria)
    ]

    return PerguntasSugeridasResponse(
        auditoria_id=auditoria_id, perguntas=perguntas
    )


@router.get(
    "/auditorias/{auditoria_id}/mensagens",
    response_model=HistoricoResponse,
)
def listar_mensagens(
    auditoria_id: int,
    session: Session = Depends(get_session),
) -> HistoricoResponse:
    """Historico persistido do chat para uma auditoria."""
    if session.get(Auditoria, auditoria_id) is None:
        raise HTTPException(status_code=404, detail=f"Auditoria {auditoria_id} nao encontrada.")
    msgs = list(session.exec(
        select(MensagemAssistente)
        .where(MensagemAssistente.auditoria_id == auditoria_id)
        .order_by(MensagemAssistente.criada_em)
    ).all())
    return HistoricoResponse(
        auditoria_id=auditoria_id,
        mensagens=[
            MensagemItem(
                id=m.id or 0,
                papel=m.papel,
                conteudo=m.conteudo,
                criada_em=m.criada_em,
            )
            for m in msgs
        ],
    )
