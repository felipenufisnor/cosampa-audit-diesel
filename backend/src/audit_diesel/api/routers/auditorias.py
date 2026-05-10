"""POST /auditorias, GET /auditorias/{id}, GET /auditorias/{id}/pdf."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session, select

from audit_diesel.ai.client import ChatClient
from audit_diesel.ai.parecer import GeradorParecer
from audit_diesel.audit.engine import AuditEngine, AuditoriaCompleta, ChecklistNaoEncontrado
from audit_diesel.config import TOLERANCIA_PERCENTUAL
from audit_diesel.models import Alerta, Auditoria, Checklist, Mobilizado, ReconciliacaoAprovada

from .. import pdf as pdf_render
from ..deps import get_chat_client, get_session
from ..schemas import (
    AlertaConsolidado,
    AlertaResponse,
    AprovarAuditoriaRequest,
    AuditoriaCompletaResponse,
    AuditoriaIndicadores,
    ConsolidadoResponse,
    CriarAuditoriaRequest,
    NFConsolidadoItem,
    ParecerMeta,
)

MODOS_VALIDOS = {"nova_versao", "sobrescrever_ultima"}

router = APIRouter(tags=["auditorias"])


# Endpoints de consolidado precisam ser declarados ANTES de
# /auditorias/{auditoria_id} para que o FastAPI nao trate "consolidado"
# como id na resolucao de rota.


@router.post("/auditorias", response_model=AuditoriaCompletaResponse)
def criar_auditoria(
    body: CriarAuditoriaRequest,
    session: Session = Depends(get_session),
    chat: ChatClient = Depends(get_chat_client),
) -> AuditoriaCompletaResponse:
    """Roda o engine deterministico e (opcionalmente) gera o parecer da IA.

    Modo `sobrescrever_ultima` apaga a auditoria mais recente da mesma
    nf_atual antes de criar a nova, evitando crescimento do historico
    quando o auditor so quer refazer um teste.
    """
    if body.modo not in MODOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Modo invalido: {body.modo}. Use um de {sorted(MODOS_VALIDOS)}.",
        )

    if body.modo == "sobrescrever_ultima":
        ultima = session.exec(
            select(Auditoria)
            .where(Auditoria.nf_atual == body.nf_atual)
            .order_by(Auditoria.criada_em.desc())
        ).first()
        if ultima is not None:
            for al in session.exec(
                select(Alerta).where(Alerta.auditoria_id == ultima.id)
            ).all():
                session.delete(al)
            session.delete(ultima)
            session.commit()

    engine = AuditEngine(session)
    try:
        resultado = engine.auditar(body.nf_anterior, body.nf_atual)
    except ChecklistNaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    parecer_meta: ParecerMeta | None = None
    if body.gerar_parecer:
        gerador = GeradorParecer(client=chat)
        result = gerador.gerar(resultado.to_dict())
        resultado.auditoria.parecer_ia = result.markdown
        session.add(resultado.auditoria)
        session.commit()
        parecer_meta = ParecerMeta(
            provider=result.provider,
            model=result.modelo,
            offline=result.offline,
            latency_s=round(result.latency_s, 3),
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
        )

    return _to_response(resultado, parecer_meta)


@router.get("/auditorias/consolidado", response_model=ConsolidadoResponse)
def consolidado(session: Session = Depends(get_session)) -> ConsolidadoResponse:
    """Resumo consolidado de todas as NFs (1 linha por NF)."""
    return _build_consolidado(session)


@router.get("/auditorias/consolidado.csv")
def consolidado_csv(session: Session = Depends(get_session)) -> Response:
    """Mesmo conteudo, exportado como CSV para Excel/planilha."""
    payload = _build_consolidado(session)
    csv_text = _to_csv(payload)
    filename = "consolidado_auditorias.csv"
    return Response(
        content=csv_text.encode("utf-8-sig"),  # BOM ajuda Excel a abrir
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/auditorias/{auditoria_id}", response_model=AuditoriaCompletaResponse)
def get_auditoria(
    auditoria_id: int,
    session: Session = Depends(get_session),
) -> AuditoriaCompletaResponse:
    a = session.get(Auditoria, auditoria_id)
    if a is None:
        raise HTTPException(status_code=404, detail=f"Auditoria {auditoria_id} nao encontrada.")
    alertas = session.exec(
        select(Alerta).where(Alerta.auditoria_id == auditoria_id)
    ).all()
    completa = AuditoriaCompleta(auditoria=a, alertas=list(alertas))
    return _to_response(completa, None)


@router.patch(
    "/auditorias/{auditoria_id}/aprovar",
    response_model=AuditoriaCompletaResponse,
)
def aprovar_auditoria(
    auditoria_id: int,
    body: AprovarAuditoriaRequest,
    session: Session = Depends(get_session),
) -> AuditoriaCompletaResponse:
    """Marca uma auditoria INCONSISTENTE como APROVADA pelo auditor.

    O contrato externo (`validacao_final`) continua usando "APROVADO" para
    compatibilidade; campos `aprovada_em`, `auditor_aprovacao` e
    `observacao_aprovacao` registram a aprovacao manual e quem a fez.
    Aprovacoes ja "APROVADO" automaticamente sao no-op com 200.
    """
    auditoria = session.get(Auditoria, auditoria_id)
    if auditoria is None:
        raise HTTPException(
            status_code=404,
            detail=f"Auditoria {auditoria_id} nao encontrada.",
        )

    if auditoria.validacao_final != "APROVADO":
        auditoria.validacao_final = "APROVADO"
    auditoria.aprovada_em = datetime.now()
    auditoria.auditor_aprovacao = body.auditor
    auditoria.observacao_aprovacao = body.observacao
    session.add(auditoria)
    session.commit()
    session.refresh(auditoria)

    alertas = session.exec(
        select(Alerta).where(Alerta.auditoria_id == auditoria_id)
    ).all()
    completa = AuditoriaCompleta(auditoria=auditoria, alertas=list(alertas))
    return _to_response(completa, None)


@router.get("/auditorias/{auditoria_id}/pdf")
def gerar_pdf_auditoria(
    auditoria_id: int,
    session: Session = Depends(get_session),
) -> Response:
    """Gera o PDF de auditoria pronto para impressao / arquivamento."""
    auditoria = session.get(Auditoria, auditoria_id)
    if auditoria is None:
        raise HTTPException(
            status_code=404, detail=f"Auditoria {auditoria_id} nao encontrada."
        )
    checklist = session.exec(
        select(Checklist).where(Checklist.nota_fiscal == auditoria.nf_atual)
    ).first()
    if checklist is None:
        raise HTTPException(
            status_code=404,
            detail=f"Checklist da NF {auditoria.nf_atual} nao localizado.",
        )

    alertas = list(
        session.exec(select(Alerta).where(Alerta.auditoria_id == auditoria_id)).all()
    )

    # Reconciliacoes aprovadas associadas. Como o /reconciliacao/aprovar pode
    # recriar a auditoria (apaga + insere), filtramos pelos abastecimentos
    # que pertencem aos alertas NAO_CADASTRADO desse ciclo OU pelo par de NFs.
    reconciliacoes_raw = list(
        session.exec(
            select(ReconciliacaoAprovada).order_by(ReconciliacaoAprovada.criada_em)
        ).all()
    )
    abastecimento_ids_da_janela = {
        a.abastecimento_id for a in alertas if a.abastecimento_id is not None
    }
    reconciliacoes_filtradas = [
        r
        for r in reconciliacoes_raw
        if r.abastecimento_id in abastecimento_ids_da_janela
        # Tambem inclui reconciliacoes ja aplicadas (que removeram o alerta):
        # nesse caso o abastecimento nao aparece mais nos alertas atuais.
        # Por isso fazemos um segundo filtro pela obra + janela na linha abaixo.
    ] or _reconciliacoes_da_obra(session, auditoria, reconciliacoes_raw)

    mobilizados_index = {
        m.id: f"{m.placa_ativo_raw} - {m.equipamento or ''}".strip(" -")
        for m in session.exec(select(Mobilizado)).all()
        if m.id is not None
    }
    reconciliacoes = pdf_render.montar_reconciliacoes_view(
        reconciliacoes_filtradas, mobilizados_index
    )

    parecer_meta = (
        {"provider": "registrado", "modelo": None, "offline": False}
        if auditoria.parecer_ia
        else None
    )

    pdf_bytes, filename = pdf_render.render_auditoria_pdf(
        auditoria=auditoria,
        checklist=checklist,
        alertas=alertas,
        reconciliacoes=reconciliacoes,
        parecer_meta=parecer_meta,
        tolerancia_pct=TOLERANCIA_PERCENTUAL,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


def _reconciliacoes_da_obra(
    session: Session,
    auditoria: Auditoria,
    todas: list[ReconciliacaoAprovada],
) -> list[ReconciliacaoAprovada]:
    """Fallback: filtra reconciliacoes da mesma obra pela janela de descarga.

    Util quando a auditoria foi recriada e o abastecimento nao consta mais
    como alerta NAO_CADASTRADO (porque ja esta reconciliado), mas a aprovacao
    pertence ao mesmo ciclo entre NFs.
    """
    if not todas:
        return []
    ck_ant = session.exec(
        select(Checklist).where(Checklist.nota_fiscal == auditoria.nf_anterior)
    ).first()
    ck_atu = session.exec(
        select(Checklist).where(Checklist.nota_fiscal == auditoria.nf_atual)
    ).first()
    if not ck_ant or not ck_atu:
        return []
    inicio = ck_ant.datetime_fim_descarga
    fim = ck_atu.datetime_fim_descarga
    out: list[ReconciliacaoAprovada] = []
    for r in todas:
        from audit_diesel.models import Abastecimento  # local import: ciclo

        ab = session.get(Abastecimento, r.abastecimento_id)
        if ab is None:
            continue
        if inicio <= ab.data < fim:
            out.append(r)
    return out


def _build_consolidado(session: Session) -> ConsolidadoResponse:
    """Monta a visao consolidada (1 linha por NF + agregados de cabecalho)."""
    checklists = list(
        session.exec(select(Checklist).order_by(Checklist.data_recebimento)).all()
    )
    auditorias_por_nf_atual: dict[str, Auditoria] = {}
    for a in session.exec(
        select(Auditoria).order_by(Auditoria.criada_em.desc())
    ).all():
        auditorias_por_nf_atual.setdefault(a.nf_atual, a)

    alertas_por_auditoria: dict[int, list[Alerta]] = {}
    for al in session.exec(select(Alerta)).all():
        alertas_por_auditoria.setdefault(al.auditoria_id, []).append(al)

    items: list[NFConsolidadoItem] = []
    total_auditado = 0.0
    diff_litros_total = 0.0
    diff_brl_total = 0.0
    total_alertas = 0
    qtd_aprov = 0
    qtd_inc = 0
    qtd_nao_aud = 0
    qtd_pend = 0

    for ck in checklists:
        total_auditado += ck.valor_total_nf
        a = auditorias_por_nf_atual.get(ck.nota_fiscal)
        alertas = alertas_por_auditoria.get(int(a.id or 0), []) if a else []
        alertas_resumo: list[AlertaConsolidado] = []
        impacto_total = 0.0
        if alertas:
            por_tipo: dict[str, list[Alerta]] = {}
            for al in alertas:
                por_tipo.setdefault(al.tipo, []).append(al)
                if al.impacto_financeiro:
                    impacto_total += al.impacto_financeiro
            for tipo, lst in por_tipo.items():
                # severidade representativa = a maior do grupo
                sev_order = {"alta": 0, "media": 1, "baixa": 2}
                sev = sorted(lst, key=lambda x: sev_order.get(x.severidade, 9))[0].severidade
                alertas_resumo.append(
                    AlertaConsolidado(tipo=tipo, severidade=sev, qtd=len(lst))
                )
        qtd_alta = sum(1 for al in alertas if al.severidade == "alta")
        if a is None:
            qtd_nao_aud += 1
            validacao = None
            nf_anterior = None
            diff_l = None
            diff_p = None
        else:
            validacao = a.validacao_final
            if validacao == "APROVADO":
                qtd_aprov += 1
            else:
                qtd_inc += 1
            nf_anterior = a.nf_anterior
            diff_l = a.diferenca_litros
            diff_p = a.diferenca_percentual
            diff_litros_total += a.diferenca_litros
            diff_brl_total += a.diferenca_litros * ck.preco_unitario
            # Alerta NAO_CADASTRADO ainda nao reconciliado = pendente.
            qtd_pend += sum(1 for al in alertas if al.tipo == "NAO_CADASTRADO")
        total_alertas += len(alertas)
        items.append(
            NFConsolidadoItem(
                nota_fiscal=ck.nota_fiscal,
                data_recebimento=ck.data_recebimento.date(),
                nome_obra=ck.nome_obra,
                qtd_litros=round(ck.quantidade_nf_litros, 2),
                valor_total=round(ck.valor_total_nf, 2),
                valor_litro=round(ck.preco_unitario, 4),
                auditoria_id=int(a.id) if (a and a.id) else None,
                nf_anterior=nf_anterior,
                diferenca_litros=round(diff_l, 2) if diff_l is not None else None,
                diferenca_percentual=round(diff_p, 6) if diff_p is not None else None,
                validacao_final=validacao,
                qtd_alertas=len(alertas),
                qtd_alertas_alta=qtd_alta,
                alertas=alertas_resumo,
                impacto_financeiro_total=round(impacto_total, 2),
            )
        )

    periodo_inicio = checklists[0].data_recebimento.date() if checklists else None
    periodo_fim = checklists[-1].data_recebimento.date() if checklists else None

    return ConsolidadoResponse(
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        total_auditado_brl=round(total_auditado, 2),
        diferenca_total_litros=round(diff_litros_total, 2),
        diferenca_total_brl=round(diff_brl_total, 2),
        total_alertas=total_alertas,
        qtd_aprovadas=qtd_aprov,
        qtd_inconsistentes=qtd_inc,
        qtd_nao_auditadas=qtd_nao_aud,
        qtd_reconciliacoes_pendentes=qtd_pend,
        items=items,
    )


def _to_csv(payload: ConsolidadoResponse) -> str:
    """Serializa o consolidado em CSV legivel para auditoria/Excel."""
    import csv  # noqa: PLC0415
    import io  # noqa: PLC0415

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    w.writerow(
        [
            "Nota Fiscal",
            "Data",
            "Obra",
            "Quantidade (L)",
            "Valor (R$)",
            "Valor unitario (R$/L)",
            "NF anterior",
            "Diferenca (L)",
            "Diferenca (%)",
            "Status",
            "Alertas (qtd)",
            "Alertas alta severidade",
            "Tipos de alerta",
            "Impacto financeiro (R$)",
        ]
    )
    for it in payload.items:
        tipos = ", ".join(f"{a.tipo}({a.qtd})" for a in it.alertas)
        w.writerow(
            [
                it.nota_fiscal,
                it.data_recebimento.strftime("%d/%m/%Y"),
                it.nome_obra,
                f"{it.qtd_litros:.2f}".replace(".", ","),
                f"{it.valor_total:.2f}".replace(".", ","),
                f"{it.valor_litro:.4f}".replace(".", ","),
                it.nf_anterior or "",
                f"{it.diferenca_litros:.2f}".replace(".", ",") if it.diferenca_litros is not None else "",
                f"{(it.diferenca_percentual or 0) * 100:.2f}".replace(".", ",") if it.diferenca_percentual is not None else "",
                it.validacao_final or "NAO_AUDITADA",
                str(it.qtd_alertas),
                str(it.qtd_alertas_alta),
                tipos,
                f"{it.impacto_financeiro_total:.2f}".replace(".", ","),
            ]
        )
    return buf.getvalue()


def _to_response(
    resultado: AuditoriaCompleta,
    parecer_meta: ParecerMeta | None,
) -> AuditoriaCompletaResponse:
    a = resultado.auditoria
    return AuditoriaCompletaResponse(
        auditoria=AuditoriaIndicadores(
            id=int(a.id or 0),
            nf_anterior=a.nf_anterior,
            nf_atual=a.nf_atual,
            nome_obra=a.nome_obra,
            criada_em=a.criada_em,
            estoque_inicial_anterior=a.estoque_inicial_anterior,
            quantidade_descarregada_anterior=a.quantidade_descarregada_anterior,
            estoque_final_teorico_anterior=a.estoque_final_teorico_anterior,
            saidas_registradas_litros=a.saidas_registradas_litros,
            saidas_registradas_custo=a.saidas_registradas_custo,
            estoque_inicial_atual=a.estoque_inicial_atual,
            saida_teorica_litros=a.saida_teorica_litros,
            diferenca_litros=a.diferenca_litros,
            diferenca_percentual=a.diferenca_percentual,
            qtd_equipamentos_nao_cadastrados=a.qtd_equipamentos_nao_cadastrados,
            validacao_final=a.validacao_final,
            parecer_ia=a.parecer_ia,
            aprovada_em=a.aprovada_em,
            auditor_aprovacao=a.auditor_aprovacao,
            observacao_aprovacao=a.observacao_aprovacao,
        ),
        alertas=[
            AlertaResponse(
                id=int(al.id or 0),
                tipo=al.tipo,
                severidade=al.severidade,
                titulo=al.titulo,
                descricao=al.descricao,
                abastecimento_id=al.abastecimento_id,
                impacto_financeiro=al.impacto_financeiro,
                payload=json.loads(al.payload_json) if al.payload_json else {},
            )
            for al in resultado.alertas
        ],
        parecer_meta=parecer_meta,
    )
