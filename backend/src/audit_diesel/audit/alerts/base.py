"""Interface comum dos alertas e contexto compartilhado."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlmodel import Session

from audit_diesel.models import Abastecimento, Checklist, Mobilizado


@dataclass
class AlertResult:
    """Resultado bruto de uma checagem; convertido em Alerta na persistencia."""

    tipo: str
    severidade: str
    titulo: str
    descricao: str
    payload: dict[str, Any] = field(default_factory=dict)
    abastecimento_id: int | None = None
    impacto_financeiro: float | None = None


@dataclass
class AuditContext:
    """Tudo que um Alert precisa para rodar.

    Os abastecimentos da janela ja vem filtrados pelo engine. O caller
    decide se a janela inclui obras especificas; aqui sao tratados como
    lista pura.
    """

    nf_anterior: Checklist
    nf_atual: Checklist
    abastecimentos_janela: list[Abastecimento]
    mobilizados: list[Mobilizado]
    session: Session


class Alert(Protocol):
    """Interface dos alertas. Cada tipo é uma classe stateless."""

    tipo: str

    def detectar(self, contexto: AuditContext) -> list[AlertResult]:
        """Aplica a checagem e devolve 0..N AlertResult."""
        ...
