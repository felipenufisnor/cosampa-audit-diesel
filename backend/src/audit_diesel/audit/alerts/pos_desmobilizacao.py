"""Alerta: abastecimento registrado apos a data de desmobilizacao do equipamento."""

from __future__ import annotations

from .base import AlertResult, AuditContext


class PosDesmobilizacaoAlert:
    """Detecta abastecimentos com data > data_desmobilizacao do mobilizado correspondente."""

    tipo: str = "POS_DESMOB"

    def detectar(self, contexto: AuditContext) -> list[AlertResult]:
        index = {m.placa_ativo_normalizada: m for m in contexto.mobilizados if m.placa_ativo_normalizada}
        resultados: list[AlertResult] = []
        for ab in contexto.abastecimentos_janela:
            mob = index.get(ab.veiculo_normalizado)
            if mob is None or mob.data_desmobilizacao is None:
                continue
            if ab.data <= mob.data_desmobilizacao:
                continue
            delta_dias = (ab.data - mob.data_desmobilizacao).days
            resultados.append(
                AlertResult(
                    tipo=self.tipo,
                    severidade="alta",
                    titulo="Abastecimento após desmobilização",
                    descricao=(
                        f"Veículo {mob.placa_ativo_raw} foi desmobilizado em "
                        f"{mob.data_desmobilizacao:%d/%m/%Y} mas registra abastecimento em "
                        f"{ab.data:%d/%m/%Y} ({delta_dias} dias após desmobilização)."
                    ),
                    payload={
                        "veiculo_raw": ab.veiculo_raw,
                        "data_desmobilizacao": mob.data_desmobilizacao.isoformat(),
                        "data_abastecimento": ab.data.isoformat(),
                        "delta_dias": delta_dias,
                        "quantidade_litros": ab.quantidade_litros,
                    },
                    abastecimento_id=ab.id,
                    impacto_financeiro=ab.custo_total,
                )
            )
        return resultados
