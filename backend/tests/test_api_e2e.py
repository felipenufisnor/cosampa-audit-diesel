"""E2E da API FastAPI usando TestClient (sem subir uvicorn)."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader


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
    assert body["assistant_status"] == "offline_fixture"
    assert body["assistant_can_answer_free_text"] is False
    assert "assistant_has_cached_answers" in body


def test_stats(client):
    r = client.get("/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_abastecimentos"] == 1862
    assert body["total_nfs"] == 4
    assert body["total_mobilizados"] == 286
    assert body["total_custo_brl"] > 0
    assert 0 <= body["pct_custo_nao_cadastrado"] <= 100
    # Periodo de abastecimentos (Infleet) e periodo de NFs sao janelas distintas
    # e devem ser expostas separadamente. Ver achado AI-05.
    assert body["periodo_inicio"] is not None
    assert body["periodo_fim"] is not None
    assert body["periodo_nfs_inicio"] is not None
    assert body["periodo_nfs_fim"] is not None
    assert body["periodo_nfs_inicio"] <= body["periodo_nfs_fim"]
    assert body["periodo_inicio"] <= body["periodo_fim"]


def test_listar_nfs(client):
    r = client.get("/nfs")
    assert r.status_code == 200
    nfs = {item["nota_fiscal"] for item in r.json()}
    assert {"8108", "8187", "8278", "8328"} == nfs
    for item in r.json():
        assert "qtd_auditorias" in item


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


def test_pdf_auditoria_layout_metadata(client):
    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()
    aud_id = aud["auditoria"]["id"]

    r = client.get(f"/auditorias/{aud_id}/pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"

    reader = PdfReader(BytesIO(r.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Setor de Auditoria e Controle" not in text
    assert "COPAMSA · Setor de Auditoria e Controle" not in text
    assert "Auditoria de Diesel · NF 8187" not in text
    assert "Auditoria de Diesel - NF 8187" in text
    assert "Auditoria de Diesel — NF 8187" not in text
    assert "Gerado em" in text
    assert "SHA256:" in text
    assert "Pagina 1 de" in text
    assert "Pagina\n" not in text


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


def test_contexto_reconciliacao_retorna_matches_e_historico(client):
    """AI-09: contexto deterministico oferece alternativas quando IA nao acha candidato."""
    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()
    aud_id = aud["auditoria"]["id"]
    alertas_nao_cad = [
        a for a in aud["alertas"] if a["tipo"] == "NAO_CADASTRADO" and a["abastecimento_id"]
    ]
    if not alertas_nao_cad:
        pytest.skip("dataset nao gerou alerta NAO_CADASTRADO no par testado")

    abast_id = alertas_nao_cad[0]["abastecimento_id"]
    r = client.get(
        f"/reconciliacao/contexto?abastecimento_id={abast_id}&auditoria_id={aud_id}"
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["abastecimento_id"] == abast_id
    assert body["nome_obra"]
    assert body["termo_busca_sugerido"]
    assert isinstance(body["matches_aproximados"], list)
    assert isinstance(body["historico"], list)
    for m in body["matches_aproximados"]:
        assert 0.0 <= m["similaridade"] <= 1.0
        assert m["candidato"]["id"]
        assert m["motivo"]


def test_contexto_reconciliacao_404_em_id_invalido(client):
    r = client.get("/reconciliacao/contexto?abastecimento_id=999999&auditoria_id=1")
    assert r.status_code == 404


def test_api_e_consolidado_expoem_nao_cadastrados_deduplicados(client):
    aud = client.post(
        "/auditorias",
        json={
            "nf_anterior": "8108",
            "nf_atual": "8187",
            "gerar_parecer": False,
            "modo": "sobrescrever_ultima",
        },
    ).json()
    alertas = aud["alertas"]
    nao_cad = [a for a in alertas if a["tipo"] == "NAO_CADASTRADO"]
    veiculos = [a["payload"]["veiculo_normalizado"] for a in nao_cad]

    assert len(veiculos) == len(set(veiculos))
    assert aud["auditoria"]["qtd_equipamentos_nao_cadastrados"] == len(nao_cad)

    consolidado = client.get("/auditorias/consolidado").json()
    item = next(i for i in consolidado["items"] if i["auditoria_id"] == aud["auditoria"]["id"])
    assert item["qtd_alertas"] == len(alertas)
    assert item["qtd_alertas_alta"] == sum(1 for a in alertas if a["severidade"] == "alta")


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
        "/reconciliacao/contexto",
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
        assert it["versao"] >= 1
        assert it["total_versoes"] >= it["versao"]
        assert it["auditoria_atual_id"] is not None


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


def test_criar_auditoria_com_ponto_corte_manual(client):
    """Auditor consegue auditar a NF mais antiga via ponto de corte manual.

    Ver achado AI-06: NF 8108 e a mais antiga, nao tem NF anterior. Pelo
    ponto de corte manual, o auditor define data + estoques iniciais e o
    engine roda a auditoria normalmente.
    """
    payload = {
        "nf_atual": "8108",
        "gerar_parecer": False,
        "ponto_corte": {
            "data_inicio": "2026-03-01T08:00:00",
            "estoque_tanque_inicial_litros": 5000.0,
            "estoque_comboio_inicial_litros": 1500.0,
            "motivo": "Medicao manual do tanque no inicio da janela",
        },
    }
    r = client.post("/auditorias", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    a = body["auditoria"]
    assert a["nf_atual"] == "8108"
    assert a["nf_anterior"].startswith("CORTE:")
    # quantidade_descarregada_anterior=0 => estoque_final_teorico = estoque_inicial.
    assert a["quantidade_descarregada_anterior"] == 0.0
    assert a["estoque_inicial_anterior"] == 6500.0
    assert a["estoque_final_teorico_anterior"] == 6500.0


def test_criar_auditoria_xor_nf_anterior_ponto_corte(client):
    # Nenhum dos dois.
    r = client.post("/auditorias", json={"nf_atual": "8108", "gerar_parecer": False})
    assert r.status_code == 422
    # Os dois.
    r = client.post(
        "/auditorias",
        json={
            "nf_atual": "8187",
            "nf_anterior": "8108",
            "gerar_parecer": False,
            "ponto_corte": {
                "data_inicio": "2026-03-01T08:00:00",
                "estoque_tanque_inicial_litros": 5000.0,
                "estoque_comboio_inicial_litros": 1500.0,
                "motivo": "ambos",
            },
        },
    )
    assert r.status_code == 422


def test_ponto_corte_rejeita_data_posterior(client):
    # data_inicio depois do fim de descarga da NF atual.
    r = client.post(
        "/auditorias",
        json={
            "nf_atual": "8108",
            "gerar_parecer": False,
            "ponto_corte": {
                "data_inicio": "2026-12-31T23:59:00",
                "estoque_tanque_inicial_litros": 0.0,
                "estoque_comboio_inicial_litros": 0.0,
                "motivo": "deve falhar",
            },
        },
    )
    assert r.status_code == 400
    assert "Ponto de corte" in r.json()["detail"]


def test_post_auditoria_rejeita_nf_anterior_posterior(client):
    r = client.post(
        "/auditorias",
        json={"nf_anterior": "8187", "nf_atual": "8108", "gerar_parecer": False},
    )
    assert r.status_code == 400
    assert "NF anterior" in r.json()["detail"]


def test_stream_auditoria_rejeita_nf_anterior_posterior(client):
    with client.stream(
        "POST",
        "/auditorias/stream",
        json={"nf_anterior": "8187", "nf_atual": "8108"},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(chunk for chunk in resp.iter_text())

    assert '"event": "error"' in body
    assert "NF anterior" in body


def test_sobrescrever_ultima_invalido_nao_apaga_historico(client):
    criada = client.post(
        "/auditorias",
        json={
            "nf_anterior": "8108",
            "nf_atual": "8187",
            "gerar_parecer": False,
            "modo": "nova_versao",
        },
    ).json()["auditoria"]

    r = client.post(
        "/auditorias",
        json={
            "nf_anterior": "8278",
            "nf_atual": "8187",
            "gerar_parecer": False,
            "modo": "sobrescrever_ultima",
        },
    )
    assert r.status_code == 400

    existente = client.get(f"/auditorias/{criada['id']}")
    assert existente.status_code == 200
    assert existente.json()["auditoria"]["id"] == criada["id"]


def test_metadados_versao_em_auditorias_duplicadas(client):
    primeira = client.post(
        "/auditorias",
        json={
            "nf_anterior": "8108",
            "nf_atual": "8187",
            "gerar_parecer": False,
            "modo": "nova_versao",
        },
    ).json()["auditoria"]
    segunda = client.post(
        "/auditorias",
        json={
            "nf_anterior": "8108",
            "nf_atual": "8187",
            "gerar_parecer": False,
            "modo": "nova_versao",
        },
    ).json()["auditoria"]

    r_primeira = client.get(f"/auditorias/{primeira['id']}")
    r_segunda = client.get(f"/auditorias/{segunda['id']}")
    assert r_primeira.status_code == 200, r_primeira.text
    assert r_segunda.status_code == 200, r_segunda.text

    a1 = r_primeira.json()["auditoria"]
    a2 = r_segunda.json()["auditoria"]
    assert a1["is_atual"] is False
    assert a2["is_atual"] is True
    assert a1["auditoria_atual_id"] == segunda["id"]
    assert a2["auditoria_atual_id"] == segunda["id"]
    assert a1["total_versoes"] == a2["total_versoes"]
    assert a1["versao"] < a2["versao"]

    nfs = client.get("/nfs").json()
    nf_8187 = next(item for item in nfs if item["nota_fiscal"] == "8187")
    assert nf_8187["qtd_auditorias"] >= 2


def test_parecer_placeholder_eh_sanitizado_no_get(client):
    """Parecer template persistido no banco deve sair como null + status placeholder."""
    from sqlmodel import Session, select

    from audit_diesel.api.deps import _engine
    from audit_diesel.models import Auditoria

    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()
    aud_id = aud["auditoria"]["id"]

    parecer_template = (
        "Resultado calculado a partir dos indicadores §4 do escopo. "
        "Avaliacao baseada nos alertas disparados pelo engine deterministico. "
        "Revise os alertas listados e proceda conforme procedimento operacional padrao. "
        "Valor consolidado conforme campo impacto_total_alertas_brl."
    )
    engine = _engine()
    with Session(engine) as s:
        auditoria = s.exec(select(Auditoria).where(Auditoria.id == aud_id)).first()
        assert auditoria is not None
        auditoria.parecer_ia = parecer_template
        s.add(auditoria)
        s.commit()

    r = client.get(f"/auditorias/{aud_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["auditoria"]["parecer_ia"] is None
    assert body["auditoria"]["parecer_status"] == "placeholder"
    assert body["parecer_meta"] is None


def test_parecer_valido_passa_no_get(client):
    """Auditoria com parecer real produzido pelo offline passa com status ok."""
    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": True},
    ).json()
    aud_id = aud["auditoria"]["id"]
    r = client.get(f"/auditorias/{aud_id}")
    body = r.json()
    assert body["auditoria"]["parecer_status"] == "ok"
    assert body["auditoria"]["parecer_ia"] is not None


def test_regenerar_parecer_substitui_placeholder(client):
    """Endpoint dedicado limpa parecer template e nao mexe em alertas/indicadores."""
    from sqlmodel import Session, select

    from audit_diesel.api.deps import _engine
    from audit_diesel.models import Alerta, Auditoria

    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()
    aud_id = aud["auditoria"]["id"]
    criada_em_original = aud["auditoria"]["criada_em"]
    qtd_alertas_original = len(aud["alertas"])

    engine = _engine()
    with Session(engine) as s:
        auditoria = s.exec(select(Auditoria).where(Auditoria.id == aud_id)).first()
        assert auditoria is not None
        auditoria.parecer_ia = (
            "Resultado calculado a partir dos indicadores §4 do escopo. "
            "Avaliacao baseada nos alertas disparados pelo engine deterministico."
        )
        s.add(auditoria)
        s.commit()

    r = client.post(f"/auditorias/{aud_id}/parecer/regenerar")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["auditoria"]["parecer_status"] == "ok"
    assert body["auditoria"]["parecer_ia"] is not None
    assert body["parecer_meta"] is not None
    # Indicadores e timestamp original intactos.
    assert body["auditoria"]["criada_em"] == criada_em_original
    assert len(body["alertas"]) == qtd_alertas_original

    # Confirma que o banco realmente foi atualizado.
    with Session(engine) as s:
        auditoria = s.exec(select(Auditoria).where(Auditoria.id == aud_id)).first()
        assert auditoria is not None
        assert "Resultado calculado a partir" not in (auditoria.parecer_ia or "")
        alertas_pos = list(
            s.exec(select(Alerta).where(Alerta.auditoria_id == aud_id)).all()
        )
        assert len(alertas_pos) == qtd_alertas_original


def test_regenerar_parecer_auditoria_inexistente(client):
    r = client.post("/auditorias/999999/parecer/regenerar")
    assert r.status_code == 404


def test_perguntas_sugeridas_endpoint(client):
    """Lista perguntas pre-cacheadas para uma auditoria existente."""
    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()
    aud_id = aud["auditoria"]["id"]
    r = client.get(f"/auditorias/{aud_id}/perguntas-sugeridas")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["auditoria_id"] == aud_id
    assert isinstance(body["perguntas"], list)
    # Quando ha cache, todas as entradas devem vir marcadas como cacheada=true.
    for p in body["perguntas"]:
        assert p["cacheada"] is True
        assert p["pergunta"].strip() != ""


def test_cache_assistente_por_janela_sobrevive_novo_id(client):
    from audit_diesel.ai.assistente import salvar_cache_chip

    primeira = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()["auditoria"]
    pergunta = "Pergunta cacheada por janela?"
    salvar_cache_chip(
        primeira["id"],
        pergunta,
        "Resposta cacheada por janela.",
        nf_anterior=primeira["nf_anterior"],
        nf_atual=primeira["nf_atual"],
    )
    segunda = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()["auditoria"]

    r = client.get(f"/auditorias/{segunda['id']}/perguntas-sugeridas")
    assert r.status_code == 200, r.text
    perguntas = [p["pergunta"] for p in r.json()["perguntas"]]
    assert pergunta in perguntas


def test_assistente_online_falha_cai_para_cache_janela(client):
    from types import SimpleNamespace

    from sqlmodel import Session

    from audit_diesel.ai.assistente import salvar_cache_chip, stream_pergunta
    from audit_diesel.ai.provider import ProviderInfo
    from audit_diesel.api.deps import _engine

    class FailingOnlineChat:
        provider = SimpleNamespace(
            info=ProviderInfo(
                name="mock-online",
                base_url="mock://online",
                model="mock",
                offline=False,
            )
        )

        def chat(self, **_kwargs):
            raise RuntimeError("provider down")

    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()["auditoria"]
    pergunta = "Use cache quando provider falhar"
    resposta = "Resposta recuperada do cache por janela."
    salvar_cache_chip(
        aud["id"],
        pergunta,
        resposta,
        nf_anterior=aud["nf_anterior"],
        nf_atual=aud["nf_atual"],
    )

    async def collect() -> str:
        engine = _engine()
        with Session(engine) as session:
            chunks = []
            async for item in stream_pergunta(
                session=session,
                auditoria_id=aud["id"],
                pergunta=pergunta,
                chat=FailingOnlineChat(),
            ):
                chunks.append(item)
            return "".join(chunks)

    body = asyncio.run(collect())
    assert resposta in body
    assert '"fallback_acionado": false' in body


def test_perguntas_sugeridas_auditoria_inexistente(client):
    r = client.get("/auditorias/999999/perguntas-sugeridas")
    assert r.status_code == 404


def _limpar_padroes_persistidos(session):
    from sqlmodel import select

    from audit_diesel.models import PadraoDetectado

    for row in session.exec(select(PadraoDetectado)).all():
        session.delete(row)
    session.commit()


def _assert_snapshot_demo_real(padroes):
    assert len(padroes) == 5
    assert [p["severidade"] for p in padroes].count("alta") == 3
    assert [p["severidade"] for p in padroes].count("media") == 2
    tipos = [p["tipo"] for p in padroes]
    assert len(set(tipos)) == 5
    assert "desmobilizado_ativo_agregado" in tipos
    assert "aumento_consumo" in tipos
    assert "horario_atipico" in tipos
    assert "inconsistencias_infleet_agregado" in tipos
    descricoes = " ".join(p["descricao"] for p in padroes)
    assert "26 placa(s)" in descricoes
    assert "12.847L" in descricoes
    assert "329% acima" in descricoes
    assert "79 abastecimento(s)" in descricoes
    assert "152 abastecimento(s) em 46 veículo(s)" in descricoes


def _popular_snapshot_persistido_valido(session, *padroes):
    from audit_diesel.models import PadraoDetectado

    rows = list(padroes)
    usados = {p.tipo for p in rows}
    fillers = [
        ("nao_cadastrado_agregado", "alta"),
        ("desmobilizado_ativo_agregado", "alta"),
        ("aumento_consumo", "alta"),
        ("horario_atipico", "media"),
        ("inconsistencias_infleet_agregado", "media"),
    ]
    for tipo, severidade in fillers:
        if len(rows) >= 5:
            break
        if tipo in usados:
            continue
        n_alta = sum(1 for p in rows if p.severidade == "alta")
        n_media = sum(1 for p in rows if p.severidade == "media")
        if severidade == "alta" and n_alta >= 3:
            continue
        if severidade == "media" and n_media >= 2:
            continue
        rows.append(
            PadraoDetectado(
                tipo=tipo,
                titulo=f"Snapshot {tipo}",
                descricao="Evidencia parseavel para snapshot persistido.",
                severidade=severidade,
                dados_json=json.dumps({"evidencia_ids": [len(rows) + 1]}),
                criado_em=datetime.now(),
            )
        )
        usados.add(tipo)

    assert len(rows) == 5
    assert sum(1 for p in rows if p.severidade == "alta") == 3
    assert sum(1 for p in rows if p.severidade == "media") == 2
    for row in rows:
        session.add(row)
    session.commit()


def test_padroes_calcula_snapshot_quando_banco_vazio(client):
    from sqlmodel import Session

    from audit_diesel.api.deps import _engine

    engine = _engine()
    with Session(engine) as s:
        _limpar_padroes_persistidos(s)

    r = client.get("/padroes")
    assert r.status_code == 200, r.text
    _assert_snapshot_demo_real(r.json()["padroes"])


def test_padroes_ignora_snapshot_invalido_e_recalcula_em_memoria(client):
    from sqlmodel import Session

    from audit_diesel.api.deps import _engine
    from audit_diesel.models import PadraoDetectado

    engine = _engine()
    with Session(engine) as s:
        _limpar_padroes_persistidos(s)
        s.add(
            PadraoDetectado(
                tipo="horario_atipico",
                titulo="Padrao sem alvo teste",
                descricao="Padrao sem evidencia suficiente.",
                severidade="media",
                dados_json=json.dumps({"total_atipicos": 3}),
                criado_em=datetime.now(),
            )
        )
        s.add(
            PadraoDetectado(
                tipo="diferenca_saidas_alta",
                titulo="Padrao alvo teste",
                descricao="Padrao com auditoria alvo explicita.",
                severidade="alta",
                dados_json=json.dumps({"top_diferencas": []}),
                criado_em=datetime.now(),
            )
        )
        s.commit()

    try:
        r = client.get("/padroes")
        assert r.status_code == 200, r.text
        padroes = r.json()["padroes"]
        _assert_snapshot_demo_real(padroes)
        titulos = {p["titulo"] for p in padroes}
        assert "Padrao sem alvo teste" not in titulos
        assert "Padrao alvo teste" not in titulos
    finally:
        with Session(engine) as s:
            _limpar_padroes_persistidos(s)


def test_padroes_informa_auditoria_alvo(client):
    from sqlmodel import Session

    from audit_diesel.api.deps import _engine
    from audit_diesel.models import PadraoDetectado

    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()["auditoria"]

    engine = _engine()
    with Session(engine) as s:
        _limpar_padroes_persistidos(s)
        _popular_snapshot_persistido_valido(
            s,
            PadraoDetectado(
                tipo="diferenca_saidas_alta",
                titulo="Padrao alvo teste",
                descricao="Padrao com auditoria alvo explicita.",
                severidade="alta",
                dados_json=json.dumps(
                    {
                        "top_diferencas": [
                            {"auditoria_id": aud["id"], "nf_atual": aud["nf_atual"]}
                        ]
                    }
                ),
                criado_em=datetime.now(),
            ),
        )

    try:
        r = client.get("/padroes")
        assert r.status_code == 200, r.text
        padrao = next(p for p in r.json()["padroes"] if p["titulo"] == "Padrao alvo teste")
        assert padrao["auditoria_alvo_id"] == aud["id"]
        assert padrao["auditoria_alvo_nf"] == aud["nf_atual"]
    finally:
        with Session(engine) as s:
            _limpar_padroes_persistidos(s)


def test_padroes_sem_alvo_nao_inventa_alvo(client):
    from sqlmodel import Session

    from audit_diesel.api.deps import _engine
    from audit_diesel.models import PadraoDetectado

    engine = _engine()
    with Session(engine) as s:
        _limpar_padroes_persistidos(s)
        _popular_snapshot_persistido_valido(
            s,
            PadraoDetectado(
                tipo="horario_atipico",
                titulo="Padrao sem alvo teste",
                descricao="Padrao com evidencia sem auditoria correspondente.",
                severidade="media",
                dados_json=json.dumps({"evidencia_ids": [999999]}),
                criado_em=datetime.now(),
            ),
        )

    try:
        r = client.get("/padroes")
        assert r.status_code == 200, r.text
        padrao = next(p for p in r.json()["padroes"] if p["titulo"] == "Padrao sem alvo teste")
        assert padrao["auditoria_alvo_id"] is None
        assert padrao["auditoria_alvo_nf"] is None
    finally:
        with Session(engine) as s:
            _limpar_padroes_persistidos(s)


def test_resposta_offline_nao_vaza_flag_tecnica(client):
    """Mensagem de fallback NUNCA pode citar AUDIT_AI_OFFLINE ao usuario final."""
    aud = client.post(
        "/auditorias",
        json={"nf_anterior": "8108", "nf_atual": "8187", "gerar_parecer": False},
    ).json()
    aud_id = aud["auditoria"]["id"]

    # Pergunta livre que nao deve estar no cache → cai no fallback.
    with client.stream(
        "POST",
        f"/auditorias/{aud_id}/perguntar",
        json={"pergunta": "Quantos batalhoes participaram da auditoria de Tabatinga?"},
    ) as resp:
        assert resp.status_code == 200
        body = "".join(chunk for chunk in resp.iter_text())

    # A flag interna nao pode aparecer em nenhum evento SSE.
    assert "AUDIT_AI_OFFLINE" not in body
    # E o texto deve indicar indisponibilidade de forma humana.
    assert "indisponivel" in body.lower() or "indisponível" in body.lower()
