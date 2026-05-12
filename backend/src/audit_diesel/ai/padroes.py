"""Analise proativa de padroes cross-NF (Feature C da v2).

Pipeline:
1. `coletar_candidatos(session)` roda 7 heuristicas estatisticas puras em
   Python sobre os dados ja persistidos (abastecimentos, auditorias,
   alertas, cadastro). Cada heuristica devolve `list[CandidatoPadrao]`
   com dados CONCRETOS (numeros, ids, evidencias). Se nao houver
   evidencia real, devolve lista vazia.
2. `analisar_padroes(session, chat)` envia os candidatos ao LLM, que
   seleciona/narra os 3-5 mais relevantes. A resposta passa por
   validacao pydantic com guardrail: padroes cujo `evidencia_ids` nao
   esta na lista de ids de candidatos sao DESCARTADOS (impede o modelo
   de inventar agregacoes).
3. Persiste em `PadraoDetectado` (apaga padroes antigos antes).

A camada respeita modo offline (AUDIT_AI_OFFLINE=1): nesse caso, em vez
de chamar o LLM, escolhe ate 5 candidatos por severidade e produz um
titulo/descricao deterministicos a partir dos proprios campos.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import structlog
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlmodel import Session, select

from audit_diesel.models import (
    Abastecimento,
    Alerta,
    Auditoria,
    Mobilizado,
    PadraoDetectado,
)

from .client import ChatClient, ChatMessage
from .prompts import padroes as prompts

log = structlog.get_logger("audit_diesel.ai.padroes")

# Janela atipica: abastecimentos fora do horario operacional padrao.
HORARIO_ATIPICO_INICIO = 22  # 22:00
HORARIO_ATIPICO_FIM = 5      # 05:00

# Limite para "aumento de consumo" semana atual vs baseline 4 semanas.
AUMENTO_CONSUMO_LIMITE = 0.50  # +50%

# Limite para "diferenca relevante entre NFs sequenciais".
DIF_PCT_NF_LIMITE = 0.05  # 5%

# Minimo de NFs distintas para considerar "nao cadastrado recorrente".
MIN_NFS_NAO_CADASTRADO_RECORRENTE = 3

# Maximo de padroes finais retornados ao auditor.
MAX_PADROES = 5


# ---------------------------------------------------------------------------
# Tipos internos
# ---------------------------------------------------------------------------


@dataclass
class CandidatoPadrao:
    """Padrao candidato com evidencia bruta antes da selecao do LLM."""

    tipo: str
    titulo_curto: str
    descricao_curta: str
    severidade_sugerida: str  # alta | media | baixa
    evidencia_ids: list[int] = field(default_factory=list)
    dados: dict[str, Any] = field(default_factory=dict)

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "tipo": self.tipo,
            "titulo_curto": self.titulo_curto,
            "descricao_curta": self.descricao_curta,
            "severidade_sugerida": self.severidade_sugerida,
            "evidencia_ids": list(self.evidencia_ids),
            "dados": self.dados,
        }


class _PadraoLLM(BaseModel):
    """Saida validada de cada padrao retornado pelo LLM."""

    tipo: str = Field(min_length=1, max_length=80)
    titulo: str = Field(min_length=1, max_length=80)
    descricao: str = Field(min_length=1, max_length=320)
    severidade: str
    evidencia_ids: list[int] = Field(default_factory=list)

    @field_validator("severidade")
    @classmethod
    def _sev(cls, v: str) -> str:
        v_low = v.lower().strip()
        if v_low not in {"alta", "media", "baixa"}:
            raise ValueError("severidade deve ser alta|media|baixa")
        return v_low


class _RespostaLLM(BaseModel):
    padroes: list[_PadraoLLM]


# ---------------------------------------------------------------------------
# Coleta de candidatos (7 heuristicas Python puras)
# ---------------------------------------------------------------------------


def coletar_candidatos(session: Session) -> list[CandidatoPadrao]:
    """Roda todas as heuristicas e retorna candidatos com evidencia."""
    candidatos: list[CandidatoPadrao] = []
    candidatos.extend(_nao_cadastrados_agregado(session))
    candidatos.extend(_aumento_consumo_por_veiculo(session))
    candidatos.extend(_horario_atipico(session))
    candidatos.extend(_nao_cadastrados_recorrentes(session))
    candidatos.extend(_nfs_sequenciais_diferenca_alta(session))
    candidatos.extend(_desmobilizados_ativos_agregado(session))
    candidatos.extend(_desmobilizados_ativos(session))
    candidatos.extend(_inconsistencias_infleet_agregado(session))
    candidatos.extend(_inconsistencias_infleet_frequentes(session))
    candidatos.extend(_concentracao_janela_horaria(session))
    return candidatos


def _nao_cadastrados_agregado(session: Session) -> list[CandidatoPadrao]:
    """Volume total de alertas de abastecimentos sem cadastro GP."""
    alertas = list(session.exec(
        select(Alerta).where(Alerta.tipo == "NAO_CADASTRADO")
    ).all())
    if not alertas:
        return []

    total_litros = 0.0
    total_custo = 0.0
    por_placa: Counter[str] = Counter()
    abastecimento_ids: list[int] = []
    for alerta in alertas:
        try:
            payload = json.loads(alerta.payload_json) if alerta.payload_json else {}
        except json.JSONDecodeError:
            payload = {}
        placa = str(
            payload.get("veiculo_normalizado")
            or payload.get("veiculo")
            or payload.get("placa")
            or ""
        ).strip()
        if placa:
            por_placa[placa] += 1
        total_litros += float(payload.get("quantidade_litros") or 0.0)
        total_custo += float(alerta.impacto_financeiro or payload.get("custo_total") or 0.0)
        if alerta.abastecimento_id is not None:
            abastecimento_ids.append(alerta.abastecimento_id)

    if len(alertas) < 3:
        return []

    top_placas = por_placa.most_common(5)
    nomes = ", ".join(f"{placa} ({n})" for placa, n in top_placas[:3])
    return [CandidatoPadrao(
        tipo="nao_cadastrado_agregado",
        titulo_curto="Abastecimentos sem cadastro GP concentrados",
        descricao_curta=(
            f"{len(alertas)} alerta(s) de equipamento sem cadastro no GP, "
            f"somando {_format_int_br(total_litros)}L e {_format_brl(total_custo)}. "
            f"Placas mais recorrentes: {nomes}."
        ),
        severidade_sugerida="alta",
        evidencia_ids=abastecimento_ids[:80],
        dados={
            "total_alertas": len(alertas),
            "total_litros": round(total_litros, 1),
            "impacto_financeiro": round(total_custo, 2),
            "top_placas": [{"placa": placa, "n": n} for placa, n in top_placas],
            "abastecimento_ids": abastecimento_ids[:80],
        },
    )]


def _aumento_consumo_por_veiculo(session: Session) -> list[CandidatoPadrao]:
    """Aumento de consumo > 50% comparando a semana mais recente com baseline."""
    abas = list(session.exec(select(Abastecimento)).all())
    if not abas:
        return []
    fim = max(a.data for a in abas)
    janela_recente = fim - timedelta(days=7)
    janela_baseline_inicio = fim - timedelta(days=35)
    janela_baseline_fim = fim - timedelta(days=7)

    consumo_recente: dict[str, float] = defaultdict(float)
    consumo_baseline: dict[str, float] = defaultdict(float)
    ids_recente: dict[str, list[int]] = defaultdict(list)
    for a in abas:
        if a.data >= janela_recente:
            consumo_recente[a.veiculo_normalizado] += float(a.quantidade_litros)
            if a.id is not None:
                ids_recente[a.veiculo_normalizado].append(a.id)
        elif janela_baseline_inicio <= a.data < janela_baseline_fim:
            consumo_baseline[a.veiculo_normalizado] += float(a.quantidade_litros)

    resultados: list[CandidatoPadrao] = []
    for veiculo, recente in consumo_recente.items():
        baseline_total = consumo_baseline.get(veiculo, 0.0)
        # Baseline media semanal = baseline_total / 4 semanas
        baseline_semanal = baseline_total / 4.0 if baseline_total else 0.0
        if baseline_semanal < 50.0:
            # Veiculos com baseline muito baixo geram ruido (frota grande, uso esporadico).
            continue
        delta = (recente - baseline_semanal) / baseline_semanal
        if delta >= AUMENTO_CONSUMO_LIMITE:
            resultados.append(CandidatoPadrao(
                tipo="aumento_consumo",
                titulo_curto=f"Aumento de consumo no veículo {veiculo}",
                descricao_curta=(
                    f"Consumo da última semana ({recente:.0f}L) está "
                    f"{delta*100:.0f}% acima do baseline semanal "
                    f"({baseline_semanal:.0f}L)."
                ),
                severidade_sugerida="alta" if delta >= 1.0 else "media",
                evidencia_ids=ids_recente[veiculo][:50],
                dados={
                    "veiculo": veiculo,
                    "litros_semana_atual": round(recente, 1),
                    "litros_baseline_semanal": round(baseline_semanal, 1),
                    "delta_pct": round(delta * 100, 1),
                },
            ))
    return resultados


def _horario_atipico(session: Session) -> list[CandidatoPadrao]:
    """Abastecimentos fora do horario operacional padrao (22h-5h)."""
    abas = list(session.exec(select(Abastecimento)).all())
    if not abas:
        return []
    atipicos: list[Abastecimento] = []
    for a in abas:
        h = a.data.hour
        if h >= HORARIO_ATIPICO_INICIO or h < HORARIO_ATIPICO_FIM:
            atipicos.append(a)
    if not atipicos:
        return []
    por_veiculo: dict[str, list[Abastecimento]] = defaultdict(list)
    for a in atipicos:
        por_veiculo[a.veiculo_normalizado].append(a)
    resultados: list[CandidatoPadrao] = []
    # Padrao agregado, nao por veiculo: chamar atencao se o total for relevante.
    total_atipicos = len(atipicos)
    total_geral = len(abas)
    pct = total_atipicos / total_geral if total_geral else 0.0
    if total_atipicos >= 3:
        top_veiculos = sorted(por_veiculo.items(), key=lambda kv: -len(kv[1]))[:3]
        nomes = ", ".join(f"{placa} ({len(itens)})" for placa, itens in top_veiculos)
        ids = [a.id for a in atipicos if a.id is not None][:80]
        resultados.append(CandidatoPadrao(
            tipo="horario_atipico",
            titulo_curto="Abastecimentos em horário atípico",
            descricao_curta=(
                f"{total_atipicos} abastecimento(s) registrado(s) entre 22h e "
                f"5h ({pct*100:.1f}% do total). Veículos com maior ocorrência: "
                f"{nomes}."
            ),
            severidade_sugerida="media" if pct < 0.10 else "alta",
            evidencia_ids=ids,
            dados={
                "total_atipicos": total_atipicos,
                "total_geral": total_geral,
                "pct": round(pct * 100, 2),
                "top_veiculos": [{"placa": placa, "n": len(itens)} for placa, itens in top_veiculos],
            },
        ))
    return resultados


def _nao_cadastrados_recorrentes(session: Session) -> list[CandidatoPadrao]:
    """Placas que aparecem como NAO_CADASTRADO em >= 3 auditorias distintas."""
    alertas = list(session.exec(
        select(Alerta).where(Alerta.tipo == "NAO_CADASTRADO")
    ).all())
    if not alertas:
        return []
    # Conta auditorias distintas por placa (via payload_json)
    placas_por_auditoria: dict[str, set[int]] = defaultdict(set)
    for al in alertas:
        try:
            payload = json.loads(al.payload_json) if al.payload_json else {}
        except json.JSONDecodeError:
            payload = {}
        placa = str(payload.get("veiculo") or payload.get("placa") or "").strip()
        if placa:
            placas_por_auditoria[placa].add(al.auditoria_id)
    resultados: list[CandidatoPadrao] = []
    for placa, audits in placas_por_auditoria.items():
        if len(audits) >= MIN_NFS_NAO_CADASTRADO_RECORRENTE:
            resultados.append(CandidatoPadrao(
                tipo="nao_cadastrado_recorrente",
                titulo_curto=f"Placa {placa} sem cadastro em múltiplas NFs",
                descricao_curta=(
                    f"A placa {placa} aparece como não cadastrada em "
                    f"{len(audits)} auditoria(s) distinta(s). Indica ausência "
                    f"real de cadastro no GP ou divergência de formatação."
                ),
                severidade_sugerida="alta" if len(audits) >= 5 else "media",
                evidencia_ids=sorted(audits),
                dados={
                    "placa": placa,
                    "n_auditorias": len(audits),
                },
            ))
    return resultados


def _nfs_sequenciais_diferenca_alta(session: Session) -> list[CandidatoPadrao]:
    """Auditorias com diferenca % > 5% (alem do limite de aprovacao de 2%)."""
    audits = list(session.exec(
        select(Auditoria).order_by(Auditoria.criada_em.desc())
    ).all())
    if not audits:
        return []
    relevantes = [
        a for a in audits
        if a.id is not None and abs(float(a.diferenca_percentual or 0.0)) > DIF_PCT_NF_LIMITE
    ]
    if not relevantes:
        return []
    # Emite UM candidato agregado por obra, com top-3 maiores diferencas.
    por_obra: dict[str, list[Auditoria]] = defaultdict(list)
    for a in relevantes:
        por_obra[a.nome_obra].append(a)
    resultados: list[CandidatoPadrao] = []
    for obra, lista in por_obra.items():
        top = sorted(lista, key=lambda x: -abs(float(x.diferenca_percentual or 0.0)))[:3]
        nfs = ", ".join(f"NF {t.nf_atual} ({float(t.diferenca_percentual)*100:+.1f}%)" for t in top)
        resultados.append(CandidatoPadrao(
            tipo="diferenca_saidas_alta",
            titulo_curto=f"Diferença de saídas elevada em {obra}",
            descricao_curta=(
                f"{len(lista)} auditoria(s) com diferença de saídas acima de "
                f"{DIF_PCT_NF_LIMITE*100:.0f}% nesta obra. Maiores: {nfs}."
            ),
            severidade_sugerida="alta" if len(lista) >= 3 else "media",
            evidencia_ids=[a.id for a in top if a.id is not None],
            dados={
                "obra": obra,
                "n_relevantes": len(lista),
                "top_diferencas": [
                    {
                        "auditoria_id": t.id,
                        "nf_atual": t.nf_atual,
                        "dif_pct": round(float(t.diferenca_percentual or 0.0) * 100, 2),
                    }
                    for t in top
                ],
            },
        ))
    return resultados


def _desmobilizados_ativos(session: Session) -> list[CandidatoPadrao]:
    """Abastecimentos posteriores a data_desmobilizacao do mobilizado correspondente."""
    mobs = list(session.exec(select(Mobilizado)).all())
    desmob_idx: dict[str, datetime] = {}
    for m in mobs:
        if m.data_desmobilizacao and m.placa_ativo_normalizada:
            existente = desmob_idx.get(m.placa_ativo_normalizada)
            if not existente or m.data_desmobilizacao > existente:
                desmob_idx[m.placa_ativo_normalizada] = m.data_desmobilizacao
    if not desmob_idx:
        return []
    abas = list(session.exec(select(Abastecimento)).all())
    pos_desmob: dict[str, list[Abastecimento]] = defaultdict(list)
    for a in abas:
        dt = desmob_idx.get(a.veiculo_normalizado)
        if dt and a.data > dt:
            pos_desmob[a.veiculo_normalizado].append(a)
    resultados: list[CandidatoPadrao] = []
    for placa, lista in pos_desmob.items():
        if len(lista) < 2:
            continue
        total_litros = sum(float(a.quantidade_litros) for a in lista)
        ids = [a.id for a in lista if a.id is not None][:50]
        resultados.append(CandidatoPadrao(
            tipo="desmobilizado_ativo",
            titulo_curto=f"Veículo desmobilizado {placa} segue abastecendo",
            descricao_curta=(
                f"{len(lista)} abastecimento(s) totalizando {total_litros:.0f}L "
                f"registrados para a placa {placa} após sua data de "
                f"desmobilização no GP."
            ),
            severidade_sugerida="alta",
            evidencia_ids=ids,
            dados={
                "placa": placa,
                "n_abastecimentos": len(lista),
                "total_litros": round(total_litros, 1),
            },
        ))
    return resultados


def _desmobilizados_ativos_agregado(session: Session) -> list[CandidatoPadrao]:
    """Resumo global de equipamentos desmobilizados que continuam abastecendo."""
    mobs = list(session.exec(select(Mobilizado)).all())
    desmob_idx: dict[str, datetime] = {}
    for m in mobs:
        if m.data_desmobilizacao and m.placa_ativo_normalizada:
            existente = desmob_idx.get(m.placa_ativo_normalizada)
            if not existente or m.data_desmobilizacao > existente:
                desmob_idx[m.placa_ativo_normalizada] = m.data_desmobilizacao
    if not desmob_idx:
        return []

    pos_desmob: dict[str, list[Abastecimento]] = defaultdict(list)
    for a in session.exec(select(Abastecimento)).all():
        dt = desmob_idx.get(a.veiculo_normalizado)
        if dt and a.data > dt:
            pos_desmob[a.veiculo_normalizado].append(a)
    placas_relevantes = {placa: itens for placa, itens in pos_desmob.items() if itens}
    if not placas_relevantes:
        return []

    total_abastecimentos = sum(len(itens) for itens in placas_relevantes.values())
    total_litros = sum(
        float(a.quantidade_litros)
        for itens in placas_relevantes.values()
        for a in itens
    )
    ids = [
        a.id
        for itens in placas_relevantes.values()
        for a in itens
        if a.id is not None
    ]
    top_placas = sorted(
        (
            (placa, len(itens), sum(float(a.quantidade_litros) for a in itens))
            for placa, itens in placas_relevantes.items()
        ),
        key=lambda item: -item[2],
    )[:5]
    nomes = ", ".join(f"{placa} ({litros:.0f}L)" for placa, _, litros in top_placas[:3])
    return [CandidatoPadrao(
        tipo="desmobilizado_ativo_agregado",
        titulo_curto="Frota desmobilizada ainda abastece",
        descricao_curta=(
            f"{len(placas_relevantes)} placa(s) desmobilizada(s) seguem com "
            f"{total_abastecimentos} abastecimento(s), totalizando {_format_int_br(total_litros)}L. "
            f"Maiores volumes: {nomes}."
        ),
        severidade_sugerida="alta",
        evidencia_ids=ids[:80],
        dados={
            "n_placas": len(placas_relevantes),
            "n_abastecimentos": total_abastecimentos,
            "total_litros": round(total_litros, 1),
            "top_placas": [
                {"placa": placa, "n": n, "litros": round(litros, 1)}
                for placa, n, litros in top_placas
            ],
            "abastecimento_ids": ids[:80],
        },
    )]


def _inconsistencias_infleet_agregado(session: Session) -> list[CandidatoPadrao]:
    """Resumo global de flags de inconsistência vindas da telemetria Infleet."""
    abas = list(session.exec(
        select(Abastecimento).where(Abastecimento.inconsistencias_infleet.is_not(None))  # type: ignore[union-attr]
    ).all())
    if len(abas) < 3:
        return []

    por_veiculo: Counter[str] = Counter(a.veiculo_normalizado for a in abas)
    top_veiculos = por_veiculo.most_common(5)
    nomes = ", ".join(f"{placa} ({n})" for placa, n in top_veiculos[:3])
    ids = [a.id for a in abas if a.id is not None]
    return [CandidatoPadrao(
        tipo="inconsistencias_infleet_agregado",
        titulo_curto="Flags Infleet recorrentes",
        descricao_curta=(
            f"{len(abas)} abastecimento(s) em {len(por_veiculo)} veículo(s) "
            f"vieram com inconsistência da telemetria Infleet. "
            f"Maiores recorrências: {nomes}."
        ),
        severidade_sugerida="media",
        evidencia_ids=ids[:80],
        dados={
            "total_flags": len(abas),
            "n_veiculos": len(por_veiculo),
            "top_veiculos": [{"placa": placa, "n": n} for placa, n in top_veiculos],
            "abastecimento_ids": ids[:80],
        },
    )]


def _format_int_br(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def _format_brl(value: float) -> str:
    txt = f"{value:,.2f}"
    txt = txt.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {txt}"


def _inconsistencias_infleet_frequentes(session: Session) -> list[CandidatoPadrao]:
    """Veiculos cujos abastecimentos vem com `inconsistencias_infleet` preenchido."""
    abas = list(session.exec(
        select(Abastecimento).where(Abastecimento.inconsistencias_infleet.is_not(None))  # type: ignore[union-attr]
    ).all())
    if not abas:
        return []
    por_veiculo: Counter[str] = Counter()
    ids_por_veiculo: dict[str, list[int]] = defaultdict(list)
    for a in abas:
        por_veiculo[a.veiculo_normalizado] += 1
        if a.id is not None:
            ids_por_veiculo[a.veiculo_normalizado].append(a.id)
    resultados: list[CandidatoPadrao] = []
    for veiculo, n in por_veiculo.most_common(5):
        if n < 3:
            continue
        resultados.append(CandidatoPadrao(
            tipo="inconsistencias_infleet",
            titulo_curto=f"Inconsistências recorrentes no veículo {veiculo}",
            descricao_curta=(
                f"{n} abastecimento(s) do veículo {veiculo} foram registrados "
                f"com flag de inconsistência pela telemetria Infleet."
            ),
            severidade_sugerida="media",
            evidencia_ids=ids_por_veiculo[veiculo][:50],
            dados={"veiculo": veiculo, "n": n},
        ))
    return resultados


def _concentracao_janela_horaria(session: Session) -> list[CandidatoPadrao]:
    """Veiculos com >= 60% dos abastecimentos concentrados em uma faixa de 3 horas."""
    abas = list(session.exec(select(Abastecimento)).all())
    if not abas:
        return []
    por_veiculo: dict[str, list[Abastecimento]] = defaultdict(list)
    for a in abas:
        por_veiculo[a.veiculo_normalizado].append(a)
    resultados: list[CandidatoPadrao] = []
    for veiculo, lista in por_veiculo.items():
        if len(lista) < 10:
            continue  # poucos pontos, nao da pra inferir
        horas = Counter(a.data.hour for a in lista)
        # Procura janela contigua de 3 horas com pico de concentracao.
        melhor_inicio = 0
        melhor_total = 0
        for h in range(24):
            soma = horas.get(h, 0) + horas.get((h + 1) % 24, 0) + horas.get((h + 2) % 24, 0)
            if soma > melhor_total:
                melhor_total = soma
                melhor_inicio = h
        pct = melhor_total / len(lista)
        if pct >= 0.60:
            ids = [a.id for a in lista if a.id is not None][:50]
            resultados.append(CandidatoPadrao(
                tipo="concentracao_horaria",
                titulo_curto=f"Concentração horária no veículo {veiculo}",
                descricao_curta=(
                    f"{melhor_total} de {len(lista)} abastecimentos do veículo "
                    f"{veiculo} ({pct*100:.0f}%) ocorreram entre "
                    f"{melhor_inicio:02d}h e {(melhor_inicio + 3) % 24:02d}h."
                ),
                severidade_sugerida="baixa",
                evidencia_ids=ids,
                dados={
                    "veiculo": veiculo,
                    "janela_inicio_h": melhor_inicio,
                    "pct_na_janela": round(pct * 100, 1),
                    "total": len(lista),
                },
            ))
    return resultados


# ---------------------------------------------------------------------------
# Orquestrador: candidatos -> LLM -> persistencia
# ---------------------------------------------------------------------------


@dataclass
class ResultadoAnalisePadroes:
    """Saida da analise: padroes persistidos + meta."""

    padroes: list[PadraoDetectado]
    n_candidatos: int
    provider: str
    modelo: str | None
    offline: bool


def gerar_padroes_em_memoria(session: Session) -> list[PadraoDetectado]:
    """Gera um snapshot deterministico para exibicao sem persistir no banco."""
    selecionados = _selecionar_offline(coletar_candidatos(session))
    agora = datetime.now()
    return [
        PadraoDetectado(
            id=-(idx + 1),
            tipo=p["tipo"],
            titulo=p["titulo"],
            descricao=p["descricao"],
            severidade=p["severidade"],
            dados_json=json.dumps(p.get("dados", {}), ensure_ascii=False, default=str),
            criado_em=agora,
        )
        for idx, p in enumerate(selecionados[:MAX_PADROES])
    ]


def analisar_padroes(
    session: Session,
    chat: ChatClient | None = None,
) -> ResultadoAnalisePadroes:
    """Coleta candidatos, narra via LLM e persiste 0-5 padroes."""
    chat = chat or ChatClient()
    candidatos = coletar_candidatos(session)
    log.info("padroes.candidatos_coletados", n=len(candidatos))

    # Apaga padroes antigos antes de gravar a nova lista (snapshot atual).
    for antigo in session.exec(select(PadraoDetectado)).all():
        session.delete(antigo)
    session.commit()

    if not candidatos:
        log.info("padroes.sem_candidatos")
        return ResultadoAnalisePadroes(
            padroes=[],
            n_candidatos=0,
            provider=chat.provider.info.name,
            modelo=chat.provider.info.model,
            offline=chat.provider.info.offline,
        )

    if chat.provider.info.offline:
        selecionados = _selecionar_offline(candidatos)
    else:
        try:
            selecionados = _selecionar_via_llm(chat, candidatos)
            if not _quota_satisfeita(selecionados, candidatos):
                log.info("padroes.llm_sem_quota_usando_fallback")
                selecionados = _selecionar_offline(candidatos)
        except (ValidationError, json.JSONDecodeError, RuntimeError) as exc:
            log.warning("padroes.llm_falhou_usando_fallback", error=str(exc))
            selecionados = _selecionar_offline(candidatos)

    persistidos: list[PadraoDetectado] = []
    agora = datetime.now()
    for p in selecionados[:MAX_PADROES]:
        registro = PadraoDetectado(
            tipo=p["tipo"],
            titulo=p["titulo"],
            descricao=p["descricao"],
            severidade=p["severidade"],
            dados_json=json.dumps(p.get("dados", {}), ensure_ascii=False, default=str),
            criado_em=agora,
        )
        session.add(registro)
        persistidos.append(registro)
    session.commit()
    for r in persistidos:
        session.refresh(r)

    return ResultadoAnalisePadroes(
        padroes=persistidos,
        n_candidatos=len(candidatos),
        provider=chat.provider.info.name,
        modelo=chat.provider.info.model,
        offline=chat.provider.info.offline,
    )


def _selecionar_via_llm(
    chat: ChatClient,
    candidatos: list[CandidatoPadrao],
) -> list[dict[str, Any]]:
    """Chama o LLM com response_format=json_object e valida a saida."""
    response = chat.chat(
        messages=[
            ChatMessage(role="system", content=prompts.SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=prompts.montar_user_message([c.to_prompt_dict() for c in candidatos]),
            ),
        ],
        temperature=0.2,
        max_tokens=2000,
    )
    parsed = _RespostaLLM.model_validate_json(_extrair_json(response.content))
    # Guardrail: descarta padroes cujo tipo ou evidencia_ids nao existem
    # entre os candidatos (impede o LLM de inventar).
    tipos_validos = {c.tipo for c in candidatos}
    ids_por_tipo: dict[str, set[int]] = {
        c.tipo: set(c.evidencia_ids) for c in candidatos
    }
    selecionados: list[dict[str, Any]] = []
    for p in parsed.padroes:
        if p.tipo not in tipos_validos:
            log.warning("padroes.guardrail_tipo_invalido", tipo=p.tipo)
            continue
        ids_ok = ids_por_tipo.get(p.tipo, set())
        evidencias = [i for i in p.evidencia_ids if i in ids_ok]
        if not evidencias and p.evidencia_ids:
            log.warning("padroes.guardrail_evidencia_invalida", tipo=p.tipo)
            continue
        dados_orig = next(
            (c.dados for c in candidatos if c.tipo == p.tipo and (
                not p.evidencia_ids or set(p.evidencia_ids) & set(c.evidencia_ids)
            )),
            {},
        )
        selecionados.append({
            "tipo": p.tipo,
            "titulo": p.titulo.strip(),
            "descricao": p.descricao.strip(),
            "severidade": p.severidade,
            "dados": {**dados_orig, "evidencia_ids": evidencias},
        })
    return selecionados


def _quota_satisfeita(
    selecionados: list[dict[str, Any]],
    candidatos: list[CandidatoPadrao],
) -> bool:
    """Confere se o LLM respeitou a quota possivel de 3 altas e 2 medias."""
    alvo_alta = min(3, sum(1 for c in candidatos if c.severidade_sugerida == "alta"))
    alvo_media = min(2, sum(1 for c in candidatos if c.severidade_sugerida == "media"))
    if len(selecionados) < min(MAX_PADROES, len(candidatos)):
        return False
    n_alta = sum(1 for p in selecionados[:MAX_PADROES] if p.get("severidade") == "alta")
    n_media = sum(1 for p in selecionados[:MAX_PADROES] if p.get("severidade") == "media")
    return n_alta >= alvo_alta and n_media >= alvo_media


def _selecionar_offline(candidatos: list[CandidatoPadrao]) -> list[dict[str, Any]]:
    """Fallback deterministico: prioriza quota, diversidade e evidencia real."""
    selecionados = _selecionar_candidatos_por_quota(candidatos)
    return [
        {
            "tipo": c.tipo,
            "titulo": c.titulo_curto,
            "descricao": c.descricao_curta,
            "severidade": c.severidade_sugerida,
            "dados": {**c.dados, "evidencia_ids": list(c.evidencia_ids)},
        }
        for c in selecionados
    ]


def _selecionar_candidatos_por_quota(
    candidatos: list[CandidatoPadrao],
) -> list[CandidatoPadrao]:
    """Escolhe ate 5 candidatos preferindo 3 altas e 2 medias, sem repetir tipo."""
    ordenados = sorted(candidatos, key=_chave_candidato)
    selecionados: list[CandidatoPadrao] = []
    usados: set[str] = set()

    def adicionar(severidade: str | None, limite: int, permitir_repetir: bool = False) -> None:
        for candidato in ordenados:
            if len(selecionados) >= MAX_PADROES or limite <= 0:
                return
            if candidato in selecionados:
                continue
            if severidade is not None and candidato.severidade_sugerida != severidade:
                continue
            if not permitir_repetir and candidato.tipo in usados:
                continue
            selecionados.append(candidato)
            usados.add(candidato.tipo)
            limite -= 1

    adicionar("alta", 3)
    adicionar("media", 2)
    adicionar(None, MAX_PADROES - len(selecionados))
    adicionar(None, MAX_PADROES - len(selecionados), permitir_repetir=True)
    return selecionados[:MAX_PADROES]


def _chave_candidato(c: CandidatoPadrao) -> tuple[int, int, float, str]:
    severidade_ordem = {"alta": 0, "media": 1, "baixa": 2}
    tipo_ordem = {
        "nao_cadastrado_agregado": 0,
        "desmobilizado_ativo_agregado": 1,
        "aumento_consumo": 2,
        "horario_atipico": 3,
        "inconsistencias_infleet_agregado": 4,
        "inconsistencias_infleet": 5,
        "desmobilizado_ativo": 6,
        "nao_cadastrado_recorrente": 7,
        "diferenca_saidas_alta": 8,
        "concentracao_horaria": 9,
    }
    return (
        severidade_ordem.get(c.severidade_sugerida, 9),
        tipo_ordem.get(c.tipo, 99),
        -_score_candidato(c),
        c.titulo_curto,
    )


def _score_candidato(c: CandidatoPadrao) -> float:
    dados = c.dados
    for key in (
        "impacto_financeiro",
        "total_litros",
        "delta_pct",
        "total_flags",
        "total_atipicos",
        "n_abastecimentos",
        "n",
        "total",
    ):
        value = dados.get(key)
        if isinstance(value, int | float):
            return float(value)
    return float(len(c.evidencia_ids))


def _extrair_json(content: str) -> str:
    """Remove cercas de codigo (```json ... ```) caso o LLM as inclua."""
    txt = content.strip()
    if txt.startswith("```"):
        # remove primeira linha (```json) e ultimas tres backticks
        partes = txt.split("\n", 1)
        if len(partes) == 2:
            txt = partes[1]
        if txt.rstrip().endswith("```"):
            txt = txt.rstrip()[: -3].rstrip()
    return txt
