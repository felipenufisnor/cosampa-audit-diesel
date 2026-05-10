"""Alerta: consumo atipico (z-score > limite) para o veiculo no historico completo."""

from __future__ import annotations

from collections import defaultdict
from math import sqrt

from sqlmodel import select

from audit_diesel.config import OUTLIER_MIN_HISTORICO, OUTLIER_ZSCORE_LIMITE
from audit_diesel.models import Abastecimento

from .base import AlertResult, AuditContext


class OutlierConsumoAlert:
    """Calcula media/desvio por veiculo na base inteira, sinaliza |z| > limite."""

    tipo: str = "OUTLIER"

    def detectar(self, contexto: AuditContext) -> list[AlertResult]:
        # Carrega todo o historico para calcular media/desvio por veiculo.
        historico = contexto.session.exec(select(Abastecimento)).all()
        por_veiculo: dict[str, list[float]] = defaultdict(list)
        for h in historico:
            por_veiculo[h.veiculo_normalizado].append(h.quantidade_litros)

        resultados: list[AlertResult] = []
        for ab in contexto.abastecimentos_janela:
            valores = por_veiculo.get(ab.veiculo_normalizado, [])
            n = len(valores)
            if n < OUTLIER_MIN_HISTORICO:
                continue
            media = sum(valores) / n
            var = sum((v - media) ** 2 for v in valores) / n
            desvio = sqrt(var)
            if desvio == 0:
                continue
            z = (ab.quantidade_litros - media) / desvio
            if abs(z) <= OUTLIER_ZSCORE_LIMITE:
                continue
            resultados.append(
                AlertResult(
                    tipo=self.tipo,
                    severidade="media",
                    titulo="Consumo atipico para o veiculo",
                    descricao=(
                        f"Abastecimento de {ab.quantidade_litros:.1f} L em "
                        f"{ab.veiculo_raw} (apelido: {ab.apelido or '-'}) tem z-score "
                        f"{z:.2f} (media historica {media:.1f} L, desvio {desvio:.1f} L "
                        f"em {n} observacoes)."
                    ),
                    payload={
                        "veiculo_raw": ab.veiculo_raw,
                        "data": ab.data.isoformat(),
                        "quantidade_litros": ab.quantidade_litros,
                        "media_historica": media,
                        "desvio_historico": desvio,
                        "n_observacoes": n,
                        "z_score": z,
                    },
                    abastecimento_id=ab.id,
                    impacto_financeiro=ab.custo_total,
                )
            )
        return resultados
