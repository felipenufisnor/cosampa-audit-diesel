"""Tool: agregados de abastecimento + alertas de uma obra em um periodo."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from audit_diesel.audit.alert_dedup import deduplicar_nao_cadastrados
from audit_diesel.models import Abastecimento, Alerta, Auditoria


def consultar_obra_no_periodo(
    session: Session,
    *,
    obra: str,
    inicio: str,
    fim: str,
) -> dict[str, Any]:
    """Retorna agregados, NFs auditadas e contagem de alertas no periodo."""
    try:
        dt_inicio = datetime.fromisoformat(inicio)
        dt_fim = datetime.fromisoformat(fim)
    except ValueError:
        return {"erro": "inicio/fim devem ser ISO 8601 (YYYY-MM-DD ou completo)"}

    abas = list(session.exec(
        select(Abastecimento)
        .where(Abastecimento.data >= dt_inicio)
        .where(Abastecimento.data <= dt_fim)
    ).all())
    total_litros = sum(float(a.quantidade_litros) for a in abas)
    total_custo = sum(float(a.custo_total) for a in abas)

    audits = list(session.exec(
        select(Auditoria)
        .where(Auditoria.nome_obra == obra)
        .where(Auditoria.criada_em >= dt_inicio)
        .where(Auditoria.criada_em <= dt_fim)
    ).all())
    ids = [a.id for a in audits if a.id is not None]
    alertas = (
        deduplicar_nao_cadastrados(
            session.exec(
                select(Alerta).where(Alerta.auditoria_id.in_(ids))  # type: ignore[attr-defined]
            ).all()
        )
        if ids
        else []
    )

    return {
        "obra": obra,
        "inicio": dt_inicio.isoformat(),
        "fim": dt_fim.isoformat(),
        "abastecimentos": {
            "n": len(abas),
            "total_litros": round(total_litros, 1),
            "total_custo_brl": round(total_custo, 2),
        },
        "auditorias": [
            {
                "id": a.id,
                "nf_atual": a.nf_atual,
                "nf_anterior": a.nf_anterior,
                "diferenca_percentual": round(float(a.diferenca_percentual or 0.0) * 100, 2),
                "validacao_final": a.validacao_final,
                "qtd_equipamentos_nao_cadastrados": sum(
                    1
                    for al in alertas
                    if al.auditoria_id == a.id and al.tipo == "NAO_CADASTRADO"
                ),
            }
            for a in audits
        ],
        "alertas_por_tipo": _contar(alertas, lambda x: x.tipo),
        "alertas_por_severidade": _contar(alertas, lambda x: x.severidade),
    }


def _contar(items: list[Alerta], key) -> dict[str, int]:  # type: ignore[no-untyped-def]
    out: dict[str, int] = {}
    for it in items:
        k = key(it) or "desconhecido"
        out[k] = out.get(k, 0) + 1
    return out
