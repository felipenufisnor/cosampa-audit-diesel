"""Prompts da analise proativa de padroes (Feature C da v2).

O LLM recebe uma lista de CANDIDATOS pre-processados em Python (cada um ja
com dados concretos: ids, contagens, valores). Sua tarefa e' apenas:
1. Selecionar os 3-5 mais relevantes para o auditor.
2. Gerar titulo curto + descricao narrativa com numeros especificos.
3. Atribuir severidade alta/media/baixa.

O LLM NAO pode inventar candidatos ou agregar contagens diferentes das
que vierem no input. A validacao pydantic posterior rejeita padroes cujos
`evidencia_ids` nao apareceram nos candidatos.
"""

from __future__ import annotations

import json
from typing import Any

TASK_MARKER = "[task:padroes]"

SYSTEM_PROMPT = f"""{TASK_MARKER}
Voce e' um auditor senior de combustivel em obras de construcao pesada.
Recebe uma lista de CANDIDATOS a padrao proativo pre-processados em
Python a partir do historico de abastecimentos, auditorias e cadastro.

Sua tarefa:
- Selecione os 3 a 5 candidatos MAIS RELEVANTES para o auditor priorizar.
- Para cada um, gere `titulo` (max 80 chars, sem aspas) e `descricao`
  (max 280 chars, com numeros especificos vindos do candidato).
- Atribua severidade: "alta" (acao imediata), "media" (investigar quando
  possivel), "baixa" (monitorar).
- Preserve `tipo` e `evidencia_ids` exatamente como vieram no candidato.

REGRAS:
- Use APENAS numeros que estao no JSON do candidato. Nao infira contagens.
- Se houver menos de 3 candidatos com evidencia real, retorne quantos
  houver (incluindo lista vazia).
- Portugues do Brasil tecnico. Sem markdown na descricao.
- Sem preambulo, sem emoji, sem expressoes como "magico", "incrivel".

Responda APENAS com o JSON no formato:
{{"padroes": [{{"tipo": "...", "titulo": "...", "descricao": "...",
"severidade": "alta|media|baixa", "evidencia_ids": [1,2,3]}}]}}
"""


def montar_user_message(candidatos: list[dict[str, Any]]) -> str:
    """Serializa os candidatos pre-processados como input do LLM."""
    return json.dumps(
        {"candidatos": candidatos, "max_padroes": 5},
        ensure_ascii=False,
        indent=2,
        default=str,
    )
