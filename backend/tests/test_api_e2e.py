"""E2E da API FastAPI usando TestClient (sem subir uvicorn)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module", autouse=True)
def _force_offline_and_seed():
    """Garante modo offline e DB carregado antes de instanciar o app."""
    os.environ["AUDIT_AI_OFFLINE"] = "1"
    from audit_diesel.config import DB_PATH
    from audit_diesel.ingestion.pipeline import ingerir
    if not DB_PATH.exists():
        ingerir(force=True)
    else:
        # Garante schema atualizado.
        ingerir(force=True)
    return DB_PATH


@pytest.fixture(scope="module")
def client():
    # Importa apos forcar offline para o singleton do ChatClient pegar a config certa.
    from audit_diesel.api.deps import _chat_client, _engine
    _chat_client.cache_clear()
    _engine.cache_clear()
    from audit_diesel.api.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "connected"
    assert body["offline"] is True
    assert body["provider"] == "offline"


def test_stats(client):
    r = client.get("/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_abastecimentos"] == 1862
    assert body["total_nfs"] == 4
    assert body["total_mobilizados"] == 286
    assert body["total_custo_brl"] > 0
    assert 0 <= body["pct_custo_nao_cadastrado"] <= 100


def test_listar_nfs(client):
    r = client.get("/nfs")
    assert r.status_code == 200
    nfs = {item["nota_fiscal"] for item in r.json()}
    assert {"8108", "8187", "8278", "8328"} == nfs


def test_detalhe_nf_404(client):
    r = client.get("/nfs/9999")
    assert r.status_code == 404


def test_criar_auditoria_e2e(client):
    payload = {"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": True}
    r = client.post("/auditorias", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    a = body["auditoria"]
    assert a["validacao_final"] in {"APROVADO", "INCONSISTENTE"}
    assert a["parecer_ia"] is not None
    assert "**Resultado**" in a["parecer_ia"]
    assert body["parecer_meta"]["offline"] is True
    assert len(body["alertas"]) > 0


def test_sugerir_e_aprovar_reconciliacao(client):
    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()
    aud_id = aud["auditoria"]["id"]
    nao_cad_inicial = aud["auditoria"]["qtd_equipamentos_nao_cadastrados"]

    sug = client.post("/reconciliacao/sugerir", json={"auditoria_id": aud_id}).json()
    assert sug["offline"] is True
    assert isinstance(sug["sugestoes"], list)
    candidato = next(
        (s for s in sug["sugestoes"] if s.get("candidato_gp") and s["confianca"] >= 0.65),
        None,
    )
    if candidato is None:
        pytest.skip("dataset real nao expos sugestao com confianca >= 0.65")

    r = client.post(
        "/reconciliacao/aprovar",
        json={
            "abastecimento_id": candidato["abastecimento_id"],
            "mobilizado_id": candidato["candidato_gp"]["id"],
            "auditor": "demo",
            "confianca": candidato["confianca"],
            "auditoria_id": aud_id,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    nova = body["auditoria_atualizada"]
    assert nova is not None
    assert nova["auditoria"]["qtd_equipamentos_nao_cadastrados"] <= nao_cad_inicial


def test_openapi_doc(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for p in (
        "/healthz",
        "/stats",
        "/nfs",
        "/nfs/{nota_fiscal}",
        "/nfs/{nota_fiscal}/auditorias",
        "/auditorias",
        "/auditorias/{auditoria_id}",
        "/auditorias/{auditoria_id}/aprovar",
        "/reconciliacao/sugerir",
        "/reconciliacao/aprovar",
    ):
        assert p in paths, f"endpoint {p} nao documentado"


def test_aprovar_auditoria_manual(client):
    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()
    aud_id = aud["auditoria"]["id"]

    r = client.patch(
        f"/auditorias/{aud_id}/aprovar",
        json={"auditor": "felipe", "observacao": "Validado em campo com a obra."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    a = body["auditoria"]
    assert a["validacao_final"] == "APROVADO"
    assert a["auditor_aprovacao"] == "felipe"
    assert a["observacao_aprovacao"] == "Validado em campo com a obra."
    assert a["aprovada_em"] is not None


def test_aprovar_auditoria_inexistente(client):
    r = client.patch("/auditorias/999999/aprovar", json={"auditor": "demo"})
    assert r.status_code == 404


def test_listar_auditorias_da_nf(client):
    # Garante ao menos uma auditoria sobre 8187.
    client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    )
    r = client.get("/nfs/8187/auditorias")
    assert r.status_code == 200, r.text
    items = r.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    for it in items:
        assert it["nf_atual"] == "8187"


def test_listar_auditorias_da_nf_inexistente(client):
    r = client.get("/nfs/9999/auditorias")
    assert r.status_code == 404


def test_post_auditoria_sobrescrever_ultima(client):
    antes = client.get("/nfs/8187/auditorias").json()
    qtd_antes = len(antes)

    client.post(
        "/auditorias",
        json={
            "nf_anterior": "8108",
            "nf_atual": "8187",
            "gerar_parecer": False,
            "modo": "nova_versao",
        },
    )
    intermediario = client.get("/nfs/8187/auditorias").json()
    assert len(intermediario) == qtd_antes + 1

    client.post(
        "/auditorias",
        json={
            "nf_anterior": "8108",
            "nf_atual": "8187",
            "gerar_parecer": False,
            "modo": "sobrescrever_ultima",
        },
    )
    depois = client.get("/nfs/8187/auditorias").json()
    # Sobrescrever apaga a ultima e cria uma nova: total fica igual ao
    # estado intermediario (uma a mais que o estado inicial).
    assert len(depois) == qtd_antes + 1


def test_post_auditoria_modo_invalido(client):
    r = client.post(
        "/auditorias",
        json={
            "nf_anterior": "8108",
            "nf_atual": "8187",
            "gerar_parecer": False,
            "modo": "modo_estranho",
        },
    )
    assert r.status_code == 400
