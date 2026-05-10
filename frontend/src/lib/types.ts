/**
 * Tipos espelhando os schemas pydantic do backend (audit_diesel.api.schemas).
 * Mantenha esta lista sincronizada manualmente: a quantidade de modelos eh
 * pequena e nao vale subir um pipeline de codegen para a POC.
 */

export interface Healthz {
  status: string;
  db: string;
  ai: string;
  provider: string;
  model: string;
  fallback_model: string | null;
  offline: boolean;
  demo_mode: boolean;
}

export interface AlertaConsolidado {
  tipo: TipoAlerta;
  severidade: SeveridadeAlerta;
  qtd: number;
}

export interface NFConsolidadoItem {
  nota_fiscal: string;
  data_recebimento: string;
  nome_obra: string;
  qtd_litros: number;
  valor_total: number;
  valor_litro: number;
  auditoria_id: number | null;
  nf_anterior: string | null;
  diferenca_litros: number | null;
  diferenca_percentual: number | null;
  validacao_final: ValidacaoFinal | null;
  qtd_alertas: number;
  qtd_alertas_alta: number;
  alertas: AlertaConsolidado[];
  impacto_financeiro_total: number;
}

export interface ConsolidadoResponse {
  periodo_inicio: string | null;
  periodo_fim: string | null;
  total_auditado_brl: number;
  diferenca_total_litros: number;
  diferenca_total_brl: number;
  total_alertas: number;
  qtd_aprovadas: number;
  qtd_inconsistentes: number;
  qtd_nao_auditadas: number;
  qtd_reconciliacoes_pendentes: number;
  items: NFConsolidadoItem[];
}

export interface Stats {
  total_abastecimentos: number;
  total_litros: number;
  total_custo_brl: number;
  periodo_inicio: string | null;
  periodo_fim: string | null;
  total_nfs: number;
  total_mobilizados: number;
  mobilizados_ativos: number;
  veiculos_distintos_infleet: number;
  abastecimentos_nao_cadastrados: number;
  custo_nao_cadastrado_brl: number;
  pct_custo_nao_cadastrado: number;
}

export type ValidacaoFinal = "APROVADO" | "INCONSISTENTE";

export interface NFListItem {
  nota_fiscal: string;
  data_recebimento: string;
  nome_obra: string;
  valor_total: number;
  qtd_litros: number;
  ultima_auditoria_id: number | null;
  ultima_validacao: ValidacaoFinal | null;
}

export interface AuditoriaResumo {
  id: number;
  nf_anterior: string;
  nf_atual: string;
  nome_obra: string;
  criada_em: string;
  validacao_final: ValidacaoFinal;
  diferenca_percentual: number;
}

export interface NFDetail {
  nota_fiscal: string;
  numero_chamado: string;
  data_recebimento: string;
  hora_inicio_descarga: string;
  hora_final_descarga: string;
  nome_obra: string;
  cnpj_fornecedor: string;
  quantidade_nf_litros: number;
  volume_conferido_litros: number;
  estoque_antes_tanque_litros: number;
  estoque_antes_comboio_litros: number;
  preco_unitario: number;
  valor_total_nf: number;
  auditorias_passadas: AuditoriaResumo[];
}

export type SeveridadeAlerta = "alta" | "media" | "baixa";

export type TipoAlerta =
  | "NAO_CADASTRADO"
  | "POS_DESMOB"
  | "OUTLIER"
  | "DUPLICIDADE";

export interface Alerta {
  id: number;
  tipo: TipoAlerta;
  severidade: SeveridadeAlerta;
  titulo: string;
  descricao: string;
  abastecimento_id: number | null;
  impacto_financeiro: number | null;
  payload: Record<string, unknown>;
}

export interface AuditoriaIndicadores {
  id: number;
  nf_anterior: string;
  nf_atual: string;
  nome_obra: string;
  criada_em: string;
  estoque_inicial_anterior: number;
  quantidade_descarregada_anterior: number;
  estoque_final_teorico_anterior: number;
  saidas_registradas_litros: number;
  saidas_registradas_custo: number;
  estoque_inicial_atual: number;
  saida_teorica_litros: number;
  diferenca_litros: number;
  diferenca_percentual: number;
  qtd_equipamentos_nao_cadastrados: number;
  validacao_final: ValidacaoFinal;
  parecer_ia: string | null;
  aprovada_em: string | null;
  auditor_aprovacao: string | null;
  observacao_aprovacao: string | null;
}

export type ModoAuditoria = "nova_versao" | "sobrescrever_ultima";

export interface ParecerMeta {
  provider: string;
  model: string | null;
  offline: boolean;
  latency_s: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface AuditoriaCompleta {
  auditoria: AuditoriaIndicadores;
  alertas: Alerta[];
  parecer_meta: ParecerMeta | null;
}

export interface CandidatoGP {
  id: number;
  placa_ativo: string;
  placa_ativo_normalizada: string;
  equipamento: string | null;
  marca: string | null;
  modelo: string | null;
  tipo_equipamento: string | null;
  capacidade_litros: number | null;
  situacao: string;
}

export interface SugestaoReconciliacao {
  abastecimento_id: number;
  veiculo_infleet: string;
  apelido_infleet: string | null;
  candidato_gp: CandidatoGP | null;
  confianca: number;
  justificativa: string;
}

export interface SugerirReconciliacaoResponse {
  sugestoes: SugestaoReconciliacao[];
  provider: string;
  offline: boolean;
}

export interface AprovarReconciliacaoResponse {
  status: string;
  reconciliacao_id: number;
  auditoria_atualizada: AuditoriaCompleta | null;
}
