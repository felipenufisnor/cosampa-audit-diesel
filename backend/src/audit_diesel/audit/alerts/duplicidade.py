"""Alerta: dois ou mais abastecimentos do mesmo veiculo no mesmo dia."""

from __future__ import annotations

from collections import defaultdict

from .base import AlertResult, AuditContext


class DuplicidadeAlert:
    """Agrupa por (veiculo_normalizado, data.date()); count >= 2 -> 1 alerta."""

    tipo: str = "DUPLICIDADE"

    def detectar(self, contexto: AuditContext) -> list[AlertResult]:
        grupos: dict[tuple[str, str], list] = defaultdict(list)
        for ab in contexto.abastecimentos_janela:
            chave = (ab.veiculo_normalizado, ab.data.date().isoformat())
            grupos[chave].append(ab)

        resultados: list[AlertResult] = []
        for (veiculo, dia), itens in grupos.items():
            if len(itens) < 2:
                continue
            ids = [i.id for i in itens if i.id is not None]
            total_litros = sum(i.quantidade_litros for i in itens)
            total_custo = sum(i.custo_total for i in itens)
            resultados.append(
                AlertResult(
                    tipo=self.tipo,
                    severidade="baixa",
                    titulo="Multiplos abastecimentos no mesmo dia",
                    descricao=(
                        f"Veiculo {itens[0].veiculo_raw} (apelido: "
                        f"{itens[0].apelido or '-'}) tem {len(itens)} abastecimentos em "
                        f"{dia} totalizando {total_litros:.1f} L (R$ {total_custo:,.2f})."
                    ),
                    payload={
                        "veiculo_normalizado": veiculo,
                        "data": dia,
                        "abastecimentos_ids": ids,
                        "quantidade_total_litros": total_litros,
                        "custo_total": total_custo,
                        "n_abastecimentos": len(itens),
                    },
                    impacto_financeiro=None,
                )
            )
        return resultados
