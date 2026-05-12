"""Schemas das tools no formato OpenAI + registry de dispatchers.

Cada entrada de `TOOL_SCHEMAS` segue o formato OpenAI/OpenRouter:
{
  "type": "function",
  "function": {
    "name": ...,
    "description": ...,
    "parameters": {JSON Schema}
  }
}

`TOOLS_REGISTRY[name]` retorna uma funcao `(session, **kwargs) -> dict`
que executa a tool. O orquestrador passa `**arguments` ja deserializados.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from .comparar_nfs import comparar_nfs
from .consultar_abastecimento import consultar_abastecimento
from .consultar_obra_no_periodo import consultar_obra_no_periodo
from .consultar_veiculo import consultar_veiculo

ToolDispatcher = Callable[..., dict[str, Any]]


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "consultar_abastecimento",
            "description": (
                "Retorna detalhes de um unico abastecimento (litros, custo, "
                "veiculo, fornecedor) e indica se a placa esta cadastrada no GP."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "abastecimento_id": {
                        "type": "integer",
                        "description": "id do abastecimento (Infleet)",
                    },
                },
                "required": ["abastecimento_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_veiculo",
            "description": (
                "Retorna o historico recente de abastecimentos de um veiculo "
                "(default: ultimos 28 dias) e seu cadastro no GP, se houver."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "placa": {
                        "type": "string",
                        "description": "placa ou identificador do ativo",
                    },
                    "dias": {
                        "type": "integer",
                        "description": "janela em dias (default 28)",
                        "default": 28,
                    },
                },
                "required": ["placa"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_obra_no_periodo",
            "description": (
                "Retorna agregados (litros, custo), auditorias e alertas de "
                "uma obra em um periodo entre duas datas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "obra": {
                        "type": "string",
                        "description": "nome da obra (igual ao do cadastro)",
                    },
                    "inicio": {
                        "type": "string",
                        "description": "data inicial ISO 8601 (YYYY-MM-DD)",
                    },
                    "fim": {
                        "type": "string",
                        "description": "data final ISO 8601 (YYYY-MM-DD)",
                    },
                },
                "required": ["obra", "inicio", "fim"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comparar_nfs",
            "description": (
                "Compara as auditorias mais recentes de duas NFs: deltas de "
                "diferenca %, nao cadastrados e saidas registradas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nf_a": {"type": "string", "description": "primeira NF"},
                    "nf_b": {"type": "string", "description": "segunda NF"},
                },
                "required": ["nf_a", "nf_b"],
            },
        },
    },
]


def _wrap(fn: ToolDispatcher) -> ToolDispatcher:
    def runner(session: Session, **kwargs: Any) -> dict[str, Any]:
        return fn(session, **kwargs)
    return runner


TOOLS_REGISTRY: dict[str, ToolDispatcher] = {
    "consultar_abastecimento": _wrap(consultar_abastecimento),
    "consultar_veiculo": _wrap(consultar_veiculo),
    "consultar_obra_no_periodo": _wrap(consultar_obra_no_periodo),
    "comparar_nfs": _wrap(comparar_nfs),
}
