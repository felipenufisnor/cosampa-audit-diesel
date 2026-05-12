"""Teste E2E: roda o engine real contra o banco real (carregado dos xlsx)."""

from __future__ import annotations

import time

import pytest
from sqlmodel import Session

from audit_diesel.audit.engine import AuditEngine, ChecklistNaoEncontrado, ParTemporalInvalido
from audit_diesel.ingestion.pipeline import build_engine, ingerir


@pytest.fixture(scope="module")
def db_real(tmp_path_factory):
    """Ingere os xlsx reais uma vez para o modulo inteiro."""
    db = tmp_path_factory.mktemp("e2e") / "audit.db"
    ingerir(db_path=db, force=True)
    return db


def test_engine_caso_real_8108_8187(db_real):
    engine = build_engine(db_real)
    with Session(engine) as session:
        eng = AuditEngine(session)
        t0 = time.perf_counter()
        resultado = eng.auditar("8108", "8187")
        elapsed = time.perf_counter() - t0
    assert elapsed < 3.0, f"engine demorou {elapsed:.2f}s"

    a = resultado.auditoria
    # NF 8108: tanque=268.3, comboio=4362.0, qtd=15000.0
    # NF 8187: tanque=268.0, comboio=1092.0, qtd=15000.0
    assert a.estoque_inicial_anterior == pytest.approx(4630.3)
    assert a.estoque_final_teorico_anterior == pytest.approx(19630.3)
    assert a.estoque_inicial_atual == pytest.approx(1360.0)
    assert a.saida_teorica_litros == pytest.approx(18270.3)

    nao_cadastrados = [al for al in resultado.alertas if al.tipo == "NAO_CADASTRADO"]
    assert len(nao_cadastrados) > 0
    assert a.validacao_final == "INCONSISTENTE"


def test_engine_levanta_quando_nf_inexistente(db_real):
    engine = build_engine(db_real)
    with Session(engine) as session:
        eng = AuditEngine(session)
        with pytest.raises(ChecklistNaoEncontrado):
            eng.auditar("99999", "99998")


def test_engine_rejeita_nf_anterior_posterior(db_real):
    engine = build_engine(db_real)
    with Session(engine) as session:
        eng = AuditEngine(session)
        with pytest.raises(ParTemporalInvalido):
            eng.auditar("8187", "8108")


def test_engine_serializacao_dict(db_real):
    engine = build_engine(db_real)
    with Session(engine) as session:
        eng = AuditEngine(session)
        resultado = eng.auditar("8108", "8187")
    d = resultado.to_dict()
    assert "auditoria" in d and "alertas" in d
    a = d["auditoria"]
    for k in (
        "nf_anterior", "nf_atual", "estoque_inicial_anterior",
        "saida_teorica_litros", "diferenca_litros", "diferenca_percentual",
        "validacao_final",
    ):
        assert k in a
    if d["alertas"]:
        for k in ("tipo", "severidade", "titulo", "descricao", "payload"):
            assert k in d["alertas"][0]
