"""Parecer deterministico usado pelo offline e como fallback seguro."""

from __future__ import annotations

from typing import Any


def gerar_parecer_deterministico(payload: dict[str, Any]) -> str:
    """Gera parecer técnico sem LLM, derivado apenas dos dados recebidos."""
    auditoria = payload.get("auditoria") or payload
    alertas = payload.get("alertas") or []

    diff_pct = float(auditoria.get("diferenca_percentual") or 0.0) * 100.0
    nao_cad = int(auditoria.get("qtd_equipamentos_nao_cadastrados") or 0)
    validacao = str(auditoria.get("validacao_final") or "INCONSISTENTE")
    diff_l = float(auditoria.get("diferenca_litros") or 0.0)
    saida_teorica = float(auditoria.get("saida_teorica_litros") or 0.0)
    saidas_reg = float(auditoria.get("saidas_registradas_litros") or 0.0)
    nf_atual = auditoria.get("nf_atual")

    impacto_total = sum(
        float(a.get("impacto_financeiro") or 0.0)
        for a in alertas
    )

    if nao_cad >= 5:
        causa = "Situação 3 (alta quantidade de não cadastrados)"
        causa_evidencia = (
            f"{nao_cad} abastecimentos da janela ocorreram em equipamentos "
            f"sem cadastro correspondente no GP, dominando o sinal de "
            f"inconsistência (diferença de {diff_l:.1f} L / {diff_pct:+.2f}%)."
        )
    elif abs(diff_pct) >= 5:
        causa = "Situação 2 (saídas muito acima do esperado)"
        causa_evidencia = (
            f"Saídas registradas no Infleet ({saidas_reg:.0f} L) divergem em "
            f"{diff_pct:+.2f}% da saída teórica ({saida_teorica:.0f} L), "
            f"compatível com registros faltantes ou consumo não reportado."
        )
    else:
        causa = "Situação 1 (divergência no recebimento)"
        causa_evidencia = (
            f"A diferença total ({diff_l:.1f} L / {diff_pct:+.2f}%) é pequena "
            f"e o número de não cadastrados ({nao_cad}) é baixo, sugerindo "
            f"discrepância pontual no checklist do recebimento."
        )

    return (
        f"**Resultado**\n"
        f"{validacao}: diferença de {diff_pct:+.2f}% entre saídas Infleet e "
        f"saída teórica; {nao_cad} equipamento(s) sem cadastro no GP.\n\n"
        f"**Causa mais provável**\n"
        f"{causa}. {causa_evidencia}\n\n"
        f"**Recomendação ao auditor**\n"
        f"1. Cobre a inserção no GP dos {nao_cad} equipamento(s) abastecido(s) "
        f"sem cadastro durante a janela.\n"
        f"2. Solicite à obra a relação de saídas de comboio não registradas "
        f"no Infleet entre o descarregamento da NF anterior e a NF {nf_atual}.\n"
        f"3. Confirme com o estoquista os valores de tanque e comboio "
        f"informados no checklist da NF {nf_atual} antes de fechar o mês.\n\n"
        f"**Risco financeiro associado**\n"
        f"R$ {_brl(impacto_total)} em alertas com impacto financeiro na janela "
        f"(não cadastrados, pós-desmobilização, outliers e duplicidades)."
    )


def _brl(v: float) -> str:
    s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")
