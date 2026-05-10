"""Orquestracao da ingestao: le os 3 xlsx, valida e popula o SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from audit_diesel.config import (
    CHECKLIST_FILENAME,
    DB_PATH,
    INFLEET_FILENAME,
    MOBILIZADOS_FILENAME,
    RAW_DIR,
    db_url,
)
from audit_diesel.models import Abastecimento, Alerta, Auditoria, Checklist, Mobilizado

from .checklist import carregar_checklists
from .infleet import carregar_abastecimentos
from .mobilizados import carregar_mobilizados


@dataclass
class IngestResult:
    """Sumario da ingestao para exibir no CLI."""

    abastecimentos: int
    mobilizados: int
    checklists: int


def build_engine(db_path: Path | None = None) -> Engine:
    """Cria engine SQLAlchemy pointing para SQLite."""
    return create_engine(db_url(db_path), echo=False)


def init_schema(engine: Engine) -> None:
    """Cria todas as tabelas declaradas via SQLModel.

    Aplica tambem migracoes leves (ALTER TABLE ADD COLUMN) para colunas
    adicionadas apos a primeira versao do schema, ja que SQLite preexistente
    nao reflete novos campos via create_all.
    """
    SQLModel.metadata.create_all(engine)
    _aplicar_migracoes_leves(engine)


def _aplicar_migracoes_leves(engine: Engine) -> None:
    """Garante presenca de colunas adicionadas pos-MVP em SQLite existente.

    Cada entrada e idempotente: checa via inspect() antes de emitir o ALTER.
    """
    novas_colunas: dict[str, list[tuple[str, str]]] = {
        "auditoria": [
            ("aprovada_em", "DATETIME"),
            ("auditor_aprovacao", "VARCHAR"),
            ("observacao_aprovacao", "VARCHAR"),
        ],
    }
    insp = inspect(engine)
    with engine.begin() as conn:
        for tabela, colunas in novas_colunas.items():
            if not insp.has_table(tabela):
                continue
            existentes = {c["name"] for c in insp.get_columns(tabela)}
            for nome, tipo in colunas:
                if nome in existentes:
                    continue
                conn.execute(text(f'ALTER TABLE "{tabela}" ADD COLUMN {nome} {tipo}'))


def reset_schema(engine: Engine) -> None:
    """Dropa e recria todas as tabelas (usado em --force e nos testes)."""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def ingerir(
    raw_dir: Path | None = None,
    db_path: Path | None = None,
    *,
    force: bool = False,
) -> IngestResult:
    """Le os tres arquivos canonicos de RAW_DIR e popula o SQLite.

    Parameters
    ----------
    raw_dir
        Diretorio onde estao os xlsx; default = RAW_DIR.
    db_path
        Caminho do SQLite a usar; default = DB_PATH.
    force
        Se True, dropa e recria todas as tabelas antes de ingerir.
    """
    raw = raw_dir or RAW_DIR
    db = db_path or DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    engine = build_engine(db)
    if force:
        reset_schema(engine)
    else:
        init_schema(engine)
        # Limpa para garantir idempotencia.
        with Session(engine) as session:
            for cls in (Alerta, Auditoria, Abastecimento, Checklist, Mobilizado):
                session.query(cls).delete()
            session.commit()

    checklists = carregar_checklists(raw / CHECKLIST_FILENAME)
    mobilizados = carregar_mobilizados(raw / MOBILIZADOS_FILENAME)
    abastecimentos = carregar_abastecimentos(raw / INFLEET_FILENAME)

    with Session(engine) as session:
        for m in mobilizados:
            session.add(m)
        for c in checklists:
            session.add(c)
        for a in abastecimentos:
            session.add(a)
        session.commit()

    return IngestResult(
        abastecimentos=len(abastecimentos),
        mobilizados=len(mobilizados),
        checklists=len(checklists),
    )
