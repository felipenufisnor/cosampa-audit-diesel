"""Testes dos 4 tipos de alerta, com casos positivos e negativos."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from audit_diesel.audit.alert_dedup import deduplicar_nao_cadastrados
from audit_diesel.audit.alerts import (
    DuplicidadeAlert,
    NaoCadastradoAlert,
    OutlierConsumoAlert,
    PosDesmobilizacaoAlert,
)
from audit_diesel.audit.alerts.base import AuditContext
from audit_diesel.models import Abastecimento, Alerta


def _build_context(session, ck_ant, ck_atu, abastecimentos, mobilizados):
    # Persistir abastecimentos para que OutlierConsumoAlert possa consultar historico.
    for a in abastecimentos:
        session.add(a)
    session.commit()
    return AuditContext(
        nf_anterior=ck_ant,
        nf_atual=ck_atu,
        abastecimentos_janela=abastecimentos,
        mobilizados=mobilizados,
        session=session,
    )


class TestNaoCadastradoAlert:
    def test_dispara_quando_sem_match(self, session, checklist_par, abastecimento_padrao):
        ck_ant, ck_atu = checklist_par
        ctx = _build_context(session, ck_ant, ck_atu, [abastecimento_padrao], [])
        alertas = NaoCadastradoAlert().detectar(ctx)
        assert len(alertas) == 1
        assert alertas[0].tipo == "NAO_CADASTRADO"
        assert alertas[0].severidade == "alta"
        assert alertas[0].impacto_financeiro == 1300.0

    def test_nao_dispara_quando_cadastrado(
        self, session, checklist_par, abastecimento_padrao, mobilizado_padrao
    ):
        ck_ant, ck_atu = checklist_par
        ctx = _build_context(
            session, ck_ant, ck_atu, [abastecimento_padrao], [mobilizado_padrao]
        )
        assert NaoCadastradoAlert().detectar(ctx) == []

    def test_deduplica_mesmo_veiculo_e_mantem_maior_custo(self, session, checklist_par):
        ck_ant, ck_atu = checklist_par
        menor = Abastecimento(
            id=101,
            data=datetime(2026, 3, 4, 10, 0),
            veiculo_raw="OSB8826",
            veiculo_normalizado="OSB8826",
            apelido="34.002",
            quantidade_litros=100,
            custo_total=650.0,
            valor_litro=6.5,
        )
        maior = Abastecimento(
            id=102,
            data=datetime(2026, 3, 5, 10, 0),
            veiculo_raw="OSB8826",
            veiculo_normalizado="OSB8826",
            apelido="34.002",
            quantidade_litros=200,
            custo_total=1300.0,
            valor_litro=6.5,
        )
        outro = Abastecimento(
            id=103,
            data=datetime(2026, 3, 6, 10, 0),
            veiculo_raw="OIP6397",
            veiculo_normalizado="OIP6397",
            apelido="35.001",
            quantidade_litros=150,
            custo_total=975.0,
            valor_litro=6.5,
        )
        ctx = _build_context(session, ck_ant, ck_atu, [menor, maior, outro], [])

        alertas = NaoCadastradoAlert().detectar(ctx)

        assert len(alertas) == 2
        osb = next(a for a in alertas if a.payload["veiculo_normalizado"] == "OSB8826")
        assert osb.abastecimento_id == 102
        assert osb.impacto_financeiro == 1300.0


class TestPosDesmobilizacaoAlert:
    def test_dispara_quando_data_posterior(
        self, session, checklist_par, abastecimento_padrao, mobilizado_padrao
    ):
        mobilizado_padrao.data_desmobilizacao = datetime(2026, 3, 1)
        ck_ant, ck_atu = checklist_par
        ctx = _build_context(
            session, ck_ant, ck_atu, [abastecimento_padrao], [mobilizado_padrao]
        )
        alertas = PosDesmobilizacaoAlert().detectar(ctx)
        assert len(alertas) == 1
        assert "dias após desmobilização" in alertas[0].descricao

    def test_nao_dispara_quando_sem_desmob(
        self, session, checklist_par, abastecimento_padrao, mobilizado_padrao
    ):
        ck_ant, ck_atu = checklist_par
        ctx = _build_context(
            session, ck_ant, ck_atu, [abastecimento_padrao], [mobilizado_padrao]
        )
        assert PosDesmobilizacaoAlert().detectar(ctx) == []

    def test_nao_dispara_quando_data_anterior(
        self, session, checklist_par, abastecimento_padrao, mobilizado_padrao
    ):
        mobilizado_padrao.data_desmobilizacao = datetime(2026, 12, 31)
        ck_ant, ck_atu = checklist_par
        ctx = _build_context(
            session, ck_ant, ck_atu, [abastecimento_padrao], [mobilizado_padrao]
        )
        assert PosDesmobilizacaoAlert().detectar(ctx) == []


class TestOutlierConsumoAlert:
    def test_dispara_quando_z_score_alto(self, session, checklist_par):
        # 10 abastecimentos historicos pequenos + 1 enorme na janela; z > 3.
        historico = [
            Abastecimento(
                data=datetime(2026, 1, dia, 10, 0),
                veiculo_raw="X", veiculo_normalizado="X",
                quantidade_litros=50, custo_total=325, valor_litro=6.5,
            )
            for dia in range(1, 11)
        ]
        outlier = Abastecimento(
            data=datetime(2026, 3, 4, 10, 0),
            veiculo_raw="X", veiculo_normalizado="X",
            quantidade_litros=5000, custo_total=32500, valor_litro=6.5,
        )
        ck_ant, ck_atu = checklist_par
        ctx = _build_context(session, ck_ant, ck_atu, [outlier], [])
        # Persiste tambem o historico.
        for h in historico:
            session.add(h)
        session.commit()
        alertas = OutlierConsumoAlert().detectar(ctx)
        assert len(alertas) == 1
        assert alertas[0].severidade == "media"

    def test_nao_dispara_sem_historico(
        self, session, checklist_par, abastecimento_padrao
    ):
        ck_ant, ck_atu = checklist_par
        ctx = _build_context(session, ck_ant, ck_atu, [abastecimento_padrao], [])
        # Apenas o proprio abastecimento na base; n=1 < OUTLIER_MIN_HISTORICO.
        assert OutlierConsumoAlert().detectar(ctx) == []

    def test_nao_dispara_com_desvio_zero(self, session, checklist_par):
        # Historico todos iguais; desvio = 0; nao deve disparar.
        historico = [
            Abastecimento(
                data=datetime(2026, 1, dia, 10, 0),
                veiculo_raw="X", veiculo_normalizado="X",
                quantidade_litros=100, custo_total=650, valor_litro=6.5,
            )
            for dia in range(1, 7)
        ]
        for h in historico:
            session.add(h)
        atual = Abastecimento(
            data=datetime(2026, 3, 4, 10, 0),
            veiculo_raw="X", veiculo_normalizado="X",
            quantidade_litros=100, custo_total=650, valor_litro=6.5,
        )
        session.add(atual)
        session.commit()
        ck_ant, ck_atu = checklist_par
        ctx = AuditContext(
            nf_anterior=ck_ant, nf_atual=ck_atu,
            abastecimentos_janela=[atual], mobilizados=[], session=session,
        )
        assert OutlierConsumoAlert().detectar(ctx) == []


class TestDuplicidadeAlert:
    def test_dispara_para_mesmo_dia_mesmo_veiculo(self, session, checklist_par):
        ck_ant, ck_atu = checklist_par
        a1 = Abastecimento(
            data=datetime(2026, 3, 4, 10, 0), veiculo_raw="X",
            veiculo_normalizado="X", quantidade_litros=100,
            custo_total=650, valor_litro=6.5,
        )
        a2 = Abastecimento(
            data=datetime(2026, 3, 4, 15, 0), veiculo_raw="X",
            veiculo_normalizado="X", quantidade_litros=80,
            custo_total=520, valor_litro=6.5,
        )
        ctx = _build_context(session, ck_ant, ck_atu, [a1, a2], [])
        alertas = DuplicidadeAlert().detectar(ctx)
        assert len(alertas) == 1
        assert alertas[0].severidade == "baixa"
        assert alertas[0].payload["n_abastecimentos"] == 2

    def test_nao_dispara_se_dias_diferentes(self, session, checklist_par):
        ck_ant, ck_atu = checklist_par
        a1 = Abastecimento(
            data=datetime(2026, 3, 4, 10, 0), veiculo_raw="X",
            veiculo_normalizado="X", quantidade_litros=100,
            custo_total=650, valor_litro=6.5,
        )
        a2 = Abastecimento(
            data=datetime(2026, 3, 5, 10, 0), veiculo_raw="X",
            veiculo_normalizado="X", quantidade_litros=80,
            custo_total=520, valor_litro=6.5,
        )
        ctx = _build_context(session, ck_ant, ck_atu, [a1, a2], [])
        assert DuplicidadeAlert().detectar(ctx) == []


@pytest.mark.parametrize(
    "alert_cls,attr",
    [
        (NaoCadastradoAlert, "tipo"),
        (PosDesmobilizacaoAlert, "tipo"),
        (OutlierConsumoAlert, "tipo"),
        (DuplicidadeAlert, "tipo"),
    ],
)
def test_alertas_tem_tipo_definido(alert_cls, attr):
    assert hasattr(alert_cls(), attr)
    assert getattr(alert_cls(), attr) != ""


def test_deduplica_alertas_persistidos_por_veiculo_e_maior_impacto():
    alertas = [
        Alerta(
            id=1,
            auditoria_id=10,
            tipo="NAO_CADASTRADO",
            severidade="alta",
            abastecimento_id=101,
            titulo="Equipamento não cadastrado no GP",
            descricao="menor",
            payload_json=json.dumps({"veiculo_normalizado": "OSB8826"}),
            impacto_financeiro=650.0,
        ),
        Alerta(
            id=2,
            auditoria_id=10,
            tipo="NAO_CADASTRADO",
            severidade="alta",
            abastecimento_id=102,
            titulo="Equipamento não cadastrado no GP",
            descricao="maior",
            payload_json=json.dumps({"veiculo_normalizado": "OSB8826"}),
            impacto_financeiro=1300.0,
        ),
        Alerta(
            id=3,
            auditoria_id=10,
            tipo="DUPLICIDADE",
            severidade="baixa",
            abastecimento_id=None,
            titulo="Possível duplicidade",
            descricao="mantem outros tipos",
            payload_json="{}",
            impacto_financeiro=None,
        ),
    ]

    dedup = deduplicar_nao_cadastrados(alertas)

    assert [a.id for a in dedup] == [2, 3]
