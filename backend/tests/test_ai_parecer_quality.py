"""Testes do detector de pareceres-template/placeholder.

Garantimos que as 4 frases reportadas em producao + vazamento de nome de
campo sao flagrados, e que o parecer deterministico real passa limpo.
"""

from __future__ import annotations

import pytest

from audit_diesel.ai.parecer_deterministico import gerar_parecer_deterministico
from audit_diesel.ai.parecer_quality import (
    avaliar_parecer,
    is_parecer_placeholder,
)


@pytest.mark.parametrize(
    "frase",
    [
        # Frases extraidas do parecer da NF 8187 em producao.
        "Resultado calculado a partir dos indicadores §4 do escopo.",
        "Avaliacao baseada nos alertas disparados pelo engine deterministico.",
        "Revise os alertas listados e proceda conforme procedimento operacional padrao.",
        "Valor consolidado conforme campo impacto_total_alertas_brl.",
    ],
)
def test_frases_template_sao_flagradas(frase: str) -> None:
    # Mesmo concatenando com texto extra para passar do limite de palavras,
    # a presenca da frase-template ou nome de campo basta para flagrar.
    parecer = frase + " " + ("palavra " * 60)
    quality = avaliar_parecer(parecer)
    assert quality.status == "placeholder"
    assert is_parecer_placeholder(parecer)


def test_nome_de_campo_vazado_eh_flagrado() -> None:
    parecer = (
        "A diferenca observada na auditoria justifica revisao do parecer "
        "tecnico. O auditor deve checar impacto_total_alertas_brl antes "
        "de fechar o periodo de analise. " + ("palavra " * 30)
    )
    quality = avaliar_parecer(parecer)
    assert quality.status == "placeholder"
    assert any("nome_campo_vazado" in r for r in quality.reasons)


def test_parecer_vazio_e_none_sao_ausente() -> None:
    assert avaliar_parecer(None).status == "ausente"
    assert avaliar_parecer("").status == "ausente"
    assert avaliar_parecer("   \n\t  ").status == "ausente"


def test_texto_curto_demais_eh_flagrado() -> None:
    quality = avaliar_parecer("Tudo certo com a auditoria.")
    assert quality.status == "placeholder"
    assert any("curto_demais" in r for r in quality.reasons)


def test_parecer_deterministico_real_passa() -> None:
    payload = {
        "auditoria": {
            "nf_atual": "8187",
            "diferenca_percentual": 0.0234,
            "diferenca_litros": 350.0,
            "qtd_equipamentos_nao_cadastrados": 6,
            "validacao_final": "INCONSISTENTE",
            "saida_teorica_litros": 15000.0,
            "saidas_registradas_litros": 15350.0,
        },
        "alertas": [
            {"severidade": "alta", "impacto_financeiro": 1200.0},
            {"severidade": "alta", "impacto_financeiro": 850.5},
        ],
    }
    parecer = gerar_parecer_deterministico(payload)
    quality = avaliar_parecer(parecer)
    assert quality.status == "ok", (
        f"Parecer deterministico nao deveria ser flagrado: reasons={quality.reasons}"
    )
