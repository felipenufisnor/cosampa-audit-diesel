"""Pydantic schemas (request/response) da API. Sao espelhados em frontend/types.ts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealthzResponse(BaseModel):
    """GET /healthz."""

    status: str
    db: str
    ai: str
    provider: str
    model: str
    fallback_model: str | None
    offline: bool
    demo_mode: bool
    assistant_status: Literal[
        "available",
        "degraded_cache",
        "offline_fixture",
        "missing_key",
        "provider_error",
    ] = "offline_fixture"
    assistant_reason: str = ""
    assistant_can_answer_free_text: bool = False
    assistant_has_cached_answers: bool = False


class StatsResponse(BaseModel):
    """GET /stats."""

    total_abastecimentos: int
    total_litros: float
    total_custo_brl: float
    periodo_inicio: date | None
    periodo_fim: date | None
    periodo_nfs_inicio: date | None
    periodo_nfs_fim: date | None
    total_nfs: int
    total_mobilizados: int
    mobilizados_ativos: int
    veiculos_distintos_infleet: int
    abastecimentos_nao_cadastrados: int
    custo_nao_cadastrado_brl: float
    pct_custo_nao_cadastrado: float
    nfs_auditadas: int = 0
    nfs_aprovadas: int = 0
    nfs_inconsistentes: int = 0
    nfs_nao_auditadas: int = 0


class NFListItem(BaseModel):
    """Item da listagem GET /nfs."""

    nota_fiscal: str
    data_recebimento: date
    nome_obra: str
    valor_total: float
    qtd_litros: float
    ultima_auditoria_id: int | None
    ultima_validacao: str | None
    qtd_auditorias: int = 0


class NFDetail(BaseModel):
    """Resposta de GET /nfs/{nota_fiscal}."""

    nota_fiscal: str
    numero_chamado: str
    data_recebimento: date
    hora_inicio_descarga: str
    hora_final_descarga: str
    nome_obra: str
    cnpj_fornecedor: str
    quantidade_nf_litros: float
    volume_conferido_litros: float
    estoque_antes_tanque_litros: float
    estoque_antes_comboio_litros: float
    preco_unitario: float
    valor_total_nf: float
    auditorias_passadas: list[AuditoriaResumo] = Field(default_factory=list)


class AuditoriaResumo(BaseModel):
    """Resumo curto de uma auditoria (usado em listagens / historico)."""

    id: int
    nf_anterior: str
    nf_atual: str
    nome_obra: str
    criada_em: datetime
    validacao_final: str
    diferenca_percentual: float
    versao: int = 1
    total_versoes: int = 1
    is_atual: bool = True
    auditoria_atual_id: int | None = None


class PontoCorteManualRequest(BaseModel):
    """Fronteira inferior da janela quando nao ha NF anterior disponivel.

    O auditor define manualmente data/hora do corte e os estoques iniciais
    de tanque e comboio nesse instante. Usado tipicamente para auditar a
    primeira NF do conjunto. Ver achado AI-06.
    """

    data_inicio: datetime
    estoque_tanque_inicial_litros: float = Field(ge=0)
    estoque_comboio_inicial_litros: float = Field(ge=0)
    motivo: str = Field(min_length=1, max_length=500)


class CriarAuditoriaRequest(BaseModel):
    """POST /auditorias body.

    Exatamente um entre `nf_anterior` e `ponto_corte` deve ser fornecido.
    """

    nf_anterior: str | None = None
    ponto_corte: PontoCorteManualRequest | None = None
    nf_atual: str
    gerar_parecer: bool = True
    # Modo de criacao:
    #  - "nova_versao" (default): cria sempre uma nova auditoria; o historico
    #    cresce e a UI mostra apenas a mais recente como "atual".
    #  - "sobrescrever_ultima": apaga a auditoria mais recente da mesma
    #    nf_atual (e seus alertas) antes de criar a nova. Util para o auditor
    #    refazer um teste sem poluir o historico.
    modo: str = "nova_versao"

    @model_validator(mode="after")
    def _validar_origem_anterior(self) -> "CriarAuditoriaRequest":
        tem_nf = self.nf_anterior is not None and self.nf_anterior.strip() != ""
        tem_corte = self.ponto_corte is not None
        if tem_nf == tem_corte:
            raise ValueError(
                "Forneca exatamente um entre `nf_anterior` e `ponto_corte`."
            )
        return self


class AprovarAuditoriaRequest(BaseModel):
    """PATCH /auditorias/{id}/aprovar body."""

    auditor: str = "demo"
    observacao: str | None = None


class AlertaResponse(BaseModel):
    """Alerta enriquecido para o frontend."""

    id: int
    tipo: str
    severidade: str
    titulo: str
    descricao: str
    abastecimento_id: int | None
    impacto_financeiro: float | None
    payload: dict[str, Any]


class AuditoriaIndicadores(BaseModel):
    """Indicadores §4 + metadados, replicado no AuditoriaCompletaResponse."""

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
    parecer_status: Literal["ok", "placeholder", "ausente"] = "ausente"
    aprovada_em: datetime | None = None
    auditor_aprovacao: str | None = None
    observacao_aprovacao: str | None = None
    versao: int = 1
    total_versoes: int = 1
    is_atual: bool = True
    auditoria_atual_id: int | None = None


class ParecerMeta(BaseModel):
    """Metadados do parecer (provider, modelo, tokens)."""

    provider: str
    model: str | None
    offline: bool
    latency_s: float
    prompt_tokens: int
    completion_tokens: int


class AuditoriaCompletaResponse(BaseModel):
    """Resposta completa de POST /auditorias e GET /auditorias/{id}."""

    auditoria: AuditoriaIndicadores
    alertas: list[AlertaResponse]
    parecer_meta: ParecerMeta | None = None


class CandidatoGPSchema(BaseModel):
    id: int
    placa_ativo: str
    placa_ativo_normalizada: str
    equipamento: str | None
    marca: str | None
    modelo: str | None
    tipo_equipamento: str | None
    capacidade_litros: int | None
    situacao: str


class SugestaoSchema(BaseModel):
    abastecimento_id: int
    veiculo_infleet: str
    apelido_infleet: str | None
    candidato_gp: CandidatoGPSchema | None
    confianca: float
    justificativa: str


class SugerirReconciliacaoRequest(BaseModel):
    auditoria_id: int


class SugerirReconciliacaoResponse(BaseModel):
    sugestoes: list[SugestaoSchema]
    provider: str
    offline: bool


class MatchAproximadoSchema(BaseModel):
    """Candidato sugerido por similaridade textual (fallback determinístico).

    Usado quando a IA não retornou correspondência: oferece ao auditor uma
    lista curta de mobilizados da mesma obra com maior similaridade de
    placa/apelido/equipamento, para acelerar a triagem manual.
    """

    candidato: CandidatoGPSchema
    similaridade: float = Field(ge=0.0, le=1.0)
    motivo: str


class HistoricoReconciliacaoItemSchema(BaseModel):
    """Reconciliação aprovada no passado para o mesmo veículo (mesma string normalizada).

    Permite ao auditor reaproveitar decisões anteriores quando o mesmo
    "veículo não cadastrado" aparece em NFs diferentes.
    """

    reconciliacao_id: int
    criada_em: datetime
    auditor: str
    confianca: float | None
    justificativa: str | None
    mobilizado: CandidatoGPSchema
    auditoria_id: int | None = None


class ContextoReconciliacaoResponse(BaseModel):
    """GET /reconciliacao/contexto: matches aproximados + histórico.

    Resposta determinística (sem chamada de IA) usada como fallback quando
    o reconciliador semântico não encontra correspondência confiável. Ver
    achado AI-09.
    """

    abastecimento_id: int
    veiculo_raw: str
    apelido: str | None
    nome_obra: str
    termo_busca_sugerido: str
    matches_aproximados: list[MatchAproximadoSchema]
    historico: list[HistoricoReconciliacaoItemSchema]


class AprovarReconciliacaoRequest(BaseModel):
    abastecimento_id: int
    mobilizado_id: int
    auditor: str = "demo"
    confianca: float | None = None
    justificativa: str | None = None
    auditoria_id: int | None = None


class AprovarReconciliacaoResponse(BaseModel):
    status: str
    reconciliacao_id: int
    auditoria_atualizada: AuditoriaCompletaResponse | None


class AlertaConsolidado(BaseModel):
    """Resumo de alerta para a tabela consolidada (sem payload pesado)."""

    tipo: str
    severidade: str
    qtd: int


class NFConsolidadoItem(BaseModel):
    """Linha da visao consolidada: 1 NF por linha."""

    nota_fiscal: str
    data_recebimento: date
    nome_obra: str
    qtd_litros: float
    valor_total: float
    valor_litro: float
    auditoria_id: int | None
    nf_anterior: str | None
    diferenca_litros: float | None
    diferenca_percentual: float | None
    validacao_final: str | None  # "APROVADO" | "INCONSISTENTE" | None
    qtd_alertas: int
    qtd_alertas_alta: int
    alertas: list[AlertaConsolidado]
    impacto_financeiro_total: float


class ConsolidadoResponse(BaseModel):
    """GET /auditorias/consolidado."""

    periodo_inicio: date | None
    periodo_fim: date | None
    total_auditado_brl: float
    diferenca_total_litros: float
    diferenca_total_brl: float
    total_alertas: int
    qtd_aprovadas: int
    qtd_inconsistentes: int
    qtd_nao_auditadas: int
    qtd_reconciliacoes_pendentes: int
    items: list[NFConsolidadoItem]


# Resolver forward references (NFDetail -> AuditoriaResumo).
NFDetail.model_rebuild()


__all__ = [
    "AlertaResponse",
    "AprovarAuditoriaRequest",
    "AprovarReconciliacaoRequest",
    "AprovarReconciliacaoResponse",
    "AuditoriaCompletaResponse",
    "AuditoriaIndicadores",
    "AuditoriaResumo",
    "CandidatoGPSchema",
    "ContextoReconciliacaoResponse",
    "CriarAuditoriaRequest",
    "HealthzResponse",
    "HistoricoReconciliacaoItemSchema",
    "MatchAproximadoSchema",
    "NFDetail",
    "NFListItem",
    "ParecerMeta",
    "PontoCorteManualRequest",
    "StatsResponse",
    "SugerirReconciliacaoRequest",
    "SugerirReconciliacaoResponse",
    "SugestaoSchema",
]
