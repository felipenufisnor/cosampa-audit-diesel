"""Testes de ingestao contra os xlsx reais e teste de idempotencia."""

from __future__ import annotations

from sqlmodel import Session, select

from audit_diesel.config import (
    CHECKLIST_FILENAME,
    INFLEET_FILENAME,
    MOBILIZADOS_FILENAME,
)
from audit_diesel.ingestion.checklist import carregar_checklists
from audit_diesel.ingestion.infleet import carregar_abastecimentos
from audit_diesel.ingestion.mobilizados import carregar_mobilizados
from audit_diesel.ingestion.pipeline import build_engine, ingerir
from audit_diesel.models import Abastecimento, Checklist, Mobilizado


def test_carregar_checklists_real(raw_dir):
    cks = carregar_checklists(raw_dir / CHECKLIST_FILENAME)
    assert len(cks) == 4
    nfs = {c.nota_fiscal for c in cks}
    assert {"8108", "8187", "8278", "8328"} == nfs


def test_carregar_mobilizados_real(raw_dir):
    mobs = carregar_mobilizados(raw_dir / MOBILIZADOS_FILENAME)
    assert len(mobs) == 286
    # Pelo menos um equipamento conhecido foi normalizado certo.
    placas = {m.placa_ativo_normalizada for m in mobs}
    assert "07T586" in placas
    assert "EH01" in placas


def test_carregar_abastecimentos_real(raw_dir):
    abasts = carregar_abastecimentos(raw_dir / INFLEET_FILENAME)
    assert len(abasts) == 1862
    # Spot-check no primeiro registro: data combinada esperada.
    primeiro = next(a for a in abasts if a.veiculo_raw == "17.T195")
    assert primeiro.data.year == 2026


def test_ingest_idempotente(db_path_tmp, raw_dir):
    """Rodar duas vezes resulta no mesmo conteudo do banco."""
    r1 = ingerir(raw_dir=raw_dir, db_path=db_path_tmp, force=True)
    r2 = ingerir(raw_dir=raw_dir, db_path=db_path_tmp, force=True)
    assert r1.abastecimentos == r2.abastecimentos == 1862
    assert r1.mobilizados == r2.mobilizados == 286
    assert r1.checklists == r2.checklists == 4

    engine = build_engine(db_path_tmp)
    with Session(engine) as session:
        assert len(session.exec(select(Abastecimento)).all()) == 1862
        assert len(session.exec(select(Mobilizado)).all()) == 286
        assert len(session.exec(select(Checklist)).all()) == 4


def test_ingest_sem_force_tambem_idempotente(db_path_tmp, raw_dir):
    """Rodar sem --force deve limpar dados anteriores e produzir mesmas contagens."""
    ingerir(raw_dir=raw_dir, db_path=db_path_tmp, force=True)
    r2 = ingerir(raw_dir=raw_dir, db_path=db_path_tmp, force=False)
    assert r2.abastecimentos == 1862
    assert r2.mobilizados == 286
    assert r2.checklists == 4
