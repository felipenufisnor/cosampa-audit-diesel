"""Orquestrador SSE da Feature A (Reasoning Stream).

Roda uma auditoria entre `nf_anterior` e `nf_atual` enquanto narra em
tempo real cada etapa deterministica e os pontos onde o LLM agrega
valor. Eventos sao emitidos no formato Server-Sent Events:

    data: {"event": "<tipo>", "payload": {...}}\\n\\n

Tipos de evento (todos com `event` no JSON, para o frontend nao depender de
campos SSE customizados):

    step_started           {step, tempo_estimado_s}
    step_completed         {step, duracao_ms, resumo}
    insight_found          {tipo, descricao, severidade}
    ia_thinking_start      {contexto, modelo}
    ia_thinking_chunk      {texto}
    ia_thinking_end        {tokens_estimados, duracao_ms}
    final_result           AuditoriaCompletaResponse (mesmo shape do /auditorias)
    error                  {mensagem, fallback_acionado}

A engine deterministica (`AuditEngine.auditar`) e' chamada uma unica vez no
inicio para coletar todos os indicadores reais; em seguida o orquestrador
narra os passos com base nesses dados verdadeiros. As 3 chamadas LLM
intercaladas (reconciliacao narrativa, outlier narrativa, parecer) sao
streamings reais ao OpenRouter quando online; replay determinisitico
quando AUDIT_AI_OFFLINE=1.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import structlog
from sqlmodel import Session

from audit_diesel.audit.engine import (
    AuditEngine,
    AuditoriaCompleta,
    ChecklistNaoEncontrado,
    ParTemporalInvalido,
)
from audit_diesel.models import Alerta

from .client import ChatClient, ChatMessage
from .parecer import GeradorParecer
from .prompts import parecer as parecer_prompts

log = structlog.get_logger("audit_diesel.ai.streaming")

# Ritmo minimo entre passos deterministicos: garante que o stream nao termine
# em <6s mesmo em maquinas rapidas (a leitura humana precisa cadencia).
PASSO_PAUSA_S = 0.35


def _sse(event: str, payload: dict[str, Any]) -> str:
    """Serializa um evento no formato SSE consumido por EventSource."""
    body = {"event": event, "payload": payload}
    return f"data: {json.dumps(body, ensure_ascii=False, default=str)}\n\n"


async def stream_auditoria(
    *,
    session: Session,
    nf_anterior: str,
    nf_atual: str,
    chat: ChatClient | None = None,
) -> AsyncIterator[str]:
    """Executa a auditoria narrando o raciocinio em SSE."""
    chat = chat or ChatClient()
    t_total = time.perf_counter()

    # --- Passo 1: carregar checklists ---------------------------------------
    yield _sse("step_started", {
        "step": f"Carregando checklists NF {nf_anterior} e NF {nf_atual}",
        "tempo_estimado_s": 1,
    })
    t0 = time.perf_counter()
    engine = AuditEngine(session)
    try:
        resultado: AuditoriaCompleta = await asyncio.to_thread(
            engine.auditar, nf_anterior, nf_atual
        )
    except ChecklistNaoEncontrado as exc:
        yield _sse("error", {
            "mensagem": str(exc),
            "fallback_acionado": False,
        })
        return
    except ParTemporalInvalido as exc:
        yield _sse("error", {
            "mensagem": str(exc),
            "fallback_acionado": False,
        })
        return
    except Exception as exc:  # noqa: BLE001
        log.exception("streaming.auditar_failed")
        yield _sse("error", {
            "mensagem": f"Falha na auditoria determinística: {exc}",
            "fallback_acionado": False,
        })
        return

    auditoria = resultado.auditoria
    alertas = resultado.alertas
    payload = resultado.to_dict()
    yield _sse("step_completed", {
        "step": f"Carregando checklists NF {nf_anterior} e NF {nf_atual}",
        "duracao_ms": int((time.perf_counter() - t0) * 1000),
        "resumo": "2 checklists carregados",
    })
    await asyncio.sleep(PASSO_PAUSA_S)

    # --- Passo 2: janela temporal -------------------------------------------
    yield _sse("step_started", {
        "step": "Calculando janela temporal",
        "tempo_estimado_s": 1,
    })
    t0 = time.perf_counter()
    yield _sse("insight_found", {
        "tipo": "janela_temporal",
        "descricao": _texto_janela(session, nf_anterior, nf_atual),
        "severidade": "info",
    })
    yield _sse("step_completed", {
        "step": "Calculando janela temporal",
        "duracao_ms": int((time.perf_counter() - t0) * 1000),
        "resumo": "janela definida",
    })
    await asyncio.sleep(PASSO_PAUSA_S)

    # --- Passo 3: abastecimentos na janela ----------------------------------
    yield _sse("step_started", {
        "step": "Identificando abastecimentos no período",
        "tempo_estimado_s": 1,
    })
    t0 = time.perf_counter()
    n_abast = _contar_abastecimentos(session, nf_anterior, nf_atual)
    custo_total = float(auditoria.saidas_registradas_custo or 0.0)
    yield _sse("insight_found", {
        "tipo": "abastecimentos_total",
        "descricao": (
            f"{n_abast} abastecimentos identificados (Infleet), "
            f"R$ {custo_total:,.2f} no período"
        ).replace(",", "X").replace(".", ",").replace("X", "."),
        "severidade": "info",
    })
    yield _sse("step_completed", {
        "step": "Identificando abastecimentos no período",
        "duracao_ms": int((time.perf_counter() - t0) * 1000),
        "resumo": f"{n_abast} abastecimentos",
    })
    await asyncio.sleep(PASSO_PAUSA_S)

    # --- Passo 4: cruzar placas com GP --------------------------------------
    yield _sse("step_started", {
        "step": "Cruzando placas com cadastro do GP",
        "tempo_estimado_s": 1,
    })
    t0 = time.perf_counter()
    qtd_nc = int(auditoria.qtd_equipamentos_nao_cadastrados or 0)
    if qtd_nc > 0:
        yield _sse("insight_found", {
            "tipo": "nao_cadastrado",
            "descricao": (
                f"{qtd_nc} veiculo(s) sem correspondencia exata no GP"
            ),
            "severidade": "warning" if qtd_nc < 10 else "alta",
        })
    else:
        yield _sse("insight_found", {
            "tipo": "nao_cadastrado",
            "descricao": "todos os veículos da janela estão cadastrados no GP",
            "severidade": "info",
        })
    yield _sse("step_completed", {
        "step": "Cruzando placas com cadastro do GP",
        "duracao_ms": int((time.perf_counter() - t0) * 1000),
        "resumo": f"{qtd_nc} placa(s) sem match exato",
    })
    await asyncio.sleep(PASSO_PAUSA_S)

    # --- Passo 5: LLM streaming narrando a reconciliacao --------------------
    if qtd_nc > 0:
        yield _sse("ia_thinking_start", {
            "contexto": f"Reconciliando {qtd_nc} placas não-cadastradas via LLM",
            "modelo": chat.settings.llm_model,
        })
        t0 = time.perf_counter()
        chars = 0
        try:
            async for chunk in chat.stream_completion(
                feature="reasoning_stream_reconciliacao",
                messages=_prompt_reconciliacao_narrativa(payload, qtd_nc),
                max_tokens=220,
                temperature=0.3,
            ):
                chars += len(chunk)
                yield _sse("ia_thinking_chunk", {"texto": chunk})
        except Exception as exc:  # noqa: BLE001
            log.warning("streaming.reconciliacao_narrativa_failed", error=str(exc))
            yield _sse("error", {
                "mensagem": "Narrativa de reconciliação indisponível",
                "fallback_acionado": True,
            })
        yield _sse("ia_thinking_end", {
            "tokens_estimados": max(1, chars // 4),
            "duracao_ms": int((time.perf_counter() - t0) * 1000),
        })
        await asyncio.sleep(PASSO_PAUSA_S)

    # --- Passo 6: outliers ---------------------------------------------------
    yield _sse("step_started", {
        "step": "Calculando outliers de consumo",
        "tempo_estimado_s": 1,
    })
    t0 = time.perf_counter()
    outlier_alertas = [a for a in alertas if a.tipo == "OUTLIER_CONSUMO"]
    if outlier_alertas:
        for ot in outlier_alertas[:3]:
            yield _sse("insight_found", {
                "tipo": "outlier",
                "descricao": ot.titulo,
                "severidade": ot.severidade.lower() if ot.severidade else "warning",
            })
    else:
        yield _sse("insight_found", {
            "tipo": "outlier",
            "descricao": "nenhum outlier acima do z-score limite",
            "severidade": "info",
        })
    yield _sse("step_completed", {
        "step": "Calculando outliers de consumo",
        "duracao_ms": int((time.perf_counter() - t0) * 1000),
        "resumo": f"{len(outlier_alertas)} outlier(s)",
    })
    await asyncio.sleep(PASSO_PAUSA_S)

    # --- Passo 7: LLM streaming avaliando outlier ---------------------------
    if outlier_alertas:
        yield _sse("ia_thinking_start", {
            "contexto": "Avaliando se outlier tem contexto operacional justificável",
            "modelo": chat.settings.llm_model,
        })
        t0 = time.perf_counter()
        chars = 0
        try:
            async for chunk in chat.stream_completion(
                feature="reasoning_stream_outlier",
                messages=_prompt_outlier_narrativa(outlier_alertas[0]),
                max_tokens=180,
                temperature=0.3,
            ):
                chars += len(chunk)
                yield _sse("ia_thinking_chunk", {"texto": chunk})
        except Exception as exc:  # noqa: BLE001
            log.warning("streaming.outlier_narrativa_failed", error=str(exc))
            yield _sse("error", {
                "mensagem": "Avaliação de outlier indisponível",
                "fallback_acionado": True,
            })
        yield _sse("ia_thinking_end", {
            "tokens_estimados": max(1, chars // 4),
            "duracao_ms": int((time.perf_counter() - t0) * 1000),
        })
        await asyncio.sleep(PASSO_PAUSA_S)

    # --- Passo 8: parecer em streaming --------------------------------------
    yield _sse("ia_thinking_start", {
        "contexto": "Compondo parecer técnico",
        "modelo": chat.settings.llm_model,
    })
    t0 = time.perf_counter()
    chars = 0
    parecer_buffer = ""
    parecer_fallback = False
    try:
        async for chunk in chat.stream_completion(
            feature="reasoning_stream_parecer",
            messages=_prompt_parecer(payload),
            max_tokens=900,
            temperature=0.25,
        ):
            chars += len(chunk)
            parecer_buffer += chunk
            yield _sse("ia_thinking_chunk", {"texto": chunk})
    except Exception as exc:  # noqa: BLE001
        log.warning("streaming.parecer_failed", error=str(exc))
        parecer_fallback = True
        yield _sse("error", {
            "mensagem": "Parecer via streaming falhou; usando gerador padrão",
            "fallback_acionado": True,
        })
    yield _sse("ia_thinking_end", {
        "tokens_estimados": max(1, chars // 4),
        "duracao_ms": int((time.perf_counter() - t0) * 1000),
    })

    # --- Persistencia do parecer e final_result ------------------------------
    parecer_final = parecer_buffer.strip()
    if parecer_fallback or len(parecer_final) < 40:
        # Reusa o gerador completo (com guardrails e fallback deterministico).
        try:
            result = await asyncio.to_thread(GeradorParecer(client=chat).gerar, payload)
            parecer_final = result.markdown
        except Exception:  # noqa: BLE001
            log.exception("streaming.parecer_fallback_failed")
            parecer_final = parecer_final or "Parecer indisponível."

    auditoria.parecer_ia = parecer_final
    session.add(auditoria)
    session.commit()
    session.refresh(auditoria)

    # Refresca alertas pra incluir parecer atualizado no payload final.
    payload_final = AuditoriaCompleta(auditoria=auditoria, alertas=alertas).to_dict()
    payload_final["streaming_meta"] = {
        "duracao_total_s": round(time.perf_counter() - t_total, 2),
        "modo_offline": chat.provider.info.offline,
    }
    yield _sse("final_result", payload_final)


# ---------------------------------------------------------------------------
# Helpers para os prompts curtos das narrativas LLM
# ---------------------------------------------------------------------------


def _prompt_reconciliacao_narrativa(payload: dict[str, Any], qtd: int) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                "[task:reconciliacao_narrativa]\n"
                "Voce e' um auditor senior de combustivel. Em 2-3 frases curtas, "
                "explique como abordara a reconciliacao das placas nao "
                "cadastradas listadas. Sem markdown. Portugues do Brasil tecnico."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Foram detectadas {qtd} placas sem match exato no cadastro do GP "
                f"na NF {payload.get('auditoria', {}).get('nf_atual')}. Explique "
                "como avaliar: variacao de formatacao, indexacao por chassi/ativo "
                "ou ausencia real de cadastro. Nao liste placas individuais."
            ),
        ),
    ]


def _prompt_outlier_narrativa(alerta: Alerta) -> list[ChatMessage]:
    return [
        ChatMessage(
            role="system",
            content=(
                "[task:outlier_narrativa]\n"
                "Voce e' um auditor senior. Em 2-3 frases, avalie se o outlier "
                "abaixo pode ter justificativa operacional plausivel ou se exige "
                "acao imediata. Sem markdown. Portugues do Brasil tecnico."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Alerta: {alerta.titulo}.\nDescricao: {alerta.descricao}.\n"
                f"Severidade: {alerta.severidade}."
            ),
        ),
    ]


def _prompt_parecer(payload: dict[str, Any]) -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content=parecer_prompts.SYSTEM_PROMPT),
        ChatMessage(role="user", content=parecer_prompts.montar_user_message(payload)),
    ]


# ---------------------------------------------------------------------------
# Pequenos helpers de derivacao
# ---------------------------------------------------------------------------


def _contar_abastecimentos(session: Session, nf_anterior: str, nf_atual: str) -> int:
    """Conta abastecimentos da Infleet entre os dois descarregamentos."""
    from sqlmodel import select

    from audit_diesel.models import Abastecimento, Checklist

    ant = session.exec(select(Checklist).where(Checklist.nota_fiscal == nf_anterior)).first()
    atu = session.exec(select(Checklist).where(Checklist.nota_fiscal == nf_atual)).first()
    if not ant or not atu:
        return 0
    return len(list(session.exec(
        select(Abastecimento)
        .where(Abastecimento.data >= ant.datetime_fim_descarga)
        .where(Abastecimento.data < atu.datetime_fim_descarga)
    ).all()))


def _texto_janela(session: Session, nf_anterior: str, nf_atual: str) -> str:
    """Le os dois checklists para narrar a janela com data e duracao."""
    from sqlmodel import select

    from audit_diesel.models import Checklist

    ant = session.exec(select(Checklist).where(Checklist.nota_fiscal == nf_anterior)).first()
    atu = session.exec(select(Checklist).where(Checklist.nota_fiscal == nf_atual)).first()
    if not ant or not atu:
        return "janela calculada a partir dos checklists das duas NFs"
    dur = atu.datetime_fim_descarga - ant.datetime_fim_descarga
    dias = dur.days
    horas = dur.seconds // 3600
    return (
        f"janela: {ant.datetime_fim_descarga.strftime('%d/%m %H:%M')} -> "
        f"{atu.datetime_fim_descarga.strftime('%d/%m %H:%M')} "
        f"({dias} dia(s) {horas}h)"
    )
