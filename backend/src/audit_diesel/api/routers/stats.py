"""GET /stats: numeros agregados para o dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from audit_diesel.models import Abastecimento, Checklist, Mobilizado

from ..deps import get_session
from ..schemas import StatsResponse

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
def stats(session: Session = Depends(get_session)) -> StatsResponse:
    """Retorna estatisticas globais usadas pelos cards do dashboard."""
    total_ab = session.exec(select(func.count()).select_from(Abastecimento)).one()
    total_litros = session.exec(select(func.sum(Abastecimento.quantidade_litros))).one() or 0.0
    total_custo = session.exec(select(func.sum(Abastecimento.custo_total))).one() or 0.0
    periodo_min = session.exec(select(func.min(Abastecimento.data))).one()
    periodo_max = session.exec(select(func.max(Abastecimento.data))).one()
    periodo_nfs_min = session.exec(select(func.min(Checklist.data_recebimento))).one()
    periodo_nfs_max = session.exec(select(func.max(Checklist.data_recebimento))).one()

    total_nfs = session.exec(select(func.count()).select_from(Checklist)).one()
    total_mob = session.exec(select(func.count()).select_from(Mobilizado)).one()
    mob_ativos = session.exec(
        select(func.count()).select_from(Mobilizado).where(Mobilizado.situacao == "MOBILIZADO")
    ).one()

    placas_cadastradas = {
        m for m in session.exec(select(Mobilizado.placa_ativo_normalizada)).all() if m
    }
    abastecimentos = session.exec(select(Abastecimento)).all()
    veiculos_distintos = len({a.veiculo_normalizado for a in abastecimentos})
    nao_cad = [a for a in abastecimentos if a.veiculo_normalizado not in placas_cadastradas]
    custo_nao_cad = sum(a.custo_total for a in nao_cad)
    pct = (custo_nao_cad / total_custo * 100.0) if total_custo else 0.0

    return StatsResponse(
        total_abastecimentos=int(total_ab or 0),
        total_litros=round(float(total_litros), 2),
        total_custo_brl=round(float(total_custo), 2),
        periodo_inicio=periodo_min.date() if periodo_min else None,
        periodo_fim=periodo_max.date() if periodo_max else None,
        periodo_nfs_inicio=periodo_nfs_min.date() if periodo_nfs_min else None,
        periodo_nfs_fim=periodo_nfs_max.date() if periodo_nfs_max else None,
        total_nfs=int(total_nfs or 0),
        total_mobilizados=int(total_mob or 0),
        mobilizados_ativos=int(mob_ativos or 0),
        veiculos_distintos_infleet=veiculos_distintos,
        abastecimentos_nao_cadastrados=len(nao_cad),
        custo_nao_cadastrado_brl=round(custo_nao_cad, 2),
        pct_custo_nao_cadastrado=round(pct, 2),
    )
