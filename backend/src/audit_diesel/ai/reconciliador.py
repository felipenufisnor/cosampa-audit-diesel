"""ReconciliadorSemantico: monta input, chama o ChatClient e parseia output.

Pipeline:
1. Recebe `auditoria_id` -> carrega abastecimentos da janela com tipo
   NAO_CADASTRADO + lista de mobilizados da mesma obra.
2. Pre-filtra candidatos para nao mandar 286 itens; usa heuristica de
   identificador / tipo de equipamento para reduzir.
3. Chama o LLM em batches de 20 abastecimentos por chamada.
4. Parseia o tool call `registrar_sugestoes`, valida com pydantic e enriquece
   com dados do mobilizado para o frontend exibir sem N+1.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import structlog
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, select

from audit_diesel.models import Abastecimento, Alerta, Auditoria, Mobilizado

from . import cache
from .client import ChatClient, ChatMessage
from .prompts import reconciliador as prompts

log = structlog.get_logger("audit_diesel.ai.reconciliador")

BATCH_SIZE = 20


class _SugestaoLLM(BaseModel):
    """Item retornado pelo modelo (validacao do tool call)."""

    abastecimento_id: int
    mobilizado_id_candidato: int | None = None
    confianca: float = Field(ge=0.0, le=1.0)
    justificativa: str = Field(max_length=500)


class _SugestoesLLM(BaseModel):
    sugestoes: list[_SugestaoLLM]


@dataclass
class CandidatoGP:
    """Resumo de um Mobilizado enviado ao modelo como candidato."""

    id: int
    placa_ativo_raw: str
    placa_ativo_normalizada: str
    equipamento: str | None
    marca: str | None
    modelo: str | None
    tipo_equipamento: str | None
    capacidade_litros: int | None
    situacao: str

    @classmethod
    def from_model(cls, m: Mobilizado) -> CandidatoGP:
        return cls(
            id=int(m.id or 0),
            placa_ativo_raw=m.placa_ativo_raw,
            placa_ativo_normalizada=m.placa_ativo_normalizada,
            equipamento=m.equipamento,
            marca=m.marca,
            modelo=m.modelo,
            tipo_equipamento=m.tipo_equipamento,
            capacidade_litros=m.capacidade_litros,
            situacao=m.situacao,
        )


@dataclass
class SugestaoReconciliacao:
    """Sugestao final, enriquecida, pronta para o frontend."""

    abastecimento_id: int
    veiculo_infleet: str
    apelido_infleet: str | None
    candidato_gp: dict[str, Any] | None
    confianca: float
    justificativa: str


class ReconciliadorSemantico:
    """Orquestra reconciliacao de abastecimentos NAO_CADASTRADO via LLM."""

    def __init__(self, session: Session, client: ChatClient | None = None) -> None:
        self.session = session
        self.client = client or ChatClient()

    def sugerir_para_auditoria(self, auditoria_id: int) -> list[SugestaoReconciliacao]:
        """Gera sugestoes para todos os abastecimentos NAO_CADASTRADO da auditoria."""
        auditoria = self.session.get(Auditoria, auditoria_id)
        if auditoria is None:
            log.warning("reconciliador.auditoria_nao_encontrada", id=auditoria_id)
            return []

        # DEMO_MODE=true: tenta cache pelo par de NFs (id da auditoria pode
        # mudar quando a re-auditoria do fluxo /reconciliacao/aprovar recria
        # a auditoria). Se o cache existir, devolve as sugestoes prontas.
        cached = cache.get_cached_reconciliacao_par(
            auditoria.nf_anterior, auditoria.nf_atual
        )
        if cached:
            return _sugestoes_from_cached(cached)

        alertas = self.session.exec(
            select(Alerta)
            .where(Alerta.auditoria_id == auditoria_id)
            .where(Alerta.tipo == "NAO_CADASTRADO")
        ).all()
        if not alertas:
            return []

        abastecimentos: list[Abastecimento] = []
        for al in alertas:
            if al.abastecimento_id is None:
                continue
            ab = self.session.get(Abastecimento, al.abastecimento_id)
            if ab is not None:
                abastecimentos.append(ab)
        if not abastecimentos:
            return []

        candidatos_full = self.session.exec(
            select(Mobilizado).where(Mobilizado.nome_obra == auditoria.nome_obra)
        ).all()
        candidatos = [CandidatoGP.from_model(m) for m in candidatos_full]
        log.info(
            "reconciliador.start",
            auditoria_id=auditoria_id,
            abastecimentos=len(abastecimentos),
            candidatos=len(candidatos),
        )

        resultados: list[SugestaoReconciliacao] = []
        for i in range(0, len(abastecimentos), BATCH_SIZE):
            batch = abastecimentos[i : i + BATCH_SIZE]
            resultados.extend(self._sugerir_batch(batch, candidatos))

        # Persiste o snapshot para a apresentacao (record/replay-miss).
        if resultados:
            cache.save_cached_reconciliacao_par(
                auditoria.nf_anterior,
                auditoria.nf_atual,
                {"sugestoes": [_sugestao_to_dict(s) for s in resultados]},
            )
        return resultados

    def _sugerir_batch(
        self,
        abastecimentos: list[Abastecimento],
        candidatos: list[CandidatoGP],
    ) -> list[SugestaoReconciliacao]:
        # Pre-filtra candidatos para reduzir custo de tokens / ruido.
        filtrados = _prefiltrar_candidatos(abastecimentos, candidatos)
        ab_payload = [_abastecimento_payload(a) for a in abastecimentos]
        cand_payload = [_candidato_payload(c) for c in filtrados]

        user_msg = prompts.montar_user_message(ab_payload, cand_payload)
        response = self.client.chat(
            messages=[
                ChatMessage(role="system", content=prompts.SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_msg),
            ],
            tools=[prompts.TOOL_SCHEMA],
            tool_choice={
                "type": "function",
                "function": {"name": "registrar_sugestoes"},
            },
            temperature=0.1,
            max_tokens=2000,
        )

        sugestoes_validadas = _extrair_sugestoes(response)
        cand_index = {c.id: c for c in candidatos}
        ab_index = {a.id: a for a in abastecimentos}
        out: list[SugestaoReconciliacao] = []
        for s in sugestoes_validadas:
            ab = ab_index.get(s.abastecimento_id)
            if ab is None:
                continue
            cand = cand_index.get(s.mobilizado_id_candidato or 0)
            out.append(
                SugestaoReconciliacao(
                    abastecimento_id=int(ab.id or 0),
                    veiculo_infleet=ab.veiculo_raw,
                    apelido_infleet=ab.apelido,
                    candidato_gp=_candidato_payload(CandidatoGP.from_model(cand))
                    if cand is not None
                    else None,
                    confianca=float(s.confianca),
                    justificativa=s.justificativa,
                )
            )
        return out


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


_NORM_RE = re.compile(r"[\s\.\-/]")


def _norm(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return _NORM_RE.sub("", s).upper()


def _abastecimento_payload(a: Abastecimento) -> dict[str, Any]:
    return {
        "abastecimento_id": int(a.id or 0),
        "veiculo_raw": a.veiculo_raw,
        "veiculo_normalizado": a.veiculo_normalizado,
        "apelido": a.apelido,
        "data": a.data.isoformat(),
        "quantidade_litros": a.quantidade_litros,
        "custo_total": a.custo_total,
        "fornecedor": a.fornecedor,
    }


def _candidato_payload(c: CandidatoGP) -> dict[str, Any]:
    return {
        "id": c.id,
        "placa_ativo_raw": c.placa_ativo_raw,
        "placa_ativo_normalizada": c.placa_ativo_normalizada,
        "equipamento": c.equipamento,
        "marca": c.marca,
        "modelo": c.modelo,
        "tipo_equipamento": c.tipo_equipamento,
        "capacidade_litros": c.capacidade_litros,
        "situacao": c.situacao,
    }


def _prefiltrar_candidatos(
    abastecimentos: list[Abastecimento],
    candidatos: list[CandidatoGP],
) -> list[CandidatoGP]:
    """Reduz a lista enviada ao modelo para os candidatos minimamente plausiveis.

    Heuristica: para cada abastecimento, mantem candidatos cujo identificador
    normalizado partilha pelo menos 2 caracteres iniciais OU cujo equipamento/
    modelo/marca aparece (substring) no apelido. Sempre retorna no maximo 60
    candidatos para a chamada (top-pelos-criterios).
    """
    selecionados: dict[int, CandidatoGP] = {}
    for ab in abastecimentos:
        v = _norm(ab.veiculo_raw)
        ap = _norm(ab.apelido)
        for c in candidatos:
            if c.id in selecionados:
                continue
            placa = c.placa_ativo_normalizada
            equip = _norm(c.equipamento)
            modelo = _norm(c.modelo)
            marca = _norm(c.marca)
            ok = False
            if placa and (placa == v or placa[:2] == v[:2] or placa in v or v in placa):
                ok = True
            elif ap and equip and equip in ap:
                ok = True
            elif ap and modelo and modelo in ap:
                ok = True
            elif ap and marca and marca in ap:
                ok = True
            if ok:
                selecionados[c.id] = c
    if not selecionados:
        # fallback: limita a 60 do total para nao mandar lista vazia
        return candidatos[:60]
    return list(selecionados.values())[:60]


def _extrair_sugestoes(response: Any) -> list[_SugestaoLLM]:
    """Extrai e valida o tool call `registrar_sugestoes`. Tolerante a falhas."""
    if not response.tool_calls:
        # Alguns providers podem responder em content JSON; tenta parse direto.
        return _try_parse_content_json(response.content)
    for tc in response.tool_calls:
        if tc.name != "registrar_sugestoes":
            continue
        try:
            payload = json.loads(tc.arguments_json or "{}")
            return _SugestoesLLM.model_validate(payload).sugestoes
        except (json.JSONDecodeError, ValidationError) as exc:
            log.warning(
                "reconciliador.tool_parse_failed",
                error=str(exc),
                args=tc.arguments_json[:200],
            )
    return []


def _try_parse_content_json(content: str) -> list[_SugestaoLLM]:
    if not content:
        return []
    try:
        payload = json.loads(content)
        if isinstance(payload, dict) and "sugestoes" in payload:
            return _SugestoesLLM.model_validate(payload).sugestoes
    except (json.JSONDecodeError, ValidationError):
        return []
    return []


def _sugestao_to_dict(s: SugestaoReconciliacao) -> dict[str, Any]:
    return {
        "abastecimento_id": s.abastecimento_id,
        "veiculo_infleet": s.veiculo_infleet,
        "apelido_infleet": s.apelido_infleet,
        "candidato_gp": s.candidato_gp,
        "confianca": s.confianca,
        "justificativa": s.justificativa,
    }


def _sugestoes_from_cached(payload: dict[str, Any]) -> list[SugestaoReconciliacao]:
    items = payload.get("sugestoes") or []
    out: list[SugestaoReconciliacao] = []
    for it in items:
        out.append(
            SugestaoReconciliacao(
                abastecimento_id=int(it.get("abastecimento_id") or 0),
                veiculo_infleet=str(it.get("veiculo_infleet") or ""),
                apelido_infleet=it.get("apelido_infleet"),
                candidato_gp=it.get("candidato_gp"),
                confianca=float(it.get("confianca") or 0.0),
                justificativa=str(it.get("justificativa") or ""),
            )
        )
    return out
