"""Testes do ReconciliadorSemantico contra fixture com casos conhecidos.

Usa OfflineProvider; inclui um teste de "acuracia" sobre 10 casos sinteticos:
o reconciliador deve devolver candidato com confianca >= 0.65 em pelo menos 7
deles. Os casos foram desenhados para serem resolveis pelas heuristicas do
fixture (placa identica, equipamento citado no apelido etc.).
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from audit_diesel.ai.client import ChatClient
from audit_diesel.ai.provider import OfflineProvider
from audit_diesel.ai.reconciliador import ReconciliadorSemantico
from audit_diesel.audit.engine import AuditEngine
from audit_diesel.config import Settings
from audit_diesel.models import Abastecimento, Checklist, Mobilizado


@pytest.fixture
def session_isolada():
    eng = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        yield s


@pytest.fixture
def reconciliador(session_isolada):
    os.environ["AUDIT_AI_OFFLINE"] = "1"
    settings = Settings()
    client = ChatClient(provider=OfflineProvider(settings), settings=settings)
    return ReconciliadorSemantico(session=session_isolada, client=client)


def _checklist(nf: str, dt: datetime) -> Checklist:
    from datetime import time
    return Checklist(
        numero_chamado="x",
        nota_fiscal=nf,
        nome_obra="OBRA TESTE",
        cnpj_fornecedor="00",
        data_recebimento=dt,
        hora_inicio_descarga=time(8),
        hora_final_descarga=time(9),
        datetime_fim_descarga=dt,
        quantidade_nf_litros=15000,
        volume_conferido_litros=15000,
        estoque_antes_tanque_litros=200,
        estoque_antes_comboio_litros=300,
        preco_unitario=6.5,
        valor_total_nf=97500,
    )


def _mobilizado(
    id_: int,
    placa: str,
    placa_norm: str,
    equip: str,
    marca: str = "M",
    modelo: str = "X",
) -> Mobilizado:
    return Mobilizado(
        id=id_,
        codigo_projeto="1211",
        nome_obra="OBRA TESTE",
        equipamento=equip,
        marca=marca,
        modelo=modelo,
        placa_ativo_raw=placa,
        placa_ativo_normalizada=placa_norm,
        situacao="MOBILIZADO",
    )


def _abastecimento(
    id_: int,
    veiculo: str,
    veiculo_norm: str,
    apelido: str | None,
    dt: datetime,
) -> Abastecimento:
    return Abastecimento(
        id=id_,
        data=dt,
        veiculo_raw=veiculo,
        veiculo_normalizado=veiculo_norm,
        apelido=apelido,
        quantidade_litros=100,
        custo_total=650,
        valor_litro=6.5,
    )


def _seed_dataset(session: Session) -> int:
    """Cria 10 casos de reconciliacao + auditoria associada. Retorna auditoria_id.

    Cada caso eh montado para que a heuristica do fixture devolva candidato
    com confianca >= 0.65 em pelo menos 7 deles.
    """
    # 10 mobilizados, todos com identificadores claramente DIFERENTES dos veiculos
    # do Infleet, exigindo que o reconciliador resolva por similaridade/semantica.
    mobs = [
        _mobilizado(1,  "07.T586",  "07T586",  "ROLO VIBRATORIO LISO"),
        _mobilizado(2,  "EH01",     "EH01",    "ESCAVADEIRA HIDRAULICA"),
        _mobilizado(3,  "13.T881",  "13T881",  "CALDEIRA"),
        _mobilizado(4,  "MN01",     "MN01",    "MOTONIVELADORA"),
        _mobilizado(5,  "RC01",     "RC01",    "ROMPEDOR HIDRAULICO"),
        _mobilizado(6,  "11.003",   "11003",   "PERFURATRIZ"),
        _mobilizado(7,  "NUY4231",  "NUY4231", "CAMINHAO PIPA"),
        _mobilizado(8,  "CB11",     "CB11",    "CAMINHAO BASCULANTE"),
        _mobilizado(9,  "PFK1D32",  "PFK1D32", "CARRETA"),
        _mobilizado(10, "GE-05",    "GE05",    "GERADOR"),
    ]
    for m in mobs:
        session.add(m)

    # 10 abastecimentos com veiculo_normalizado distinto de todas as placas GP
    # (forca virem como NAO_CADASTRADO). 7 trazem pista semantica (apelido casa
    # com Equipamento) ou identificador parcial; 3 sao genericamente
    # nao-resolveis.
    base = datetime(2026, 3, 6, 9, 0)
    abs_ = [
        _abastecimento(101, "INFLEET-07T586", "INFLEET07T586", "ROL-01",                base),
        _abastecimento(102, "I-EH01",         "IEH01",         "ESCAVADEIRA HIDRAULICA",base),
        _abastecimento(103, "MARTINHO",       "MARTINHO",      "CALDEIRA US ASF-01",    base),
        _abastecimento(104, "INF-MN01",       "INFMN01",       "MOTONIVELADORA",        base),
        _abastecimento(105, "X-RC01",         "XRC01",         "ROMPEDOR HIDRAULICO",   base),
        _abastecimento(106, "P-11003",        "P11003",        "PERFURATRIZ",           base),
        _abastecimento(107, "PIPA-NUY4231",   "PIPANUY4231",   "CAMINHAO PIPA - JP",    base),
        _abastecimento(108, "ZZZ-001",        "ZZZ001",        None,                    base),
        _abastecimento(109, "ZZZ-002",        "ZZZ002",        "operador alfa",         base),
        _abastecimento(110, "ZZZ-003",        "ZZZ003",        "turno noite",           base),
    ]
    for a in abs_:
        session.add(a)

    # checklists antes/depois para o engine criar a auditoria.
    session.add(_checklist("ANT", datetime(2026, 3, 5, 9, 0)))
    session.add(_checklist("ATU", datetime(2026, 3, 7, 9, 0)))
    session.commit()

    auditoria = AuditEngine(session).auditar("ANT", "ATU")
    return int(auditoria.auditoria.id or 0)


def test_reconciliador_acuracia_alvo_70pct(reconciliador, session_isolada):
    auditoria_id = _seed_dataset(session_isolada)
    sugestoes = reconciliador.sugerir_para_auditoria(auditoria_id)
    assert len(sugestoes) == 10
    high = [s for s in sugestoes if s.confianca >= 0.65]
    assert len(high) >= 7, f"esperado >= 7 hits, obtido {len(high)}"


def test_reconciliador_devolve_null_para_nao_resolvel(reconciliador, session_isolada):
    auditoria_id = _seed_dataset(session_isolada)
    sugestoes = {s.abastecimento_id: s for s in reconciliador.sugerir_para_auditoria(auditoria_id)}
    for ab_id in (108, 109, 110):
        assert sugestoes[ab_id].candidato_gp is None
        assert sugestoes[ab_id].confianca == 0.0
