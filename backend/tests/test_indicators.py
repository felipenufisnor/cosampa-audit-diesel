"""Testes das formulas do §4 do escopo."""

from __future__ import annotations

from datetime import datetime

import pytest

from audit_diesel.audit.indicators import calcular_indicadores
from audit_diesel.models import Abastecimento


def _ab(qtd: float, custo: float, dia: int = 4) -> Abastecimento:
    return Abastecimento(
        data=datetime(2026, 3, dia, 10, 0),
        veiculo_raw="X",
        veiculo_normalizado="X",
        quantidade_litros=qtd,
        custo_total=custo,
        valor_litro=custo / qtd if qtd else 0,
    )


def test_indicadores_calculo_basico(checklist_par):
    ck_ant, ck_atu = checklist_par
    abasts = [_ab(300, 1950), _ab(200, 1300), _ab(300, 1950)]
    ind = calcular_indicadores(ck_ant, ck_atu, abasts)
    # estoque_inicial_anterior = 500 + 300 = 800
    assert ind.estoque_inicial_anterior == 800
    # estoque_final_teorico_anterior = 800 + 1000 = 1800
    assert ind.estoque_final_teorico_anterior == 1800
    # estoque_inicial_atual = 600 + 400 = 1000
    assert ind.estoque_inicial_atual == 1000
    # saida_teorica = 1800 - 1000 = 800
    assert ind.saida_teorica_litros == 800
    # saidas_registradas = 800 (consistente!)
    assert ind.saidas_registradas_litros == 800
    assert ind.diferenca_litros == 0
    assert ind.diferenca_percentual == 0
    assert ind.saidas_registradas_custo == pytest.approx(5200.0)


def test_indicadores_diferenca_positiva(checklist_par):
    ck_ant, ck_atu = checklist_par
    abasts = [_ab(900, 5850)]  # 100 L acima do teorico
    ind = calcular_indicadores(ck_ant, ck_atu, abasts)
    assert ind.diferenca_litros == 100
    assert ind.diferenca_percentual == pytest.approx(100 / 800)


def test_saida_teorica_zero_nao_quebra(checklist_par):
    ck_ant, ck_atu = checklist_par
    # Forca saida_teorica == 0
    ck_atu.estoque_antes_tanque_litros = 1500
    ck_atu.estoque_antes_comboio_litros = 300
    ind = calcular_indicadores(ck_ant, ck_atu, [])
    assert ind.saida_teorica_litros == 0
    assert ind.diferenca_percentual == 0
