"""Deduplicacao de alertas para exposicao publica."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from audit_diesel.models import Alerta


def deduplicar_nao_cadastrados(alertas: Iterable[Alerta]) -> list[Alerta]:
    """Mantem um NAO_CADASTRADO por veiculo, escolhendo o maior impacto."""
    resultado: list[Alerta] = []
    pos_por_veiculo: dict[tuple[int, str], int] = {}

    for alerta in alertas:
        if alerta.tipo != "NAO_CADASTRADO":
            resultado.append(alerta)
            continue

        veiculo_key = _veiculo_key(alerta)
        if veiculo_key is None:
            resultado.append(alerta)
            continue

        key = (alerta.auditoria_id, veiculo_key)
        pos = pos_por_veiculo.get(key)
        if pos is None:
            pos_por_veiculo[key] = len(resultado)
            resultado.append(alerta)
            continue

        atual = resultado[pos]
        if _impacto(alerta) > _impacto(atual):
            resultado[pos] = alerta

    return resultado


def _veiculo_key(alerta: Alerta) -> str | None:
    payload = _payload(alerta)
    veiculo = payload.get("veiculo_normalizado") or payload.get("veiculo_raw")
    return str(veiculo) if veiculo else None


def _payload(alerta: Alerta) -> dict[str, Any]:
    if not alerta.payload_json:
        return {}
    try:
        payload = json.loads(alerta.payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _impacto(alerta: Alerta) -> float:
    return float(alerta.impacto_financeiro or 0.0)
