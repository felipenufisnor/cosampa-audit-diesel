"""Fixtures determinísticas para o modo offline.

Simulam respostas razoáveis de um modelo Qwen coder/reasoning para as duas
tarefas do sistema (`reconciliador`, `parecer`). A lógica é suficiente para
exercitar o pipeline ponta-a-ponta sem depender de chave de provider.

Identificação de tarefa: olhamos o primeiro system message procurando os
markers `[task:reconciliador]` e `[task:parecer]` definidos nos prompts.
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any

from .parecer_deterministico import gerar_parecer_deterministico
from .prompts.parecer import TASK_MARKER as PARECER_MARKER
from .prompts.reconciliador import TASK_MARKER as RECONCILIADOR_MARKER


def responder(
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Despacha a chamada para a fixture certa baseado no marker da tarefa."""
    system = _first_system_content(messages)
    if RECONCILIADOR_MARKER in system:
        return _reconciliador_response(messages, tools)
    if PARECER_MARKER in system:
        return _parecer_response(messages)
    return _empty_response("Tarefa desconhecida pelo provider offline.")


def _first_system_content(messages: list[dict[str, Any]]) -> str:
    for m in messages:
        if m.get("role") == "system":
            return str(m.get("content") or "")
    return ""


def _last_user_content(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content") or "")
    return ""


def _norm(s: str) -> str:
    """Normaliza para comparacao: uppercase + sem acentos + sem .-/espacos."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[\s\.\-/]", "", s)
    return s.upper()


# --------------------------------------------------------------------------- #
# Reconciliador
# --------------------------------------------------------------------------- #


def _reconciliador_response(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Heuristica de matching que mimetiza um modelo Qwen razoavelmente afiado.

    Estrategia, em ordem:
    1. Match exato no identificador normalizado.
    2. Match parcial (substring) entre identificadores normalizados.
    3. Match semantico no apelido contra Equipamento/Modelo/Marca do candidato.
    4. Senao, mobilizado_id_candidato=null.
    """
    payload = _safe_json(_last_user_content(messages))
    abastecimentos = payload.get("abastecimentos_nao_cadastrados", [])
    candidatos = payload.get("candidatos_gp_mesma_obra", [])

    sugestoes: list[dict[str, Any]] = []
    for ab in abastecimentos:
        sug = _melhor_sugestao(ab, candidatos)
        sugestoes.append(sug)

    args_json = json.dumps({"sugestoes": sugestoes}, ensure_ascii=False)
    tool_call = {
        "id": f"call_{uuid.uuid4().hex[:12]}",
        "type": "function",
        "function": {
            "name": "registrar_sugestoes",
            "arguments": args_json,
        },
    }
    return _wrap_response(
        content="",
        tool_calls=[tool_call],
        usage_in=len(json.dumps(payload)),
        usage_out=len(args_json),
        finish_reason="tool_calls",
    )


def _melhor_sugestao(
    ab: dict[str, Any], candidatos: list[dict[str, Any]]
) -> dict[str, Any]:
    """Decide o melhor candidato para um abastecimento (algoritmo determinisitico)."""
    veiculo = str(ab.get("veiculo_raw") or "")
    apelido = str(ab.get("apelido") or "")
    veiculo_norm = _norm(veiculo)
    apelido_norm = _norm(apelido)

    melhor: dict[str, Any] | None = None
    melhor_score = 0.0
    melhor_motivo = ""

    for c in candidatos:
        placa_norm = _norm(str(c.get("placa_ativo_raw") or ""))
        equip_norm = _norm(str(c.get("equipamento") or ""))
        marca_norm = _norm(str(c.get("marca") or ""))
        modelo_norm = _norm(str(c.get("modelo") or ""))

        score = 0.0
        motivo = ""

        if placa_norm and placa_norm == veiculo_norm:
            score, motivo = 0.95, (
                f"Identificadores normalizam para o mesmo valor ({placa_norm})."
            )
        elif placa_norm and (
            placa_norm in veiculo_norm or veiculo_norm in placa_norm
        ):
            score, motivo = 0.78, (
                f"Identificador do GP {c.get('placa_ativo_raw')} aparece "
                f"como subsequência da placa Infleet {veiculo}."
            )
        elif apelido_norm and len(equip_norm) >= 4 and equip_norm in apelido_norm:
            score, motivo = 0.82, (
                f"Apelido do Infleet '{apelido}' contém o equipamento "
                f"'{c.get('equipamento')}' do candidato GP id={c.get('id')}."
            )
        elif apelido_norm and len(modelo_norm) >= 4 and modelo_norm in apelido_norm:
            score, motivo = 0.7, (
                f"Apelido '{apelido}' contém o modelo '{c.get('modelo')}' "
                f"(GP id={c.get('id')})."
            )
        elif apelido_norm and len(marca_norm) >= 4 and marca_norm in apelido_norm:
            score, motivo = 0.55, (
                f"Apelido '{apelido}' contém a marca '{c.get('marca')}' "
                f"(GP id={c.get('id')}); evidência parcial."
            )
        else:
            continue

        if score > melhor_score:
            melhor = c
            melhor_score = score
            melhor_motivo = motivo

    if melhor is None or melhor_score < 0.4:
        return {
            "abastecimento_id": ab.get("abastecimento_id"),
            "mobilizado_id_candidato": None,
            "confianca": 0.0,
            "justificativa": (
                f"Nenhum candidato para {veiculo!r} tem evidência suficiente "
                f"(>= 0.40) entre os {len(candidatos)} mobilizados da obra."
            ),
        }
    return {
        "abastecimento_id": ab.get("abastecimento_id"),
        "mobilizado_id_candidato": melhor.get("id"),
        "confianca": round(melhor_score, 2),
        "justificativa": melhor_motivo,
    }


# --------------------------------------------------------------------------- #
# Parecer
# --------------------------------------------------------------------------- #


def _parecer_response(messages: list[dict[str, Any]]) -> dict[str, Any]:
    payload = _safe_json(_last_user_content(messages))
    parecer = gerar_parecer_deterministico(payload)

    return _wrap_response(
        content=parecer,
        tool_calls=[],
        usage_in=len(json.dumps(payload)),
        usage_out=len(parecer),
        finish_reason="stop",
    )

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _safe_json(text: str) -> dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {"_raw": data}


def _wrap_response(
    *,
    content: str,
    tool_calls: list[dict[str, Any]],
    usage_in: int,
    usage_out: int,
    finish_reason: str,
) -> dict[str, Any]:
    """Constroi um envelope no formato OpenAI Chat Completions."""
    return {
        "id": f"chatcmpl-offline-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(datetime.now(tz=timezone.utc).timestamp()),
        "model": "qwen3-32b-offline-mock",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls or None,
                },
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": max(1, usage_in // 4),
            "completion_tokens": max(1, usage_out // 4),
            "total_tokens": max(1, (usage_in + usage_out) // 4),
        },
    }


def _empty_response(reason: str) -> dict[str, Any]:
    return _wrap_response(
        content=f"[fixture] {reason}",
        tool_calls=[],
        usage_in=len(reason),
        usage_out=len(reason),
        finish_reason="stop",
    )
