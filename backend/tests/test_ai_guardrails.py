from __future__ import annotations

import os
from typing import Any

import pytest

from audit_diesel.ai.client import ChatClient, ChatMessage
from audit_diesel.ai.parecer import GeradorParecer
from audit_diesel.ai.parecer_deterministico import gerar_parecer_deterministico
from audit_diesel.ai.parecer_guardrails import validar_parecer
from audit_diesel.ai.provider import ProviderInfo
from audit_diesel.ai.reconciliador import (
    _extrair_sugestoes,
    _sanitizar_sugestoes,
    _SugestaoLLM,
)
from audit_diesel.config import Settings


def _payload() -> dict[str, Any]:
    return {
        "auditoria": {
            "nf_atual": "8187",
            "nf_anterior": "8108",
            "diferenca_percentual": 0.005,
            "diferenca_litros": 90.0,
            "qtd_equipamentos_nao_cadastrados": 10,
            "validacao_final": "INCONSISTENTE",
            "saida_teorica_litros": 18000,
            "saidas_registradas_litros": 18090,
        },
        "alertas": [{"severidade": "alta", "impacto_financeiro": 1200.0}],
    }


def test_parecer_valido_passa_guardrail():
    md = gerar_parecer_deterministico(_payload())
    validation = validar_parecer(md, _payload())
    assert validation.ok, validation.errors


def test_parecer_rejeita_blocos_ausentes():
    validation = validar_parecer("INCONSISTENTE: texto solto.", _payload())
    assert not validation.ok
    assert any("blocos" in e for e in validation.errors)


def test_parecer_rejeita_excesso_de_palavras():
    md = gerar_parecer_deterministico(_payload()) + "\n" + ("extra " * 230)
    validation = validar_parecer(md, _payload())
    assert not validation.ok
    assert any("220" in e for e in validation.errors)


def test_parecer_rejeita_code_fence_status_errado_e_numero_inventado():
    md = gerar_parecer_deterministico(_payload())
    md = md.replace("INCONSISTENTE", "APROVADO", 1)
    md = "```markdown\n" + md + "\nR$ 999.999,99\n```"
    validation = validar_parecer(md, _payload())
    assert not validation.ok
    assert any("cerca" in e for e in validation.errors)
    assert any("status" in e for e in validation.errors)
    assert any("números" in e for e in validation.errors)


def test_reconciliacao_sanitiza_id_inexistente_duplicado_e_faltante():
    sugestoes = [
        _SugestaoLLM(
            abastecimento_id=1,
            mobilizado_id_candidato=999,
            confianca=0.9,
            justificativa="id inventado",
        ),
        _SugestaoLLM(
            abastecimento_id=2,
            mobilizado_id_candidato=10,
            confianca=0.9,
            justificativa="ok 1",
        ),
        _SugestaoLLM(
            abastecimento_id=2,
            mobilizado_id_candidato=10,
            confianca=0.9,
            justificativa="ok 2",
        ),
        _SugestaoLLM(
            abastecimento_id=999,
            mobilizado_id_candidato=10,
            confianca=0.9,
            justificativa="abastecimento inventado",
        ),
    ]
    out = _sanitizar_sugestoes(sugestoes, abastecimento_ids=[1, 2, 3], candidato_ids={10})
    assert [s.abastecimento_id for s in out] == [1, 2, 3]
    assert all(s.mobilizado_id_candidato is None for s in out)
    assert all(s.confianca == 0.0 for s in out)


def test_reconciliacao_parseia_json_em_content_sem_tool_call():
    class Response:
        tool_calls: list[Any] = []
        content = (
            '{"sugestoes":[{"abastecimento_id":1,"mobilizado_id_candidato":null,'
            '"confianca":0.0,"justificativa":"sem match"}]}'
        )

    out = _extrair_sugestoes(Response())
    assert out is not None
    assert out[0].abastecimento_id == 1


def test_reconciliacao_resposta_invalida_sinaliza_parse_fail():
    class Response:
        tool_calls: list[Any] = []
        content = "não é json"

    assert _extrair_sugestoes(Response()) is None


def test_parecer_degrada_para_deterministico_apos_qwen_reparo_e_deepseek_invalidos():
    class FakeProvider:
        def __init__(self) -> None:
            self.info = ProviderInfo(
                name="fake",
                base_url="local://fake",
                model="qwen",
                offline=False,
            )
            self.models: list[str] = []

        def chat(self, **kwargs: Any) -> dict[str, Any]:
            self.models.append(str(kwargs.get("model")))
            return {
                "model": kwargs.get("model"),
                "choices": [
                    {
                        "message": {"content": "APROVADO 999999", "tool_calls": None},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

    provider = FakeProvider()
    settings = Settings(
        llm_model="qwen",
        llm_fallback_model="deepseek",
        audit_ai_offline=False,
        llm_api_key="fake",
    )
    gerador = GeradorParecer(client=ChatClient(provider=provider, settings=settings))
    result = gerador.gerar(_payload())
    assert provider.models == ["qwen", "qwen", "deepseek"]
    assert result.provider == "deterministic_fallback"
    assert result.modelo == "deterministic-parecer-fallback"
    assert validar_parecer(result.markdown, _payload()).ok


@pytest.mark.real_llm
def test_real_llm_preflight_opt_in():
    if os.environ.get("RUN_REAL_LLM_TESTS") != "1":
        pytest.skip("RUN_REAL_LLM_TESTS=1 não definido")
    settings = Settings()
    if settings.audit_ai_offline or settings.demo_replay or not settings.llm_api_key:
        pytest.skip("provider real não configurado")
    client = ChatClient(settings=settings)
    response = client.chat(
        messages=[
            ChatMessage(role="system", content="Responda apenas OK."),
            ChatMessage(role="user", content="OK"),
        ],
        max_tokens=8,
        temperature=0.0,
    )
    assert response.content
