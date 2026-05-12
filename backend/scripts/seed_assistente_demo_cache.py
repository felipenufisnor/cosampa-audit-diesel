"""Popula cache mínimo do Assistente para a janela demo 8108 -> 8187.

Uso:
    uv run python scripts/seed_assistente_demo_cache.py

Este seed não depende de provider real. Ele garante que a NF 8187 tenha
perguntas sugeridas úteis mesmo quando a IA livre estiver offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from audit_diesel.ai.assistente import salvar_cache_chip  # noqa: E402


NF_ANTERIOR = "8108"
NF_ATUAL = "8187"
AUDITORIA_ID_COMPAT = 0

ENTRADAS = {
    "Quais veiculos nao estao cadastrados nesta NF?": (
        "Nesta janela 8108 -> 8187, a auditoria aponta 36 equipamentos sem "
        "cadastro correspondente no GP. Priorize as placas com maior impacto "
        "financeiro nos alertas NAO_CADASTRADO e solicite regularizacao do "
        "cadastro antes de liberar a NF."
    ),
    "Compare o consumo desta NF com a NF anterior": (
        "A NF 8187 fecha a janela iniciada apos a NF 8108. O consumo registrado "
        "no Infleet ficou muito proximo da saida teorica, com diferenca de "
        "+0,39%, mas o volume de equipamentos nao cadastrados impede confiar "
        "apenas no indicador agregado."
    ),
    "Qual o impacto financeiro dos alertas desta auditoria?": (
        "O principal risco financeiro vem dos alertas de equipamentos sem "
        "cadastro. Na amostra da NF 8187, o maior alerta individual exibido "
        "na tela e de R$ 6.888,96. Recomendo revisar primeiro os alertas de "
        "alta severidade e reconciliar os abastecimentos com o GP."
    ),
    "Existe algum padrao suspeito nesta auditoria?": (
        "Sim. O padrao mais relevante e operacional: muitos abastecimentos "
        "concentram-se em veiculos sem cadastro no GP, apesar da diferenca "
        "percentual total estar baixa. Isso sugere falha de cadastro ou uso "
        "de ativos nao refletidos oficialmente na obra."
    ),
}


def main() -> int:
    for pergunta, resposta in ENTRADAS.items():
        salvar_cache_chip(
            AUDITORIA_ID_COMPAT,
            pergunta,
            resposta,
            nf_anterior=NF_ANTERIOR,
            nf_atual=NF_ATUAL,
        )
    print(
        f"Cache do Assistente populado para NF {NF_ATUAL} anterior {NF_ANTERIOR} "
        f"({len(ENTRADAS)} perguntas)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
