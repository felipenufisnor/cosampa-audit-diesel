"""Leitor da planilha de Checklists / Recebimentos de NF (origem GLPI)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from audit_diesel.models import Checklist

from .normalizers import (
    combinar_data_hora,
    normalizar_data,
    normalizar_hora,
    normalizar_numero_br,
    normalizar_texto,
)


def carregar_checklists(arquivo: Path) -> list[Checklist]:
    """Le o xlsx de chamados GLPI e devolve a lista de Checklist (1 por NF)."""
    df = pd.read_excel(arquivo, sheet_name=0)
    registros: list[Checklist] = []
    for _, row in df.iterrows():
        nf = normalizar_texto(row.get("Nota Fiscal"))
        if not nf:
            continue
        data_recebimento = normalizar_data(row.get("Data Recebimento da Mercadoria"))
        if data_recebimento is None:
            continue
        hora_inicio = normalizar_hora(row.get("Hora Inicio da Descarga"))
        hora_final = normalizar_hora(row.get("Hora Final da Descarga"))
        dt_fim = combinar_data_hora(data_recebimento, hora_final)
        if dt_fim is None:
            continue
        registros.append(
            Checklist(
                numero_chamado=str(normalizar_texto(row.get("Numero do Chamado")) or ""),
                nota_fiscal=nf,
                nome_obra=normalizar_texto(row.get("Nome da Obra")) or "",
                cnpj_fornecedor=normalizar_texto(row.get("CNPJ Fornecedor")) or "",
                data_recebimento=data_recebimento,
                hora_inicio_descarga=hora_inicio or hora_final or _midnight(),
                hora_final_descarga=hora_final or _midnight(),
                datetime_fim_descarga=dt_fim,
                quantidade_nf_litros=normalizar_numero_br(row.get("Quantidade de Compras em Litros")),
                volume_conferido_litros=normalizar_numero_br(row.get("Volume Conferido")),
                estoque_antes_tanque_litros=normalizar_numero_br(
                    row.get("Estoque Antes da Descarga - Tanque")
                ),
                estoque_antes_comboio_litros=normalizar_numero_br(
                    row.get("Estoque Antes da Descarga - Comboio")
                ),
                preco_unitario=normalizar_numero_br(row.get("Preco Unitario")),
                valor_total_nf=normalizar_numero_br(row.get("Valor Total da NF")),
            )
        )
    return registros


def _midnight():  # noqa: ANN202
    from datetime import time
    return time(0, 0)
