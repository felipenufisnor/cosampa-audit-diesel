"""POST /reconciliacao/sugerir e POST /reconciliacao/aprovar."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from audit_diesel.ai.client import ChatClient
from audit_diesel.ai.reconciliador import ReconciliadorSemantico
from audit_diesel.audit.engine import AuditEngine, AuditoriaCompleta
from audit_diesel.models import Abastecimento, Alerta, Auditoria, Mobilizado, ReconciliacaoAprovada

from ..deps import get_chat_client, get_session
from ..schemas import (
    AlertaResponse,
    AprovarReconciliacaoRequest,
    AprovarReconciliacaoResponse,
    AuditoriaCompletaResponse,
    AuditoriaIndicadores,
    CandidatoGPSchema,
    SugerirReconciliacaoRequest,
    SugerirReconciliacaoResponse,
    SugestaoSchema,
)
from .auditorias import _to_response  # reuso do mapeamento

router = APIRouter(tags=["reconciliacao"], prefix="/reconciliacao")


@router.post("/sugerir", response_model=SugerirReconciliacaoResponse)
def sugerir(
    body: SugerirReconciliacaoRequest,
    session: Session = Depends(get_session),
    chat: ChatClient = Depends(get_chat_client),
) -> SugerirReconciliacaoResponse:
    """Pede ao LLM sugestoes de reconciliacao para abastecimentos NAO_CADASTRADO."""
    if session.get(Auditoria, body.auditoria_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Auditoria {body.auditoria_id} nao encontrada.",
        )
    rec = ReconciliadorSemantico(session=session, client=chat)
    sugestoes = rec.sugerir_para_auditoria(body.auditoria_id)

    out: list[SugestaoSchema] = []
    for s in sugestoes:
        cand = None
        if s.candidato_gp is not None:
            cand = CandidatoGPSchema(
                id=int(s.candidato_gp["id"]),
                placa_ativo=str(s.candidato_gp["placa_ativo_raw"]),
                placa_ativo_normalizada=str(s.candidato_gp["placa_ativo_normalizada"]),
                equipamento=s.candidato_gp.get("equipamento"),
                marca=s.candidato_gp.get("marca"),
                modelo=s.candidato_gp.get("modelo"),
                tipo_equipamento=s.candidato_gp.get("tipo_equipamento"),
                capacidade_litros=s.candidato_gp.get("capacidade_litros"),
                situacao=str(s.candidato_gp.get("situacao") or ""),
            )
        out.append(
            SugestaoSchema(
                abastecimento_id=s.abastecimento_id,
                veiculo_infleet=s.veiculo_infleet,
                apelido_infleet=s.apelido_infleet,
                candidato_gp=cand,
                confianca=s.confianca,
                justificativa=s.justificativa,
            )
        )
    info = chat.provider.info
    return SugerirReconciliacaoResponse(
        sugestoes=out,
        provider=info.name,
        offline=info.offline,
    )


@router.post("/aprovar", response_model=AprovarReconciliacaoResponse)
def aprovar(
    body: AprovarReconciliacaoRequest,
    session: Session = Depends(get_session),
) -> AprovarReconciliacaoResponse:
    """Cria o vinculo aprovado e re-roda a auditoria associada para refletir o ajuste."""
    if session.get(Abastecimento, body.abastecimento_id) is None:
        raise HTTPException(status_code=404, detail="Abastecimento nao encontrado.")
    if session.get(Mobilizado, body.mobilizado_id) is None:
        raise HTTPException(status_code=404, detail="Mobilizado nao encontrado.")

    rec = ReconciliacaoAprovada(
        abastecimento_id=body.abastecimento_id,
        mobilizado_id=body.mobilizado_id,
        auditor=body.auditor,
        confianca=body.confianca,
        justificativa=body.justificativa,
        criada_em=datetime.now(),
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)

    auditoria_atualizada: AuditoriaCompletaResponse | None = None
    if body.auditoria_id is not None:
        velha = session.get(Auditoria, body.auditoria_id)
        if velha is not None:
            nf_ant = velha.nf_anterior
            nf_atu = velha.nf_atual
            # Apaga a auditoria velha + alertas para evitar acumulo.
            for al in session.exec(
                select(Alerta).where(Alerta.auditoria_id == velha.id)
            ).all():
                session.delete(al)
            session.delete(velha)
            session.commit()
            engine = AuditEngine(session)
            nova: AuditoriaCompleta = engine.auditar(nf_ant, nf_atu)
            auditoria_atualizada = _to_response(nova, parecer_meta=None)

    return AprovarReconciliacaoResponse(
        status="ok",
        reconciliacao_id=int(rec.id or 0),
        auditoria_atualizada=auditoria_atualizada,
    )
