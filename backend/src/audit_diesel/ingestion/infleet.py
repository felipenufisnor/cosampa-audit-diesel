"""Leitor da planilha Infleet (abastecimentos individuais)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from audit_diesel.models import Abastecimento

from .normalizers import (
    combinar_data_hora,
    normalizar_data,
    normalizar_hora,
    normalizar_numero_br,
    normalizar_placa,
    normalizar_texto,
)


def carregar_abastecimentos(arquivo: Path) -> list[Abastecimento]:
    """Le o xlsx do Infleet e devolve a lista de Abastecimento prontos para insert.

    Linhas com Veiculo vazio sao descartadas. Autonomia '--' vira None.
    """
    df = pd.read_excel(arquivo, sheet_name=0)
    registros: list[Abastecimento] = []
    for _, row in df.iterrows():
        veiculo_raw = normalizar_texto(row.get("Veículo"))
        if not veiculo_raw:
            continue
        data = normalizar_data(row.get("Data"))
        hora = normalizar_hora(row.get("Horário"))
        dt = combinar_data_hora(data, hora)
        if dt is None:
            continue
        registros.append(
            Abastecimento(
                data=dt,
                veiculo_raw=veiculo_raw,
                veiculo_normalizado=normalizar_placa(veiculo_raw),
                apelido=normalizar_texto(row.get("Apelido")),
                quantidade_litros=normalizar_numero_br(row.get("Quantidade")),
                custo_total=normalizar_numero_br(row.get("Custo total (R$)")),
                valor_litro=normalizar_numero_br(row.get("Valor do litro (R$/l)")),
                medido_por=normalizar_texto(row.get("Medido por")),
                medicao=_to_optional_float(row.get("Medição")),
                autonomia_media=_to_optional_float(row.get("Autonomia média (km/l ou l/h)")),
                observacoes=normalizar_texto(row.get("Observações")),
                inconsistencias_infleet=normalizar_texto(row.get("Inconsistências")),
                fornecedor=normalizar_texto(row.get("Fornecedor")),
            )
        )
    return registros


def _to_optional_float(valor: object) -> float | None:
    """pd.to_numeric-style: '-' e NaN viram None, resto vira float."""
    txt = normalizar_texto(valor)
    if txt is None:
        return None
    try:
        return float(str(txt).replace(",", "."))
    except ValueError:
        return None
