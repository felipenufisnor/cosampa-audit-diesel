"""Testes E2E da CLI: invoca via subprocess e valida JSON contra schema."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from audit_diesel.config import DB_PATH
from audit_diesel.ingestion.pipeline import ingerir


class AlertaSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    tipo: str
    severidade: str
    titulo: str
    descricao: str
    abastecimento_id: int | None
    impacto_financeiro: float | None
    payload: dict


class AuditoriaSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    nf_anterior: str
    nf_atual: str
    nome_obra: str
    criada_em: datetime
    estoque_inicial_anterior: float
    quantidade_descarregada_anterior: float
    estoque_final_teorico_anterior: float
    saidas_registradas_litros: float
    saidas_registradas_custo: float
    estoque_inicial_atual: float
    saida_teorica_litros: float
    diferenca_litros: float
    diferenca_percentual: float
    qtd_equipamentos_nao_cadastrados: int
    validacao_final: str
    parecer_ia: str | None


class AuditoriaCompletaSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auditoria: AuditoriaSchema
    alertas: list[AlertaSchema] = Field(default_factory=list)


@pytest.fixture(scope="module", autouse=True)
def garantir_banco_real():
    """Garante que o banco DB_PATH esta carregado e com schema atualizado."""
    ingerir(force=True)


def _run(args: list[str]) -> subprocess.CompletedProcess:
    import os

    backend_root = Path(__file__).resolve().parents[1]
    src = str(backend_root / "src")
    env = os.environ.copy()
    # Fallback caso a editable install do uv tenha ficado marcada como hidden no macOS.
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "audit_diesel.cli", *args],
        capture_output=True,
        text=True,
        cwd=backend_root,
        env=env,
    )


def test_cli_listar_nfs():
    proc = _run(["listar-nfs"])
    assert proc.returncode == 0, proc.stderr
    for nf in ("8108", "8187", "8278", "8328"):
        assert nf in proc.stdout


def test_cli_auditar_json_e_valido():
    proc = _run(["auditar", "--nf-anterior", "8108", "--nf-atual", "8187", "--json"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    parsed = AuditoriaCompletaSchema.model_validate(data)
    assert parsed.auditoria.nf_anterior == "8108"
    assert parsed.auditoria.nf_atual == "8187"


def test_cli_auditar_render_humano():
    proc = _run(["auditar", "--nf-anterior", "8108", "--nf-atual", "8187"])
    assert proc.returncode == 0, proc.stderr
    assert "Indicadores" in proc.stdout
    assert "Validacao final" in proc.stdout


def test_cli_stats():
    proc = _run(["stats"])
    assert proc.returncode == 0, proc.stderr
    assert "abastecimentos" in proc.stdout.lower()
