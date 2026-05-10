"""Indicadores quantitativos definidos no §4 do escopo da auditoria.

A formula referencia o documento "Auditoria de Diesel - REV04" do consorcio:

    estoque_final_teorico_anterior =
        estoque_antes_tanque + estoque_antes_comboio + quantidade_descarregada

    saida_teorica = estoque_final_teorico_anterior - estoque_inicial_atual

    diferenca = saidas_registradas (Infleet) - saida_teorica

TODO(escopo §4.1): O escopo cita "Quantidade Descarregada" como sinonimo da
quantidade da NF; aqui usamos `quantidade_nf_litros`. Validar com o cliente
se ha cenarios em que `volume_conferido` deveria substituir esse campo.
"""

from __future__ import annotations

from dataclasses import dataclass

from audit_diesel.models import Abastecimento, Checklist


@dataclass
class IndicadoresAuditoria:
    """Pacote de numeros derivados das formulas do §4 do escopo."""

    estoque_inicial_anterior: float
    quantidade_descarregada_anterior: float
    estoque_final_teorico_anterior: float
    saidas_registradas_litros: float
    saidas_registradas_custo: float
    estoque_inicial_atual: float
    saida_teorica_litros: float
    diferenca_litros: float
    diferenca_percentual: float


def calcular_indicadores(
    nf_anterior: Checklist,
    nf_atual: Checklist,
    abastecimentos_janela: list[Abastecimento],
) -> IndicadoresAuditoria:
    """Aplica as formulas do escopo, dado o par de NFs e os abastecimentos da janela."""
    estoque_inicial_anterior = (
        nf_anterior.estoque_antes_tanque_litros + nf_anterior.estoque_antes_comboio_litros
    )
    quantidade_descarregada_anterior = nf_anterior.quantidade_nf_litros
    estoque_final_teorico_anterior = estoque_inicial_anterior + quantidade_descarregada_anterior

    saidas_litros = sum(a.quantidade_litros for a in abastecimentos_janela)
    saidas_custo = sum(a.custo_total for a in abastecimentos_janela)

    estoque_inicial_atual = (
        nf_atual.estoque_antes_tanque_litros + nf_atual.estoque_antes_comboio_litros
    )
    saida_teorica = estoque_final_teorico_anterior - estoque_inicial_atual
    diferenca = saidas_litros - saida_teorica
    diferenca_pct = diferenca / saida_teorica if saida_teorica != 0 else 0.0

    return IndicadoresAuditoria(
        estoque_inicial_anterior=estoque_inicial_anterior,
        quantidade_descarregada_anterior=quantidade_descarregada_anterior,
        estoque_final_teorico_anterior=estoque_final_teorico_anterior,
        saidas_registradas_litros=saidas_litros,
        saidas_registradas_custo=saidas_custo,
        estoque_inicial_atual=estoque_inicial_atual,
        saida_teorica_litros=saida_teorica,
        diferenca_litros=diferenca,
        diferenca_percentual=diferenca_pct,
    )
