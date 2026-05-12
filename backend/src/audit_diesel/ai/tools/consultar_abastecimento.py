"""Tool: detalhes de um abastecimento individual."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session

from audit_diesel.models import Abastecimento, Mobilizado


def consultar_abastecimento(
    session: Session, *, abastecimento_id: int
) -> dict[str, Any]:
    """Retorna campos do abastecimento + status de cadastro no GP."""
    a = session.get(Abastecimento, int(abastecimento_id))
    if a is None:
        return {"erro": f"abastecimento {abastecimento_id} nao encontrado"}
    # Verifica se a placa esta cadastrada (busca exata pela placa_normalizada).
    from sqlmodel import select

    cadastrado = session.exec(
        select(Mobilizado).where(
            Mobilizado.placa_ativo_normalizada == a.veiculo_normalizado
        )
    ).first()
    return {
        "id": a.id,
        "data": a.data.isoformat(),
        "veiculo": a.veiculo_normalizado,
        "veiculo_raw": a.veiculo_raw,
        "apelido": a.apelido,
        "litros": float(a.quantidade_litros),
        "custo": float(a.custo_total),
        "valor_litro": float(a.valor_litro),
        "medido_por": a.medido_por,
        "fornecedor": a.fornecedor,
        "inconsistencias_infleet": a.inconsistencias_infleet,
        "cadastrado_no_gp": cadastrado is not None,
        "mobilizado_match": (
            {
                "id": cadastrado.id,
                "equipamento": cadastrado.equipamento,
                "marca": cadastrado.marca,
                "modelo": cadastrado.modelo,
                "tipo_equipamento": cadastrado.tipo_equipamento,
                "situacao": cadastrado.situacao,
            }
            if cadastrado
            else None
        ),
    }
