"""Camada de IA. Provider-agnostico, fala dialeto OpenAI Chat Completions.

Composta por:
    - provider.py    : interface LLMProvider + factory
    - client.py      : ChatClient (retry, timeout, logs estruturados)
    - prompts/       : prompts e schemas das tarefas (reconciliador, parecer)
    - reconciliador.py / parecer.py : domain logic que monta input,
      chama o client, parseia output e valida.
"""

from .client import ChatClient, ChatMessage, ChatResponse
from .provider import LLMProvider, get_provider
from .reconciliador import ReconciliadorSemantico, SugestaoReconciliacao
from .parecer import GeradorParecer

__all__ = [
    "ChatClient",
    "ChatMessage",
    "ChatResponse",
    "GeradorParecer",
    "LLMProvider",
    "ReconciliadorSemantico",
    "SugestaoReconciliacao",
    "get_provider",
]
