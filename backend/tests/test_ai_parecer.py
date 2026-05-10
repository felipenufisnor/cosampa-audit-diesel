"""Testes do GeradorParecer rodando contra o OfflineProvider."""

from __future__ import annotations

import os

from audit_diesel.ai.client import ChatClient
from audit_diesel.ai.parecer import GeradorParecer
from audit_diesel.ai.provider import OfflineProvider
from audit_diesel.config import Settings


def _gerador() -> GeradorParecer:
    os.environ["AUDIT_AI_OFFLINE"] = "1"
    settings = Settings()
    return GeradorParecer(client=ChatClient(provider=OfflineProvider(settings), settings=settings))


def _payload(diff_pct: float, qtd_nao_cad: int, validacao: str = "INCONSISTENTE") -> dict:
    return {
        "auditoria": {
            "nf_atual": "8187",
            "nf_anterior": "8108",
            "diferenca_percentual": diff_pct,
            "diferenca_litros": diff_pct * 18000,
            "qtd_equipamentos_nao_cadastrados": qtd_nao_cad,
            "validacao_final": validacao,
            "saida_teorica_litros": 18000,
            "saidas_registradas_litros": 18000 + diff_pct * 18000,
        },
        "alertas": [
            {"severidade": "alta", "impacto_financeiro": 1200.0},
            {"severidade": "alta", "impacto_financeiro": 800.5},
        ],
    }


def test_parecer_contem_4_blocos_e_eh_curto():
    p = _gerador().gerar(_payload(diff_pct=0.005, qtd_nao_cad=10))
    md = p.markdown
    for bloco in (
        "**Resultado**",
        "**Causa mais provavel**",
        "**Recomendacao ao auditor**",
        "**Risco financeiro associado**",
    ):
        assert bloco in md, f"bloco ausente: {bloco}"
    assert len(md.split()) <= 220, "parecer com mais de 220 palavras"


def test_parecer_situacao_3_quando_dominam_nao_cadastrados():
    p = _gerador().gerar(_payload(diff_pct=0.005, qtd_nao_cad=20))
    assert "Situacao 3" in p.markdown


def test_parecer_situacao_2_quando_diferenca_alta():
    p = _gerador().gerar(_payload(diff_pct=0.10, qtd_nao_cad=2))
    assert "Situacao 2" in p.markdown


def test_parecer_situacao_1_quando_tudo_pequeno():
    p = _gerador().gerar(_payload(diff_pct=0.01, qtd_nao_cad=1))
    assert "Situacao 1" in p.markdown


def test_parecer_metadata_offline():
    p = _gerador().gerar(_payload(diff_pct=0.005, qtd_nao_cad=10))
    assert p.offline is True
    assert p.provider == "offline"
    assert p.prompt_tokens > 0
    assert p.completion_tokens > 0
