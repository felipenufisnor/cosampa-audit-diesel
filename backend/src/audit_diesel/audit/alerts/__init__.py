"""Conjunto de checagens (Alerts) que rodam contra uma janela de auditoria."""

from .base import Alert, AlertResult, AuditContext
from .duplicidade import DuplicidadeAlert
from .nao_cadastrado import NaoCadastradoAlert
from .outlier_consumo import OutlierConsumoAlert
from .pos_desmobilizacao import PosDesmobilizacaoAlert

ALERTAS_PADRAO: list[Alert] = [
    NaoCadastradoAlert(),
    PosDesmobilizacaoAlert(),
    OutlierConsumoAlert(),
    DuplicidadeAlert(),
]

__all__ = [
    "ALERTAS_PADRAO",
    "Alert",
    "AlertResult",
    "AuditContext",
    "DuplicidadeAlert",
    "NaoCadastradoAlert",
    "OutlierConsumoAlert",
    "PosDesmobilizacaoAlert",
]
