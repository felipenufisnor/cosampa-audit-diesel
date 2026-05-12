"""Tools expostas ao Assistente de Investigacao (Feature B da v2).

Cada funcao e' uma `tool` no formato OpenAI/OpenRouter. Recebe argumentos
ja deserializados a partir do JSON do `tool_calls` do modelo, executa
contra o banco e retorna um dict serializavel (que sera passado de volta
ao modelo como `role=tool` content).

As tools NAO sao expostas via HTTP nem chamadas pelo frontend; sao
sempre invocadas pelo orquestrador `ai.assistente` no servidor.
"""

from __future__ import annotations

from .comparar_nfs import comparar_nfs
from .consultar_abastecimento import consultar_abastecimento
from .consultar_obra_no_periodo import consultar_obra_no_periodo
from .consultar_veiculo import consultar_veiculo
from .schemas import TOOL_SCHEMAS, TOOLS_REGISTRY

__all__ = [
    "TOOLS_REGISTRY",
    "TOOL_SCHEMAS",
    "comparar_nfs",
    "consultar_abastecimento",
    "consultar_obra_no_periodo",
    "consultar_veiculo",
]
