"""Prompt + tool schema do reconciliador semantico.

O contrato eh OpenAI tools/function calling (formato chat.completions). O
modelo recebe sistema + dados estruturados em texto e responde chamando a
ferramenta `registrar_sugestoes`. Este modulo eh puro: sem chamadas externas.
"""

from __future__ import annotations

import json
from typing import Any

# Marker [task:...] permite que o OfflineProvider identifique a tarefa apenas
# olhando o system prompt, mantendo o offline robusto a mudancas de texto.
TASK_MARKER = "[task:reconciliador]"

SYSTEM_PROMPT = f"""{TASK_MARKER}
Voce eh um especialista em reconciliacao de cadastros de equipamentos de obra.
Sua tarefa eh, dada uma identificacao de veiculo/equipamento usada num sistema
de telemetria (Infleet), encontrar a correspondencia mais provavel no cadastro
oficial (GP/Mobilizados) da mesma obra.

Regras de raciocinio:
1. Identificadores podem aparecer em formatos heterogeneos: placa Mercosul,
   placa antiga, codigo interno com ponto (07.T586), codigo sem ponto (EH01),
   numero de chassi, ou nome funcional ("MACARICO", "CALDEIRA").
2. O campo "apelido" do Infleet costuma trazer informacao semantica forte
   que casa com Equipamento/Modelo do GP.
3. Capacidade do tanque (litros) e tipo de equipamento sao bons desempates
   quando ha mais de 1 candidato.
4. Confianca 0.0-1.0:
   - >= 0.85: identificadores normalizam para o mesmo valor OU apelido casa
     inequivocamente com nome do equipamento.
   - 0.65-0.84: forte sinal semantico mas sem prova literal.
   - 0.40-0.64: hipotese plausivel, requer validacao humana.
   - < 0.40: NAO sugira; retorne mobilizado_id_candidato=null para esse abastecimento.
5. Se nenhum candidato fornecido casar minimamente, retorne null.
6. Sua justificativa DEVE citar evidencia especifica do dado, nao generalidades.
7. Sempre responda chamando a ferramenta `registrar_sugestoes` com uma
   sugestao por abastecimento de entrada, na mesma ordem.
"""


TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "registrar_sugestoes",
        "description": (
            "Registra a sugestao de reconciliacao para cada abastecimento de entrada. "
            "Use mobilizado_id_candidato=null quando nenhum candidato for plausivel."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sugestoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
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

    Mantemos JSON puro (e nao tabela) para o modelo poder citar IDs com
    precisao na justificativa.
    """
    payload = {
        "abastecimentos_nao_cadastrados": abastecimentos,
        "candidatos_gp_mesma_obra": candidatos,
        "instrucao": (
            "Para cada abastecimento, decida o melhor candidato_GP. Use null "
            "quando nada for >= 0.40 de confianca. Cite o ID do candidato "
            "escolhido na justificativa."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
