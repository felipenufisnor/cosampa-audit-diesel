"""Modelos SQLModel correspondentes ao schema do SQLite."""

from __future__ import annotations

from datetime import datetime, time

from sqlmodel import Field, SQLModel


class Mobilizado(SQLModel, table=True):
    """Equipamento mobilizado/desmobilizado em uma obra (origem: Gestao de Projetos)."""

    id: int | None = Field(default=None, primary_key=True)
    codigo_projeto: str
    nome_obra: str
    tipo_equipamento: str | None = None
    equipamento: str | None = None
    marca: str | None = None
    modelo: str | None = None
    placa_ativo_raw: str
    placa_ativo_normalizada: str = Field(index=True)
    situacao: str
    data_mobilizacao: datetime | None = None
    data_desmobilizacao: datetime | None = None
    capacidade_litros: int | None = None
    ano: int | None = None


class Checklist(SQLModel, table=True):
    """Recebimento de NF de diesel (origem: GLPI - listagem de chamados)."""

    id: int | None = Field(default=None, primary_key=True)
    numero_chamado: str = Field(index=True)
    nota_fiscal: str = Field(index=True, unique=True)
    nome_obra: str
    cnpj_fornecedor: str
    data_recebimento: datetime
    hora_inicio_descarga: time
    hora_final_descarga: time
    datetime_fim_descarga: datetime
    quantidade_nf_litros: float
    volume_conferido_litros: float
    estoque_antes_tanque_litros: float
    estoque_antes_comboio_litros: float
    preco_unitario: float
    valor_total_nf: float


class Abastecimento(SQLModel, table=True):
    """Abastecimento individual de equipamento (origem: Infleet)."""

    id: int | None = Field(default=None, primary_key=True)
    data: datetime
    veiculo_raw: str
    veiculo_normalizado: str = Field(index=True)
    apelido: str | None = None
    quantidade_litros: float
    custo_total: float
    valor_litro: float
    medido_por: str | None = None
    medicao: float | None = None
    autonomia_media: float | None = None
    observacoes: str | None = None
    inconsistencias_infleet: str | None = None
    fornecedor: str | None = None


class Auditoria(SQLModel, table=True):
    """Resultado consolidado de uma auditoria entre duas NFs sequenciais."""

    id: int | None = Field(default=None, primary_key=True)
    nf_anterior: str = Field(index=True)
    nf_atual: str = Field(index=True)
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
    parecer_ia: str | None = None
    # Campos de aprovacao manual (PATCH /auditorias/{id}/aprovar). Permitem
    # marcar uma auditoria INCONSISTENTE como APROVADA apos validacao do
    # auditor, mantendo rastreabilidade. Sao preenchidos apenas no fluxo
    # de aprovacao manual; permanecem None para aprovacoes automaticas.
    aprovada_em: datetime | None = None
    auditor_aprovacao: str | None = None
    observacao_aprovacao: str | None = None


class Alerta(SQLModel, table=True):
    """Alerta gerado por uma checagem da audit.alerts.* dentro de uma auditoria."""

    id: int | None = Field(default=None, primary_key=True)
    auditoria_id: int = Field(foreign_key="auditoria.id")
    tipo: str
    severidade: str
    abastecimento_id: int | None = Field(default=None, foreign_key="abastecimento.id")
    titulo: str
    descricao: str
    payload_json: str
    impacto_financeiro: float | None = None


class ReconciliacaoAprovada(SQLModel, table=True):
    """Vinculo aprovado entre um abastecimento orfao e um mobilizado.

    Criado pelo endpoint POST /reconciliacao/aprovar. Nao altera a tabela
    Mobilizado nem Abastecimento; e considerado pelo engine ao re-auditar
    como uma "lista de exclusao" para o NaoCadastradoAlert.
    """

    id: int | None = Field(default=None, primary_key=True)
    abastecimento_id: int = Field(foreign_key="abastecimento.id", index=True)
    mobilizado_id: int = Field(foreign_key="mobilizado.id", index=True)
    auditor: str
    confianca: float | None = None
    justificativa: str | None = None
    criada_em: datetime
