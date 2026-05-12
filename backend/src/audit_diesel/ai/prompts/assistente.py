"""Prompt do Assistente de Investigacao (Feature B da v2).

Sistema curto e diretivo: o modelo e' um auditor senior que investiga UMA
auditoria especifica. Ele tem acesso a 4 tools para consultar o banco e
deve usa-las antes de fazer afirmacoes quantitativas. A saida final e'
texto puro em pt-BR tecnico.
"""

from __future__ import annotations

import json
from typing import Any

TASK_MARKER = "[task:assistente]"

SYSTEM_PROMPT = f"""{TASK_MARKER}
Voce e' um auditor senior de combustivel investigando UMA auditoria
especifica. O usuario e' o auditor responsavel por liberar (ou nao) a NF
para pagamento.

Voce tem 4 ferramentas (`tools`) para consultar dados do banco:
- consultar_abastecimento(abastecimento_id)
- consultar_veiculo(placa, dias=28)
- consultar_obra_no_periodo(obra, inicio, fim)
- comparar_nfs(nf_a, nf_b)

Regras:
- Use as tools SEMPRE que precisar de numeros especificos, datas ou
  status de cadastro. Nao chute valores.
- Antes de afirmar "veiculo X nao esta cadastrado", confirme com
  `consultar_veiculo` ou `consultar_abastecimento`.
- Respostas em portugues do Brasil tecnico. Sem markdown pesado (use no
  maximo `*negrito*` para o veredito principal). Sem emoji.
- Maximo 180 palavras na resposta final.
- Se a pergunta for ambigua, peca esclarecimento antes de chamar tools.
- Se uma tool retornar `erro`, mencione a limitacao na resposta em vez de
  prosseguir com dados inventados.
"""


def montar_contexto_auditoria(payload: dict[str, Any]) -> str:
    """Bloco de contexto adicionado como system message apos o prompt principal."""
    auditoria = payload.get("auditoria") or {}
    alertas = payload.get("alertas") or []
    resumo = {
        "auditoria_id": auditoria.get("id"),
        "nf_atual": auditoria.get("nf_atual"),
        "nf_anterior": auditoria.get("nf_anterior"),
        "nome_obra": auditoria.get("nome_obra"),
        "diferenca_percentual": auditoria.get("diferenca_percentual"),
        "qtd_equipamentos_nao_cadastrados": auditoria.get(
            "qtd_equipamentos_nao_cadastrados"
        ),
        "validacao_final": auditoria.get("validacao_final"),
        "saidas_registradas_litros": auditoria.get("saidas_registradas_litros"),
        "saidas_registradas_custo": auditoria.get("saidas_registradas_custo"),
        "n_alertas": len(alertas),
        "alertas_por_tipo": _contar(alertas, "tipo"),
        "alertas_por_severidade": _contar(alertas, "severidade"),
    }
    return (
        "Contexto da auditoria sendo investigada (use como referencia, NAO "
        "como unica fonte; consulte tools para dados especificos):\n"
        + json.dumps(resumo, ensure_ascii=False, indent=2, default=str)
    )


def _contar(items: list[dict[str, Any]], chave: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        v = str(it.get(chave) or "")
        out[v] = out.get(v, 0) + 1
    return out
