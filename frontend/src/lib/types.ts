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
  assistant_status:
    | "available"
    | "degraded_cache"
    | "offline_fixture"
    | "missing_key"
    | "provider_error";
  assistant_reason: string;
  assistant_can_answer_free_text: boolean;
  assistant_has_cached_answers: boolean;
}

export interface PerguntaSugerida {
  pergunta: string;
  cacheada: boolean;
}

export interface PerguntasSugeridasResponse {
  auditoria_id: number;
  perguntas: PerguntaSugerida[];
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
  periodo_nfs_inicio: string | null;
  periodo_nfs_fim: string | null;
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
  qtd_auditorias: number;
}

export interface AuditoriaResumo {
  id: number;
  nf_anterior: string;
  nf_atual: string;
  nome_obra: string;
  criada_em: string;
  validacao_final: ValidacaoFinal;
  diferenca_percentual: number;
  versao: number;
  total_versoes: number;
  is_atual: boolean;
  auditoria_atual_id: number | null;
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
  parecer_status: "ok" | "placeholder" | "ausente";
  aprovada_em: string | null;
  auditor_aprovacao: string | null;
  observacao_aprovacao: string | null;
  versao: number;
  total_versoes: number;
  is_atual: boolean;
  auditoria_atual_id: number | null;
}

export type ModoAuditoria = "nova_versao" | "sobrescrever_ultima";

export interface PontoCorteManual {
  data_inicio: string; // ISO datetime, ex: "2026-03-01T08:00:00"
  estoque_tanque_inicial_litros: number;
  estoque_comboio_inicial_litros: number;
  motivo: string;
}

export interface CriarAuditoriaPayload {
  nf_atual: string;
  nf_anterior?: string;
  ponto_corte?: PontoCorteManual;
  gerar_parecer?: boolean;
  modo?: ModoAuditoria;
}

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

export interface MatchAproximado {
  candidato: CandidatoGP;
  similaridade: number;
  motivo: string;
}

export interface HistoricoReconciliacaoItem {
  reconciliacao_id: number;
  criada_em: string;
  auditor: string;
  confianca: number | null;
  justificativa: string | null;
  mobilizado: CandidatoGP;
  auditoria_id: number | null;
}

export interface ContextoReconciliacaoResponse {
  abastecimento_id: number;
  veiculo_raw: string;
  apelido: string | null;
  nome_obra: string;
  termo_busca_sugerido: string;
  matches_aproximados: MatchAproximado[];
  historico: HistoricoReconciliacaoItem[];
}

// --- Padroes proativos (Feature C) ----------------------------------------

export type PadraoSeveridade = "alta" | "media" | "baixa";

export interface Padrao {
  id: number;
  tipo: string;
  titulo: string;
  descricao: string;
  severidade: PadraoSeveridade;
  dados: Record<string, unknown>;
  criado_em: string;
  auditoria_alvo_id: number | null;
  auditoria_alvo_nf: string | null;
}

export interface PadroesResponse {
  padroes: Padrao[];
  atualizado_em: string | null;
}

export interface RecalcularPadroesResponse {
  n_candidatos: number;
  n_padroes: number;
  provider: string;
  modelo: string | null;
  offline: boolean;
}

// --- Assistente (Feature B) -----------------------------------------------

export type AssistantStreamKind =
  | "assistant_status"
  | "tool_call_started"
  | "tool_call_completed"
  | "assistant_chunk"
  | "assistant_done"
  | "error";

export interface AssistantStreamEvent {
  event: AssistantStreamKind;
  payload: Record<string, unknown>;
}

export interface MensagemAssistente {
  id: number;
  papel: "user" | "assistant";
  conteudo: string;
  criada_em: string;
}

export interface AssistenteHistorico {
  auditoria_id: number;
  mensagens: MensagemAssistente[];
}

// --- Reasoning Stream (Feature A) -----------------------------------------

export type StreamEventKind =
  | "step_started"
  | "step_completed"
  | "insight_found"
  | "ia_thinking_start"
  | "ia_thinking_chunk"
  | "ia_thinking_end"
  | "final_result"
  | "error";

export interface StreamEvent {
  event: StreamEventKind;
  payload: Record<string, unknown>;
}
