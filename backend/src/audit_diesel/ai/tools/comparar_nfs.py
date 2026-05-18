"""Tool: comparacao rapida entre duas auditorias (por nf_atual)."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from audit_diesel.audit.alert_dedup import deduplicar_nao_cadastrados
from audit_diesel.models import Alerta, Auditoria


def comparar_nfs(session: Session, *, nf_a: str, nf_b: str) -> dict[str, Any]:
    """Retorna deltas entre as auditorias mais recentes das duas NFs."""
    a = _mais_recente(session, str(nf_a))
    b = _mais_recente(session, str(nf_b))
    if a is None or b is None:
        return {
            "erro": "uma das NFs nao tem auditoria registrada",
            "nf_a_encontrada": a is not None,
            "nf_b_encontrada": b is not None,
        }
    alertas_a = deduplicar_nao_cadastrados(
        session.exec(select(Alerta).where(Alerta.auditoria_id == a.id)).all()
    )
    alertas_b = deduplicar_nao_cadastrados(
        session.exec(select(Alerta).where(Alerta.auditoria_id == b.id)).all()
    )
    return {
        "nf_a": _resumo(a, alertas_a),
        "nf_b": _resumo(b, alertas_b),
        "deltas": {
            "diferenca_pct_pp": round(
                (float(b.diferenca_percentual or 0.0) - float(a.diferenca_percentual or 0.0)) * 100, 2
            ),
            "nao_cadastrados": _qtd_nao_cadastrados(alertas_b)
                - _qtd_nao_cadastrados(alertas_a),
            "saidas_registradas_brl": round(
                float(b.saidas_registradas_custo or 0.0) - float(a.saidas_registradas_custo or 0.0), 2
            ),
        },
    }


def _mais_recente(session: Session, nf_atual: str) -> Auditoria | None:
    return session.exec(
        select(Auditoria)
        .where(Auditoria.nf_atual == nf_atual)
        .order_by(Auditoria.criada_em.desc())  # type: ignore[attr-defined]
    ).first()


def _resumo(a: Auditoria, alertas: list[Alerta]) -> dict[str, Any]:
    return {
        "auditoria_id": a.id,
        "nf_atual": a.nf_atual,
        "nf_anterior": a.nf_anterior,
        "nome_obra": a.nome_obra,
        "diferenca_percentual": round(float(a.diferenca_percentual or 0.0) * 100, 2),
        "saidas_registradas_litros": float(a.saidas_registradas_litros or 0.0),
        "saidas_registradas_custo": float(a.saidas_registradas_custo or 0.0),
        "qtd_nao_cadastrados": _qtd_nao_cadastrados(alertas),
        "validacao_final": a.validacao_final,
        "n_alertas": len(alertas),
    }


def _qtd_nao_cadastrados(alertas: list[Alerta]) -> int:
    return sum(1 for al in alertas if al.tipo == "NAO_CADASTRADO")
