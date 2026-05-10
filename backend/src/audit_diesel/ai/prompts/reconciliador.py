"""Prompt + tool schema do reconciliador semântico.

O contrato é OpenAI tools/function calling (formato chat.completions). O
modelo recebe sistema + dados estruturados em texto e responde chamando a
ferramenta `registrar_sugestoes`. Este módulo é puro: sem chamadas externas.
"""

from __future__ import annotations

import json
from typing import Any

# Marker [task:...] permite que o OfflineProvider identifique a tarefa apenas
# olhando o system prompt, mantendo o offline robusto a mudanças de texto.
TASK_MARKER = "[task:reconciliador]"

SYSTEM_PROMPT = f"""{TASK_MARKER}
Você é um especialista em reconciliação de cadastros de equipamentos de obra.
Sua tarefa é, dada uma identificação de veículo/equipamento usada num sistema
de telemetria (Infleet), encontrar a correspondência mais provável no cadastro
oficial (GP/Mobilizados) da mesma obra.

Regras de raciocínio:
1. Identificadores podem aparecer em formatos heterogeneos: placa Mercosul,
   placa antiga, código interno com ponto (07.T586), código sem ponto (EH01),
   número de chassi, ou nome funcional ("MACARICO", "CALDEIRA").
2. O campo "apelido" do Infleet costuma trazer informação semântica forte
   que casa com Equipamento/Modelo do GP.
3. Capacidade do tanque (litros) e tipo de equipamento são bons desempates
   quando há mais de 1 candidato.
4. Confiança 0.0-1.0:
   - >= 0.85: identificadores normalizam para o mesmo valor OU apelido casa
     inequivocamente com nome do equipamento.
   - 0.65-0.84: forte sinal semântico mas sem prova literal.
   - 0.40-0.64: hipótese plausível, requer validação humana.
   - < 0.40: NÃO sugira; retorne mobilizado_id_candidato=null para esse abastecimento.
5. Se nenhum candidato fornecido casar minimamente, retorne null.
6. Sua justificativa DEVE citar evidência específica do dado, não generalidades.
7. Sempre responda chamando a ferramenta `registrar_sugestoes` com uma
   sugestão por abastecimento de entrada, na mesma ordem.
"""


TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "registrar_sugestoes",
        "description": (
            "Registra a sugestão de reconciliação para cada abastecimento de entrada. "
            "Use mobilizado_id_candidato=null quando nenhum candidato for plausível."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "sugestoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "abastecimento_id": {"type": "integer"},
                            "mobilizado_id_candidato": {"type": ["integer", "null"]},
                            "confianca": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                            "justificativa": {
                                "type": "string",
                                "maxLength": 280,
                            },
                        },
                        "required": [
                            "abastecimento_id",
                            "mobilizado_id_candidato",
                            "confianca",
                            "justificativa",
                        ],
                    },
                }
            },
            "required": ["sugestoes"],
        },
    },
}


def montar_user_message(
    abastecimentos: list[dict[str, Any]],
    candidatos: list[dict[str, Any]],
) -> str:
    """Serializa abastecimentos + candidatos como JSON pretty-printed.

    Mantemos JSON puro (e não tabela) para o modelo poder citar IDs com
    precisão na justificativa.
    """
    payload = {
        "abastecimentos_nao_cadastrados": abastecimentos,
        "candidatos_gp_mesma_obra": candidatos,
        "instrucao": (
            "Para cada abastecimento, decida o melhor candidato_GP. Use null "
            "quando nada for >= 0.40 de confiança. Cite o ID do candidato "
            "escolhido na justificativa."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
