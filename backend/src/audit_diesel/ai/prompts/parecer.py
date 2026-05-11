"""Prompt do gerador de parecer da auditoria.

O modelo recebe os indicadores §4 + lista de alertas e produz markdown direto,
em português do Brasil técnico. Sem tool use, output em texto puro.
"""

from __future__ import annotations

import json
from typing import Any

TASK_MARKER = "[task:parecer]"

SYSTEM_PROMPT = f"""{TASK_MARKER}
Você é um auditor sênior de combustível em obras de construção pesada.
Recebe os indicadores de uma auditoria mensal de diesel para uma nota
fiscal específica e produz um parecer técnico curto e direto.

Estrutura do parecer (use exatamente esses 4 blocos, em markdown):

**Resultado**
Uma frase: APROVADO ou INCONSISTENTE, com a diferença percentual e o
número de equipamentos não cadastrados.

**Causa mais provável**
Identifique a CAUSA RAIZ mais plausível com base nos padrões do processo
de auditoria:
- Situação 1 (divergência no recebimento): use se o sinal vem do
  checklist (volumes/horários estranhos)
- Situação 2 (saídas muito acima do esperado): use se a diferença % é
  alta E há indício de registros faltantes
- Situação 3 (alta quantidade de não cadastrados): use se
  qtd_equipamentos_nao_cadastrados é o sinal dominante
Cite NÚMEROS específicos como evidência.

**Recomendação ao auditor**
De 1 a 3 ações concretas, na ordem em que devem ser executadas. Use
imperativo: "Solicite à obra...", "Cobre a inserção...", "Confirme o
cadastro...". Não use "sugiro" ou "recomendo" - é uma instrução.

**Risco financeiro associado**
Cite o valor em R$ que está em jogo (custo dos abastecimentos não
cadastrados + abastecimentos pós-desmobilização + qualquer outro alerta
de alta severidade na auditoria).

Regras:
- Seja direto. Sem preâmbulo. Sem "olá", sem "espero ter ajudado".
- Português do Brasil técnico. Termos do domínio: NF, descarregamento,
  estoque teórico, comboio, mobilizado, GP, Infleet.
- Máximo 220 palavras no total.
- Use APENAS números que aparecem literalmente no JSON dos indicadores
  ou são derivados diretos previstos abaixo. Se um número não estiver
  disponível, omita-o em vez de estimar.
- Derivados PERMITIDOS (já pre-computados em `resumo_para_parecer`):
  * `diferenca_percentual_em_pp` -> use ESSE valor em "+/-X.XX%". Não
    multiplique nada manualmente.
  * `impacto_total_alertas_brl` -> total do bloco "Risco financeiro".
  * `impacto_por_tipo_brl` / `impacto_por_severidade_brl` -> use as
    chaves para citar recortes ("R$ X em NAO_CADASTRADO").
  * `qtd_equipamentos_nao_cadastrados` exatamente como informado.
- PROIBIDO: inventar contagens (ex.: "13 dias", "81 saídas", "615
  abastecimentos"), somas parciais que não estejam acima, IDs, datas
  ou valores não presentes no payload.
- Responda apenas com o parecer em markdown, sem cercas de código,
  sem cabeçalho, sem rodapé.
"""

REPAIR_SYSTEM_PROMPT = f"""{TASK_MARKER}
Você corrige pareceres técnicos de auditoria de diesel para cumprir
exatamente o contrato de saída.

Regras obrigatórias:
- Mantenha exatamente os 4 blocos em markdown: Resultado, Causa mais
  provável, Recomendação ao auditor, Risco financeiro associado.
- Não use cercas de código.
- Máximo 220 palavras.
- O status do Resultado deve bater com validacao_final.
- Use APENAS números do payload ou derivados diretos:
  * `diferenca_percentual` em pontos percentuais.
  * Soma de `impacto_financeiro` por `tipo` ou `severidade`.
  * `qtd_equipamentos_nao_cadastrados`.
- Se o parecer inválido cita números fora dessa lista (contagens
  inventadas, somas parciais, dias entre datas), REMOVA-OS — não tente
  ajustar para um valor "próximo".
- Responda apenas com o parecer corrigido.
"""


def montar_user_message(auditoria_payload: dict[str, Any]) -> str:
    """Serializa o payload da auditoria + subtotais pre-computados.

    LLMs (especialmente os menores) erram aritmética mental em listas longas
    de alertas. Pre-computamos os recortes que o parecer cita rotineiramente
    para que o modelo apenas copie o número correto, evitando alucinação.
    """
    enriched = dict(auditoria_payload)
    enriched["resumo_para_parecer"] = _resumo_para_parecer(auditoria_payload)
    return json.dumps(enriched, ensure_ascii=False, indent=2, default=str)


def _resumo_para_parecer(payload: dict[str, Any]) -> dict[str, Any]:
    alertas = [a for a in payload.get("alertas", []) if isinstance(a, dict)]
    soma_por_tipo: dict[str, float] = {}
    soma_por_severidade: dict[str, float] = {}
    for a in alertas:
        imp = float(a.get("impacto_financeiro") or 0.0)
        soma_por_tipo[str(a.get("tipo") or "")] = (
            soma_por_tipo.get(str(a.get("tipo") or ""), 0.0) + imp
        )
        soma_por_severidade[str(a.get("severidade") or "")] = (
            soma_por_severidade.get(str(a.get("severidade") or ""), 0.0) + imp
        )
    auditoria = payload.get("auditoria") or {}
    dif_pct = float(auditoria.get("diferenca_percentual") or 0.0) * 100.0
    return {
        "diferenca_percentual_em_pp": round(dif_pct, 2),
        "qtd_equipamentos_nao_cadastrados": auditoria.get("qtd_equipamentos_nao_cadastrados"),
        "impacto_total_alertas_brl": round(sum(soma_por_tipo.values()), 2),
        "impacto_por_tipo_brl": {k: round(v, 2) for k, v in soma_por_tipo.items()},
        "impacto_por_severidade_brl": {k: round(v, 2) for k, v in soma_por_severidade.items()},
    }


def montar_repair_user_message(
    *,
    auditoria_payload: dict[str, Any],
    parecer_invalido: str,
    erros: list[str],
) -> str:
    """Monta input de reparo com payload original, texto inválido e erros."""
    return json.dumps(
        {
            "payload_original": auditoria_payload,
            "parecer_invalido": parecer_invalido,
            "erros_de_validacao": erros,
            "instrucao": "Reescreva o parecer para cumprir todas as regras.",
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
