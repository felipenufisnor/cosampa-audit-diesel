"""POST /reconciliacao/sugerir e POST /reconciliacao/aprovar."""

from __future__ import annotations

import difflib
import re
import unicodedata
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
    ContextoReconciliacaoResponse,
    HistoricoReconciliacaoItemSchema,
    MatchAproximadoSchema,
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
    """Pede ao LLM sugestões de reconciliação para abastecimentos NAO_CADASTRADO."""
    if session.get(Auditoria, body.auditoria_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Auditoria {body.auditoria_id} não encontrada.",
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
        raise HTTPException(status_code=404, detail="Abastecimento não encontrado.")
    if session.get(Mobilizado, body.mobilizado_id) is None:
        raise HTTPException(status_code=404, detail="Mobilizado não encontrado.")

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
            auditoria_atualizada = _to_response(nova, parecer_meta=None, session=session)

    return AprovarReconciliacaoResponse(
        status="ok",
        reconciliacao_id=int(rec.id or 0),
        auditoria_atualizada=auditoria_atualizada,
    )


# --------------------------------------------------------------------------- #
# Contexto determinístico (fallback quando a IA não retorna candidato) — AI-09
# --------------------------------------------------------------------------- #


_NORM_RE = re.compile(r"[\s\.\-/]")


def _norm(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return _NORM_RE.sub("", s).upper()


def _candidato_schema(m: Mobilizado) -> CandidatoGPSchema:
    return CandidatoGPSchema(
        id=int(m.id or 0),
        placa_ativo=m.placa_ativo_raw,
        placa_ativo_normalizada=m.placa_ativo_normalizada,
        equipamento=m.equipamento,
        marca=m.marca,
        modelo=m.modelo,
        tipo_equipamento=m.tipo_equipamento,
        capacidade_litros=m.capacidade_litros,
        situacao=m.situacao,
    )


def _matches_aproximados(
    ab: Abastecimento, candidatos: list[Mobilizado], limit: int = 5
) -> list[MatchAproximadoSchema]:
    """Top N candidatos da mesma obra ranqueados por similaridade textual.

    Heurística determinística (sem LLM): combina razão de SequenceMatcher
    contra placa normalizada e contra apelido/equipamento, com bônus quando
    há substring direta.
    """
    alvo_placa = _norm(ab.veiculo_raw)
    alvo_apelido = _norm(ab.apelido)
    scored: list[tuple[float, str, Mobilizado]] = []
    for c in candidatos:
        placa = c.placa_ativo_normalizada or _norm(c.placa_ativo_raw)
        equip = _norm(c.equipamento)
        marca = _norm(c.marca)
        modelo = _norm(c.modelo)

        razao_placa = (
            difflib.SequenceMatcher(None, alvo_placa, placa).ratio() if placa else 0.0
        )
        texto_cand = " ".join(filter(None, [equip, marca, modelo]))
        razao_apelido = (
            difflib.SequenceMatcher(None, alvo_apelido, texto_cand).ratio()
            if alvo_apelido and texto_cand
            else 0.0
        )
        bonus = 0.0
        motivo_partes: list[str] = []
        if placa and alvo_placa and (placa in alvo_placa or alvo_placa in placa):
            bonus += 0.2
            motivo_partes.append("placa contém termos do veículo")
        if alvo_apelido and equip and equip in alvo_apelido:
            bonus += 0.15
            motivo_partes.append("equipamento aparece no apelido")
        if alvo_apelido and modelo and modelo in alvo_apelido:
            bonus += 0.1
            motivo_partes.append("modelo aparece no apelido")
        if alvo_apelido and marca and marca in alvo_apelido:
            bonus += 0.05
            motivo_partes.append("marca aparece no apelido")

        score = min(1.0, max(razao_placa, razao_apelido) + bonus)
        if not motivo_partes:
            motivo_partes.append(
                f"similaridade textual {int(score * 100)}% (placa/apelido)"
            )
        if score >= 0.3:
            scored.append((score, "; ".join(motivo_partes), c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        MatchAproximadoSchema(
            candidato=_candidato_schema(c),
            similaridade=round(score, 3),
            motivo=motivo,
        )
        for score, motivo, c in scored[:limit]
    ]


def _historico_para_veiculo(
    session: Session, veiculo_normalizado: str, abastecimento_id_atual: int
) -> list[HistoricoReconciliacaoItemSchema]:
    """Reconciliações aprovadas em outros abastecimentos com o mesmo veículo normalizado."""
    if not veiculo_normalizado:
        return []
    rows = session.exec(
        select(ReconciliacaoAprovada, Mobilizado, Abastecimento)
        .join(Abastecimento, Abastecimento.id == ReconciliacaoAprovada.abastecimento_id)
        .join(Mobilizado, Mobilizado.id == ReconciliacaoAprovada.mobilizado_id)
        .where(Abastecimento.veiculo_normalizado == veiculo_normalizado)
        .where(Abastecimento.id != abastecimento_id_atual)
        .order_by(ReconciliacaoAprovada.criada_em.desc())
    ).all()

    # Deduplica pelo mobilizado: o mesmo veículo pode ter sido reconciliado
    # várias vezes no histórico; mostramos apenas a decisão mais recente
    # por mobilizado para não poluir a UI.
    vistos: set[int] = set()
    out: list[HistoricoReconciliacaoItemSchema] = []
    for rec, mob, _ab in rows:
        if mob.id in vistos:
            continue
        vistos.add(int(mob.id or 0))
        out.append(
            HistoricoReconciliacaoItemSchema(
                reconciliacao_id=int(rec.id or 0),
                criada_em=rec.criada_em,
                auditor=rec.auditor,
                confianca=rec.confianca,
                justificativa=rec.justificativa,
                mobilizado=_candidato_schema(mob),
            )
        )
        if len(out) >= 5:
            break
    return out


@router.get("/contexto", response_model=ContextoReconciliacaoResponse)
def contexto(
    abastecimento_id: int,
    auditoria_id: int,
    session: Session = Depends(get_session),
) -> ContextoReconciliacaoResponse:
    """Contexto determinístico para decisão manual do auditor (achado AI-09).

    Retorna candidatos por similaridade textual (sem LLM) e histórico de
    reconciliações anteriores para o mesmo veículo normalizado. Usado pelo
    modal de reconciliação quando a IA não retorna correspondência.
    """
    ab = session.get(Abastecimento, abastecimento_id)
    if ab is None:
        raise HTTPException(status_code=404, detail="Abastecimento não encontrado.")
    auditoria = session.get(Auditoria, auditoria_id)
    if auditoria is None:
        raise HTTPException(status_code=404, detail="Auditoria não encontrada.")

    candidatos = session.exec(
        select(Mobilizado).where(Mobilizado.nome_obra == auditoria.nome_obra)
    ).all()

    matches = _matches_aproximados(ab, list(candidatos), limit=5)
    historico = _historico_para_veiculo(session, ab.veiculo_normalizado, int(ab.id or 0))

    return ContextoReconciliacaoResponse(
        abastecimento_id=int(ab.id or 0),
        veiculo_raw=ab.veiculo_raw,
        apelido=ab.apelido,
        nome_obra=auditoria.nome_obra,
        termo_busca_sugerido=(ab.apelido or ab.veiculo_raw or "").strip(),
        matches_aproximados=matches,
        historico=historico,
    )
