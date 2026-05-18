"""Alerta: abastecimento de veiculo sem cadastro correspondente no GP."""

from __future__ import annotations

from .base import AlertResult, AuditContext


class NaoCadastradoAlert:
    """Para cada abastecimento da janela, exige um Mobilizado com a placa correspondente."""

    tipo: str = "NAO_CADASTRADO"

    def detectar(self, contexto: AuditContext) -> list[AlertResult]:
        cadastrados = {m.placa_ativo_normalizada for m in contexto.mobilizados if m.placa_ativo_normalizada}
        representantes = {}
        for ab in contexto.abastecimentos_janela:
            if ab.veiculo_normalizado in cadastrados:
                continue
            key = ab.veiculo_normalizado or ab.veiculo_raw
            atual = representantes.get(key)
            if atual is None or ab.custo_total > atual.custo_total:
                representantes[key] = ab

        resultados: list[AlertResult] = []
        for ab in representantes.values():
            resultados.append(
                AlertResult(
                    tipo=self.tipo,
                    severidade="alta",
                    titulo="Equipamento não cadastrado no GP",
                    descricao=(
                        f"Veículo {ab.veiculo_raw} (apelido: {ab.apelido or '-'}) "
                        f"abastecido em {ab.data:%d/%m/%Y %H:%M} mas sem cadastro "
                        f"correspondente no GP."
                    ),
                    payload={
                        "veiculo_raw": ab.veiculo_raw,
                        "veiculo_normalizado": ab.veiculo_normalizado,
                        "apelido": ab.apelido,
                        "data": ab.data.isoformat(),
                        "quantidade_litros": ab.quantidade_litros,
                        "custo_total": ab.custo_total,
                    },
                    abastecimento_id=ab.id,
                    impacto_financeiro=ab.custo_total,
                )
            )
        return resultados
