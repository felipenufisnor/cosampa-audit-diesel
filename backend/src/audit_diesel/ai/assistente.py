"""Orquestrador do Assistente de Investigacao (Feature B da v2).

Loop:
1. Monta `messages` com SYSTEM_PROMPT + contexto da auditoria + historico
   persistido + nova pergunta.
2. Chama LLM SYNC com `tools` habilitadas (max 4 iteracoes para evitar loop
   infinito). Cada `tool_calls` retornado e' executado localmente; o
   resultado e' adicionado como `role=tool` no historico.
3. Quando o LLM responde sem tool_calls, fazemos UMA nova chamada em modo
   STREAMING para emitir a resposta final ao frontend chunk-por-chunk.
4. Em modo offline, todo o passo 3 vira replay deterministico do
   stream_completion offline, com 1 tool call sintetica baseado na
   pergunta (para a UX nao ficar vazia).

Eventos SSE emitidos:
    tool_call_started     {nome, argumentos}
    tool_call_completed   {nome, resultado_resumo}
    assistant_chunk       {texto}
    assistant_done        {mensagem_completa, tokens_estimados}
    error                 {mensagem, fallback_acionado}

A persistencia das mensagens visiveis (`user` e `assistant`) acontece no
final do loop, NAO durante o stream, para nao deixar gravacao parcial.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from sqlmodel import Session, select

from audit_diesel.audit.engine import AuditoriaCompleta
from audit_diesel.config import BACKEND_DIR
from audit_diesel.models import Alerta, Auditoria, MensagemAssistente

from .client import ChatClient, ChatMessage
from .prompts import assistente as prompts
from .tools import TOOL_SCHEMAS, TOOLS_REGISTRY

CACHE_DIR: Path = BACKEND_DIR / "data" / "cache"

log = structlog.get_logger("audit_diesel.ai.assistente")

MAX_TOOL_ITERATIONS = 4
MAX_HISTORICO_MENSAGENS = 12


def _sse(event: str, payload: dict[str, Any]) -> str:
    body = {"event": event, "payload": payload}
    return f"data: {json.dumps(body, ensure_ascii=False, default=str)}\n\n"


async def stream_pergunta(
    *,
    session: Session,
    auditoria_id: int,
    pergunta: str,
    chat: ChatClient | None = None,
) -> AsyncIterator[str]:
    """Executa o loop do assistente e emite eventos SSE."""
    chat = chat or ChatClient()
    pergunta = pergunta.strip()
    if not pergunta:
        yield _sse("error", {"mensagem": "pergunta vazia", "fallback_acionado": False})
        return

    auditoria = session.get(Auditoria, auditoria_id)
    if auditoria is None:
        yield _sse("error", {
            "mensagem": f"Auditoria {auditoria_id} não encontrada",
            "fallback_acionado": False,
        })
        return

    alertas = list(session.exec(
        select(Alerta).where(Alerta.auditoria_id == auditoria_id)
    ).all())
    payload = AuditoriaCompleta(auditoria=auditoria, alertas=alertas).to_dict()

    historico_db = _carregar_historico(session, auditoria_id)
    messages = _montar_messages(payload, historico_db, pergunta)
    yield _sse("assistant_status", {
        "mensagem": "Preparando análise da auditoria...",
    })
    await asyncio.sleep(0.01)

    # Modo offline: tenta replay do cache JSON; fallback honesto se nao houver.
    if chat.provider.info.offline:
        cache = _carregar_cache_chips(auditoria, pergunta)
        if cache is not None:
            async for ev in _replay_cache(cache):
                yield ev
            _persistir(session, auditoria_id, pergunta, cache.get("resposta") or "")
            return
        async for ev in _fallback_offline_honesto(pergunta):
            yield ev
        _persistir(session, auditoria_id, pergunta, _FALLBACK_TEXTO)
        return

    # Online: ate MAX_TOOL_ITERATIONS rodadas com tools.
    final_text = ""
    fallback_used = False
    for iteracao in range(MAX_TOOL_ITERATIONS):
        try:
            response = await asyncio.to_thread(
                chat.chat,
                messages=messages,
                tools=TOOL_SCHEMAS,
                temperature=0.3,
                max_tokens=600,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("assistente.chat_falhou", iter=iteracao, error=str(exc))
            cache = _carregar_cache_chips(auditoria, pergunta)
            if cache is not None:
                async for ev in _replay_cache(cache):
                    yield ev
                _persistir(session, auditoria_id, pergunta, cache.get("resposta") or "")
                return
            async for ev in _fallback_sem_cache():
                yield ev
            return

        if not response.tool_calls:
            # Modelo terminou sem chamar tools. Emite o conteudo direto
            # como chunks (sem precisar de novo round-trip de streaming).
            final_text = response.content or ""
            for chunk in _quebrar_em_chunks(final_text):
                yield _sse("assistant_chunk", {"texto": chunk})
            break

        # Existem tool_calls: executa cada uma e injeta resultado no historico.
        tc_dicts: list[dict[str, Any]] = []
        for tc in response.tool_calls:
            tc_dicts.append({
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.name, "arguments": tc.arguments_json},
            })
        messages.append(ChatMessage(
            role="assistant",
            content=response.content or "",
            tool_calls=tc_dicts,
        ))

        for tc in response.tool_calls:
            yield _sse("tool_call_started", {
                "nome": tc.name,
                "argumentos": _safe_loads(tc.arguments_json),
            })
            resultado, resumo = _executar_tool(session, tc.name, tc.arguments_json)
            yield _sse("tool_call_completed", {
                "nome": tc.name,
                "resultado_resumo": resumo,
            })
            messages.append(ChatMessage(
                role="tool",
                content=json.dumps(resultado, ensure_ascii=False, default=str),
                tool_call_id=tc.id,
                name=tc.name,
            ))
    else:
        # Estouro do loop sem texto final: gera fallback.
        fallback_used = True
        final_text = (
            "Não consegui concluir a investigação após várias consultas. "
            "Refraseie a pergunta ou consulte diretamente os alertas da auditoria."
        )
        for chunk in _quebrar_em_chunks(final_text):
            yield _sse("assistant_chunk", {"texto": chunk})

    yield _sse("assistant_done", {
        "mensagem_completa": final_text,
        "tokens_estimados": max(1, len(final_text) // 4),
        "fallback_acionado": fallback_used,
    })
    _persistir(session, auditoria_id, pergunta, final_text)
    if final_text:
        salvar_cache_chip(
            auditoria_id,
            pergunta,
            final_text,
            nf_anterior=auditoria.nf_anterior,
            nf_atual=auditoria.nf_atual,
        )


_FALLBACK_TEXTO = (
    "O assistente de IA está temporariamente indisponível neste ambiente, "
    "então não foi possível analisar esta pergunta livre. Use uma das "
    "perguntas sugeridas no rodapé (que têm resposta pré-cacheada) ou "
    "consulte diretamente os alertas listados nesta auditoria."
)


def hash_pergunta(pergunta: str) -> str:
    """Hash estavel para indexar respostas cacheadas no cache JSON."""
    normalizada = " ".join(pergunta.strip().lower().split())
    return hashlib.sha1(normalizada.encode("utf-8")).hexdigest()[:12]


def cache_path_legacy(auditoria_id: int) -> Path:
    return CACHE_DIR / f"assistente_{auditoria_id}.json"


def cache_path_janela(nf_anterior: str, nf_atual: str) -> Path:
    return CACHE_DIR / f"assistente_NF_{nf_atual}_anterior_{nf_anterior}.json"


def _cache_paths(auditoria: Auditoria) -> list[Path]:
    paths = [cache_path_janela(auditoria.nf_anterior, auditoria.nf_atual)]
    if auditoria.id is not None:
        paths.append(cache_path_legacy(int(auditoria.id)))
    return paths


def _ler_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("assistente.cache_corrompido", path=str(path), error=str(exc))
        return None
    return doc if isinstance(doc, dict) else None


def perguntas_cacheadas_para_auditoria(auditoria: Auditoria) -> list[str]:
    """Perguntas com resposta cacheada, preferindo cache estavel por janela."""
    perguntas: list[str] = []
    vistas: set[str] = set()
    for path in _cache_paths(auditoria):
        doc = _ler_cache(path)
        if doc is None:
            continue
        for entrada in (doc.get("entradas") or {}).values():
            pergunta_txt = str(entrada.get("pergunta") or "").strip()
            normalizada = " ".join(pergunta_txt.lower().split())
            if pergunta_txt and normalizada not in vistas:
                perguntas.append(pergunta_txt)
                vistas.add(normalizada)
    return perguntas


def existe_cache_assistente() -> bool:
    """Sinal global para /healthz indicar se ha fallback local disponivel."""
    if not CACHE_DIR.exists():
        return False
    return any(CACHE_DIR.glob("assistente_*.json"))


def _carregar_cache_chips(
    auditoria: Auditoria,
    pergunta: str,
) -> dict[str, Any] | None:
    """Busca pelo hash no cache por janela e, em seguida, no legado por id."""
    h = hash_pergunta(pergunta)
    for path in _cache_paths(auditoria):
        doc = _ler_cache(path)
        if doc is None:
            continue
        entrada = (doc.get("entradas") or {}).get(h)
        if entrada is not None:
            return entrada
    return None


def salvar_cache_chip(
    auditoria_id: int,
    pergunta: str,
    resposta: str,
    tool_calls: list[dict[str, Any]] | None = None,
    nf_anterior: str | None = None,
    nf_atual: str | None = None,
) -> None:
    """Helper usado pelo `scripts/popular_cache_v2.py` para gravar uma entrada."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    entrada = {
        "pergunta": pergunta,
        "resposta": resposta,
        "tool_calls": tool_calls or [],
        "gravado_em": datetime.now().isoformat(),
    }
    targets: list[tuple[Path, dict[str, Any]]] = [
        (cache_path_legacy(auditoria_id), {"auditoria_id": auditoria_id, "entradas": {}})
    ]
    if nf_anterior and nf_atual:
        targets.insert(
            0,
            (
                cache_path_janela(nf_anterior, nf_atual),
                {
                    "nf_anterior": nf_anterior,
                    "nf_atual": nf_atual,
                    "entradas": {},
                },
            ),
        )
    for path, default_doc in targets:
        _salvar_entrada_cache(path, default_doc, pergunta, entrada)


