"""Tool: historico de abastecimentos + cadastro de um veiculo."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from audit_diesel.ingestion.normalizers import normalizar_placa
from audit_diesel.models import Abastecimento, Mobilizado


def consultar_veiculo(
    session: Session, *, placa: str, dias: int = 28
) -> dict[str, Any]:
    """Historico dos ultimos `dias` para a placa informada."""
    placa_norm = normalizar_placa(placa)
    if not placa_norm:
        return {"erro": "placa invalida"}
    fim = _fim_da_janela(session)
    inicio = fim - timedelta(days=int(dias))
    abas = list(session.exec(
        select(Abastecimento)
        .where(Abastecimento.veiculo_normalizado == placa_norm)
        .where(Abastecimento.data >= inicio)
        .where(Abastecimento.data <= fim)
        .order_by(Abastecimento.data)
    ).all())
    cadastrado = session.exec(
        select(Mobilizado).where(Mobilizado.placa_ativo_normalizada == placa_norm)
    ).first()
    total_litros = sum(float(a.quantidade_litros) for a in abas)
    total_custo = sum(float(a.custo_total) for a in abas)
    return {
        "placa": placa_norm,
        "placa_raw": placa,
        "dias": int(dias),
        "janela_inicio": inicio.isoformat(),
        "janela_fim": fim.isoformat(),
        "cadastrado_no_gp": cadastrado is not None,
        "mobilizado": (
            {
                "id": cadastrado.id,
                "equipamento": cadastrado.equipamento,
                "marca": cadastrado.marca,
                "modelo": cadastrado.modelo,
                "tipo_equipamento": cadastrado.tipo_equipamento,
                "situacao": cadastrado.situacao,
                "data_mobilizacao": (
                    cadastrado.data_mobilizacao.isoformat()
                    if cadastrado.data_mobilizacao
                    else None
                ),
                "data_desmobilizacao": (
                    cadastrado.data_desmobilizacao.isoformat()
                    if cadastrado.data_desmobilizacao
                    else None
                ),
            }
            if cadastrado
            else None
        ),
        "n_abastecimentos": len(abas),
        "total_litros": round(total_litros, 1),
        "total_custo_brl": round(total_custo, 2),
        "amostra_abastecimentos": [
            {
                "id": a.id,
                "data": a.data.isoformat(),
                "litros": float(a.quantidade_litros),
                "custo": float(a.custo_total),
                "inconsistencia": a.inconsistencias_infleet,
            }
            for a in abas[:8]
        ],
    }


def _fim_da_janela(session: Session) -> datetime:
    """Usa a data do abastecimento mais recente como referencia (dataset estatico)."""
    ult = session.exec(
        select(Abastecimento).order_by(Abastecimento.data.desc()).limit(1)  # type: ignore[attr-defined]
    ).first()
    return ult.data if ult else datetime.now()
