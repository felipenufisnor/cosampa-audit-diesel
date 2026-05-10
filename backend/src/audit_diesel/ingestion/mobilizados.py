"""Leitor da planilha Mobilizados (cadastro de equipamentos do GP)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from audit_diesel.models import Mobilizado

from .normalizers import (
    normalizar_capacidade,
    normalizar_data,
    normalizar_placa,
    normalizar_texto,
)


def carregar_mobilizados(arquivo: Path) -> list[Mobilizado]:
    """Le o xlsx do Gestao de Projetos e devolve a lista de Mobilizado.

    O cabecalho real esta na linha 5 (indice 4); as 4 primeiras linhas sao
    metadados de geracao do relatorio. Linhas sem ID (rodape e total) sao
    descartadas.
    """
    df = pd.read_excel(arquivo, sheet_name=0, header=4)
    registros: list[Mobilizado] = []
    for _, row in df.iterrows():
        id_val = row.get("ID")
        if pd.isna(id_val):
            continue
        try:
            id_int = int(id_val)
        except (ValueError, TypeError):
            continue
        placa_raw = normalizar_texto(row.get("Placa/Ativo")) or ""
        situacao = normalizar_texto(row.get("Situação")) or "DESCONHECIDA"
        ano_val = row.get("Ano")
        try:
            ano = int(ano_val) if not pd.isna(ano_val) else None
        except (ValueError, TypeError):
            ano = None
        registros.append(
            Mobilizado(
                id=id_int,
                codigo_projeto=normalizar_texto(row.get("Código Projeto")) or "",
                nome_obra=normalizar_texto(row.get("Nome da Obra")) or "",
                tipo_equipamento=normalizar_texto(row.get("Tipo de Equipamento")),
                equipamento=normalizar_texto(row.get("Equipamento")),
                marca=normalizar_texto(row.get("Marca")),
                modelo=normalizar_texto(row.get("Modelo")),
                placa_ativo_raw=placa_raw,
                placa_ativo_normalizada=normalizar_placa(placa_raw),
                situacao=situacao,
                data_mobilizacao=normalizar_data(row.get("Data Mobilização")),
                data_desmobilizacao=normalizar_data(row.get("Data Desmobilização")),
                capacidade_litros=normalizar_capacidade(row.get("Capacidade")),
                ano=ano,
            )
        )
    return registros
