"""GET /nfs e GET /nfs/{nota_fiscal}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from audit_diesel.models import Auditoria, Checklist

from ..deps import get_session
from ..schemas import AuditoriaResumo, NFDetail, NFListItem

router = APIRouter(tags=["nfs"])


@router.get("/nfs", response_model=list[NFListItem])
def listar_nfs(session: Session = Depends(get_session)) -> list[NFListItem]:
    """Lista todas as NFs disponiveis com a ultima auditoria associada (se houver)."""
    checklists = session.exec(
        select(Checklist).order_by(Checklist.data_recebimento)
    ).all()
    items: list[NFListItem] = []
    for c in checklists:
        ultima = session.exec(
            select(Auditoria)
            .where(Auditoria.nf_atual == c.nota_fiscal)
            .order_by(Auditoria.criada_em.desc())
        ).first()
        items.append(
            NFListItem(
                nota_fiscal=c.nota_fiscal,
                data_recebimento=c.data_recebimento.date(),
                nome_obra=c.nome_obra,
                valor_total=c.valor_total_nf,
                qtd_litros=c.quantidade_nf_litros,
                ultima_auditoria_id=ultima.id if ultima else None,
                ultima_validacao=ultima.validacao_final if ultima else None,
            )
        )
    return items


@router.get("/nfs/{nota_fiscal}/auditorias", response_model=list[AuditoriaResumo])
def listar_auditorias_da_nf(
    nota_fiscal: str,
    session: Session = Depends(get_session),
) -> list[AuditoriaResumo]:
    """Lista auditorias cuja nf_atual e a NF informada (mais recente primeiro)."""
    if session.exec(
        select(Checklist).where(Checklist.nota_fiscal == nota_fiscal)
    ).first() is None:
        raise HTTPException(status_code=404, detail=f"NF {nota_fiscal} não encontrada.")
    auditorias = session.exec(
        select(Auditoria)
        .where(Auditoria.nf_atual == nota_fiscal)
        .order_by(Auditoria.criada_em.desc())
    ).all()
    return [
        AuditoriaResumo(
            id=int(a.id or 0),
            nf_anterior=a.nf_anterior,
            nf_atual=a.nf_atual,
            nome_obra=a.nome_obra,
            criada_em=a.criada_em,
            validacao_final=a.validacao_final,
            diferenca_percentual=a.diferenca_percentual,
        )
        for a in auditorias
    ]


@router.get("/nfs/{nota_fiscal}", response_model=NFDetail)
def detalhe_nf(nota_fiscal: str, session: Session = Depends(get_session)) -> NFDetail:
    """Retorna o checklist completo + historico de auditorias daquela NF."""
    c = session.exec(
        select(Checklist).where(Checklist.nota_fiscal == nota_fiscal)
    ).first()
    if c is None:
        raise HTTPException(status_code=404, detail=f"NF {nota_fiscal} não encontrada.")
    auditorias = session.exec(
        select(Auditoria)
        .where(
            (Auditoria.nf_atual == nota_fiscal) | (Auditoria.nf_anterior == nota_fiscal)
        )
        .order_by(Auditoria.criada_em.desc())
    ).all()
    return NFDetail(
        nota_fiscal=c.nota_fiscal,
        numero_chamado=c.numero_chamado,
        data_recebimento=c.data_recebimento.date(),
        hora_inicio_descarga=c.hora_inicio_descarga.isoformat(timespec="minutes"),
        hora_final_descarga=c.hora_final_descarga.isoformat(timespec="minutes"),
        nome_obra=c.nome_obra,
        cnpj_fornecedor=c.cnpj_fornecedor,
        quantidade_nf_litros=c.quantidade_nf_litros,
        volume_conferido_litros=c.volume_conferido_litros,
        estoque_antes_tanque_litros=c.estoque_antes_tanque_litros,
        estoque_antes_comboio_litros=c.estoque_antes_comboio_litros,
        preco_unitario=c.preco_unitario,
        valor_total_nf=c.valor_total_nf,
        auditorias_passadas=[
            AuditoriaResumo(
                id=int(a.id or 0),
                nf_anterior=a.nf_anterior,
                nf_atual=a.nf_atual,
                nome_obra=a.nome_obra,
                criada_em=a.criada_em,
                validacao_final=a.validacao_final,
                diferenca_percentual=a.diferenca_percentual,
            )
            for a in auditorias
        ],
    )