def _salvar_entrada_cache(
    path: Path,
    default_doc: dict[str, Any],
    pergunta: str,
    entrada: dict[str, Any],
) -> None:
    doc = default_doc
    if path.exists():
        try:
            with path.open(encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, json.JSONDecodeError):
            pass
    entradas = doc.setdefault("entradas", {})
    entradas[hash_pergunta(pergunta)] = entrada
    with path.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)


async def _replay_cache(cache: dict[str, Any]) -> AsyncIterator[str]:
    """Replay deterministico a partir da entrada cacheada."""
    for tc in cache.get("tool_calls") or []:
        yield _sse("tool_call_started", {
            "nome": tc.get("nome", ""),
            "argumentos": tc.get("argumentos") or {},
        })
        await asyncio.sleep(0.15)
        yield _sse("tool_call_completed", {
            "nome": tc.get("nome", ""),
            "resultado_resumo": tc.get("resultado_resumo", "consulta cacheada"),
        })
        await asyncio.sleep(0.15)
    resposta = cache.get("resposta") or ""
    # Quebra em chunks ~8 chars para simular streaming natural
    for i in range(0, len(resposta), 8):
        yield _sse("assistant_chunk", {"texto": resposta[i : i + 8]})
        await asyncio.sleep(0.018)
    yield _sse("assistant_done", {
        "mensagem_completa": resposta,
        "tokens_estimados": max(1, len(resposta) // 4),
        "fallback_acionado": False,
    })


async def _fallback_offline_honesto(_pergunta: str) -> AsyncIterator[str]:
    """Resposta padrao quando a pergunta livre nao esta no cache."""
    for i in range(0, len(_FALLBACK_TEXTO), 8):
        yield _sse("assistant_chunk", {"texto": _FALLBACK_TEXTO[i : i + 8]})
        await asyncio.sleep(0.012)
    yield _sse("assistant_done", {
        "mensagem_completa": _FALLBACK_TEXTO,
        "tokens_estimados": max(1, len(_FALLBACK_TEXTO) // 4),
        "fallback_acionado": True,
    })


async def _fallback_sem_cache() -> AsyncIterator[str]:
    texto = (
        "Assistente de IA indisponível e sem respostas pré-carregadas para "
        "esta auditoria. Verifique a configuração da IA ou consulte os alertas "
        "desta NF enquanto o serviço é restabelecido."
    )
    for chunk in _quebrar_em_chunks(texto):
        yield _sse("assistant_chunk", {"texto": chunk})
        await asyncio.sleep(0.012)
    yield _sse("assistant_done", {
        "mensagem_completa": texto,
        "tokens_estimados": max(1, len(texto) // 4),
        "fallback_acionado": True,
    })


def _carregar_historico(session: Session, auditoria_id: int) -> list[MensagemAssistente]:
    msgs = list(session.exec(
        select(MensagemAssistente)
        .where(MensagemAssistente.auditoria_id == auditoria_id)
        .order_by(MensagemAssistente.criada_em)
    ).all())
    # Trunca pelo final para nao explodir o contexto.
    return msgs[-MAX_HISTORICO_MENSAGENS:]


def _montar_messages(
    payload: dict[str, Any],
    historico: list[MensagemAssistente],
    pergunta: str,
) -> list[ChatMessage]:
    msgs: list[ChatMessage] = [
        ChatMessage(role="system", content=prompts.SYSTEM_PROMPT),
        ChatMessage(role="system", content=prompts.montar_contexto_auditoria(payload)),
    ]
    for h in historico:
        msgs.append(ChatMessage(role=h.papel, content=h.conteudo))
    msgs.append(ChatMessage(role="user", content=pergunta))
    return msgs


def _executar_tool(
    session: Session,
    nome: str,
    arguments_json: str,
) -> tuple[dict[str, Any], str]:
    """Executa a tool localmente; retorna (resultado, resumo curto)."""
    fn = TOOLS_REGISTRY.get(nome)
    if fn is None:
        return ({"erro": f"tool {nome} nao registrada"}, "tool desconhecida")
    try:
        args = json.loads(arguments_json) if arguments_json else {}
        if not isinstance(args, dict):
            args = {}
    except json.JSONDecodeError as exc:
        return ({"erro": f"argumentos invalidos: {exc}"}, "argumentos invalidos")
    try:
        resultado = fn(session, **args)
    except TypeError as exc:
        return ({"erro": f"assinatura: {exc}"}, "assinatura invalida")
    except Exception as exc:  # noqa: BLE001
        log.warning("assistente.tool_falhou", nome=nome, error=str(exc))
        return ({"erro": str(exc)}, "falha na execucao")
    resumo = _resumir(resultado)
    return (resultado, resumo)


def _resumir(resultado: dict[str, Any]) -> str:
    """Resumo curto para mostrar ao usuario entre mensagens."""
    if "erro" in resultado:
        return f"erro: {resultado['erro']}"
    if "n_abastecimentos" in resultado:
        return (
            f"{resultado.get('n_abastecimentos', 0)} abastecimentos em "
            f"{resultado.get('dias', '?')} dias"
        )
    if "abastecimentos" in resultado:
        ab = resultado["abastecimentos"]
        return f"{ab.get('n', 0)} abastecimentos, R$ {ab.get('total_custo_brl', 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if "deltas" in resultado:
        d = resultado["deltas"]
        return f"delta dif%={d.get('diferenca_pct_pp', 0):+.1f}pp"
    if "cadastrado_no_gp" in resultado:
        return "cadastrado" if resultado["cadastrado_no_gp"] else "nao cadastrado no GP"
    return "consulta concluida"


def _safe_loads(s: str) -> dict[str, Any]:
    try:
        v = json.loads(s) if s else {}
    except json.JSONDecodeError:
        v = {}
    return v if isinstance(v, dict) else {}


def _quebrar_em_chunks(texto: str, tamanho: int = 8) -> list[str]:
    """Emula streaming a partir de um texto ja completo (~25ms de leitura cada)."""
    return [texto[i : i + tamanho] for i in range(0, len(texto), tamanho)] or [""]


def _persistir(
    session: Session,
    auditoria_id: int,
    pergunta: str,
    resposta: str,
) -> None:
    """Grava pergunta + resposta no historico."""
    agora = datetime.now()
    session.add(MensagemAssistente(
        auditoria_id=auditoria_id,
        papel="user",
        conteudo=pergunta,
        criada_em=agora,
    ))
    session.add(MensagemAssistente(
        auditoria_id=auditoria_id,
        papel="assistant",
        conteudo=resposta or "",
        criada_em=agora,
        tokens_estimados=max(1, len(resposta or "") // 4),
    ))
    session.commit()
