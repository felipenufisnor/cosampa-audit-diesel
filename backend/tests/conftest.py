"""Fixtures compartilhadas: SQLite em memoria, dados sinteticos, paths reais."""

from __future__ import annotations

import sys
from datetime import datetime, time
from pathlib import Path

# Garante que src/ esta no sys.path mesmo se a editable install do uv ficou marcada
# como UF_HIDDEN (problema conhecido em macOS) e o .pth foi ignorado pelo site.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pytest  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from audit_diesel.models import Abastecimento, Checklist, Mobilizado  # noqa: E402


@pytest.fixture
def in_memory_engine():
    """Engine SQLite em memoria com schema criado."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(in_memory_engine):
    """Session pronta para uso, isolada por teste."""
    with Session(in_memory_engine) as s:
        yield s


@pytest.fixture
def raw_dir() -> Path:
    """Diretorio com os xlsx reais do cliente."""
    here = Path(__file__).resolve().parents[1]
    return here / "data" / "raw"


@pytest.fixture
def db_path_tmp(tmp_path) -> Path:
    """Caminho de SQLite temporario para testes E2E de ingestao."""
    return tmp_path / "audit_test.db"


@pytest.fixture
def checklist_par():
    """Par de checklists sintetico para testes do engine.

    Janela de 7 dias. NF anterior em 01/03 09:00, NF atual em 08/03 09:00.
    Estoques montados para que a saida_teorica = 800 L.
    """
    ck_ant = Checklist(
        id=1,
        numero_chamado="100",
        nota_fiscal="100",
        nome_obra="OBRA TESTE",
        cnpj_fornecedor="00.000.000/0001-00",
        data_recebimento=datetime(2026, 3, 1, 9, 0),
        hora_inicio_descarga=time(8, 0),
        hora_final_descarga=time(9, 0),
        datetime_fim_descarga=datetime(2026, 3, 1, 9, 0),
        quantidade_nf_litros=1000,
        volume_conferido_litros=1000,
        estoque_antes_tanque_litros=500,
        estoque_antes_comboio_litros=300,
        preco_unitario=6.5,
        valor_total_nf=6500,
    )
    ck_atu = Checklist(
        id=2,
        numero_chamado="200",
        nota_fiscal="200",
        nome_obra="OBRA TESTE",
        cnpj_fornecedor="00.000.000/0001-00",
        data_recebimento=datetime(2026, 3, 8, 9, 0),
        hora_inicio_descarga=time(8, 0),
        hora_final_descarga=time(9, 0),
        datetime_fim_descarga=datetime(2026, 3, 8, 9, 0),
        quantidade_nf_litros=1000,
        volume_conferido_litros=1000,
        estoque_antes_tanque_litros=600,
        estoque_antes_comboio_litros=400,
        preco_unitario=6.5,
        valor_total_nf=6500,
    )
    return ck_ant, ck_atu


@pytest.fixture
def mobilizado_padrao() -> Mobilizado:
    """Equipamento mobilizado padrao."""
    return Mobilizado(
        id=10,
        codigo_projeto="1211",
        nome_obra="OBRA TESTE",
        tipo_equipamento="MAQUINAS",
        equipamento="ESCAVADEIRA",
        marca="X",
        modelo="Y",
        placa_ativo_raw="07.T586",
        placa_ativo_normalizada="07T586",
        situacao="MOBILIZADO",
        data_mobilizacao=datetime(2025, 1, 1),
        data_desmobilizacao=None,
        capacidade_litros=280,
        ano=2022,
    )


@pytest.fixture
def abastecimento_padrao() -> Abastecimento:
    """Abastecimento padrao dentro da janela 01/03-08/03 do par sintetico."""
    return Abastecimento(
        id=100,
        data=datetime(2026, 3, 4, 10, 0),
        veiculo_raw="07.T586",
        veiculo_normalizado="07T586",
        apelido="ROL-01",
        quantidade_litros=200,
        custo_total=1300.0,
        valor_litro=6.5,
        medido_por="H",
        medicao=10.0,
        autonomia_media=20.0,
    )
