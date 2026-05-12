/**
 * Dados sinteticos do Preview de Investigacoes.
 *
 * NAO sao reais. NAO sao persistidos. Apenas alimentam o kanban
 * navegavel para demonstrar a funcionalidade prevista para a fase 2.
 *
 * Mudancas entre colunas via drag-and-drop ficam em estado local; ao
 * recarregar a pagina volta para o snapshot abaixo.
 */

export type ColunaKanban =
  | "abertas"
  | "aguardando_obra"
  | "em_analise"
  | "concluidas";

export type TipoInconsistencia =
  | "Não cadastrado"
  | "Pós-desmobilização"
  | "Outlier de consumo"
  | "Diferença de saídas"
  | "Duplicidade";

export type PrioridadeInvestigacao = "alta" | "media" | "baixa";

export interface EventoTimeline {
  data: string; // dd/mm hh:mm
  texto: string;
  marca?: "sistema" | "auditor" | "obra";
}

export interface Evidencia {
  nome: string;
  tipo: "pdf" | "jpg" | "xlsx";
  tamanho_kb: number;
}

export interface Investigacao {
  id: string;
  coluna: ColunaKanban;
  nf: string;
  obra: string;
  tipo: TipoInconsistencia;
  prioridade: PrioridadeInvestigacao;
  responsavel: { nome: string; iniciais: string };
  aberta_ha_dias: number;
  resumo: string;
  timeline: EventoTimeline[];
  evidencias: Evidencia[];
  analise_automatica: string;
}

export const INVESTIGACOES_MOCK: Investigacao[] = [
  // --- ABERTAS (3) ---------------------------------------------------------
  {
    id: "INV-2026-042",
    coluna: "abertas",
    nf: "8187",
    obra: "CONSÓRCIO ARCO JP",
    tipo: "Não cadastrado",
    prioridade: "alta",
    responsavel: { nome: "Camila Souza", iniciais: "CS" },
    aberta_ha_dias: 3,
    resumo:
      "36 placas detectadas sem cadastro exato no GP. Inclui veículo 04T639 com sinal de pós-desmobilização recorrente.",
    timeline: [
      { data: "13/04 14:20", texto: "Inconsistência detectada automaticamente pelo sistema.", marca: "sistema" },
      { data: "13/04 15:01", texto: "Auditor abriu investigação e atribuiu a Camila Souza.", marca: "auditor" },
      { data: "14/04 09:30", texto: "E-mail enviado para o gestor da obra solicitando lista de cadastros pendentes.", marca: "auditor" },
    ],
    evidencias: [
      { nome: "amostra_placas.xlsx", tipo: "xlsx", tamanho_kb: 28 },
      { nome: "nf_8187_capa.pdf", tipo: "pdf", tamanho_kb: 142 },
    ],
    analise_automatica:
      "Probabilidade de fraude: baixa. Padrão consistente com gap de cadastro: 27 das 36 placas seguem o padrão 00X000 típico de cadastro por ativo não realizado. Sugestão: cobrar formalmente a obra pelo cadastro retroativo no GP.",
  },
  {
    id: "INV-2026-043",
    coluna: "abertas",
    nf: "8278",
    obra: "CONSÓRCIO ARCO JP",
    tipo: "Outlier de consumo",
    prioridade: "media",
    responsavel: { nome: "Diego Pacheco", iniciais: "DP" },
    aberta_ha_dias: 2,
    resumo:
      "Veículo OSB8826 consumiu 600L na última semana versus 140L de baseline (+329%).",
    timeline: [
      { data: "15/04 08:10", texto: "Outlier disparado pelo engine determinístico (z-score 4.6).", marca: "sistema" },
      { data: "15/04 11:45", texto: "Diego abriu a investigação e marcou prioridade média.", marca: "auditor" },
    ],
    evidencias: [],
    analise_automatica:
      "Contexto operacional plausível: há um pico semelhante de outras placas da mesma frota no mesmo período, indicando possível mudança de frente de obra. Recomendado confirmar com o coordenador antes de escalar.",
  },
  {
    id: "INV-2026-044",
    coluna: "abertas",
    nf: "8328",
    obra: "CONSÓRCIO ARCO JP",
    tipo: "Diferença de saídas",
    prioridade: "alta",
    responsavel: { nome: "Renata Lima", iniciais: "RL" },
    aberta_ha_dias: 1,
    resumo: "Diferença de saídas em -7.4% acima do limite de 2% do escopo.",
    timeline: [
      { data: "16/04 17:02", texto: "Engine retornou validação INCONSISTENTE.", marca: "sistema" },
      { data: "16/04 17:30", texto: "Auditor revisou indicadores e iniciou investigação.", marca: "auditor" },
    ],
    evidencias: [{ nome: "indicadores_nf_8328.pdf", tipo: "pdf", tamanho_kb: 88 }],
    analise_automatica:
      "Hipótese principal: omissão de registros no Infleet. Há 4 dias consecutivos no período sem qualquer abastecimento registrado, atípico para a frota mobilizada. Recomendado confrontar com o checklist físico no GLPI.",
  },

  // --- AGUARDANDO OBRA (2) -------------------------------------------------
  {
    id: "INV-2026-038",
    coluna: "aguardando_obra",
    nf: "8108",
    obra: "CONSÓRCIO ARCO JP",
    tipo: "Pós-desmobilização",
    prioridade: "alta",
    responsavel: { nome: "Camila Souza", iniciais: "CS" },
    aberta_ha_dias: 8,
    resumo: "Veículo 04T639 com 18 abastecimentos após a data de desmobilização.",
    timeline: [
      { data: "08/04 10:11", texto: "Alerta de pós-desmobilização gerado.", marca: "sistema" },
      { data: "08/04 14:05", texto: "Auditor enviou solicitação formal ao gestor da obra.", marca: "auditor" },
      { data: "10/04 09:00", texto: "Obra acusou recebimento e prometeu apurar internamente.", marca: "obra" },
    ],
    evidencias: [{ nome: "checklist_fisico_8108.pdf", tipo: "pdf", tamanho_kb: 215 }],
    analise_automatica:
      "Severidade alta sustentada. Possível uso indevido do tanque comboio ou cadastro de desmobilização desatualizado no GP. Sem evidência da obra até 17/04, escalonar.",
  },
  {
    id: "INV-2026-040",
    coluna: "aguardando_obra",
    nf: "8187",
    obra: "CONSÓRCIO ARCO JP",
    tipo: "Duplicidade",
    prioridade: "media",
    responsavel: { nome: "Diego Pacheco", iniciais: "DP" },
    aberta_ha_dias: 5,
    resumo: "Dois abastecimentos com mesmo veículo e mesmo valor em janela de 12 minutos.",
    timeline: [
      { data: "11/04 13:22", texto: "Alerta de duplicidade gerado.", marca: "sistema" },
      { data: "12/04 09:15", texto: "Obra foi acionada para confirmar se houve registro duplicado no Infleet.", marca: "auditor" },
    ],
    evidencias: [],
    analise_automatica:
      "Padrão típico de duplo lançamento operacional. Recomendar invalidação de um dos registros e revisão do procedimento de campo.",
  },

  // --- EM ANALISE (1) ------------------------------------------------------
  {
    id: "INV-2026-035",
    coluna: "em_analise",
    nf: "8108",
    obra: "CONSÓRCIO ARCO JP",
    tipo: "Não cadastrado",
    prioridade: "media",
    responsavel: { nome: "Renata Lima", iniciais: "RL" },
    aberta_ha_dias: 12,
    resumo: "Lote de 9 placas com cadastro divergente entre GP e Infleet.",
    timeline: [
      { data: "04/04 11:00", texto: "Auditor iniciou normalização dos 9 cadastros divergentes.", marca: "auditor" },
      { data: "07/04 16:30", texto: "Recebida planilha de equivalência da obra.", marca: "obra" },
      { data: "12/04 10:45", texto: "Em revisão técnica antes de fechar.", marca: "auditor" },
    ],
    evidencias: [
      { nome: "equivalencia_cadastros.xlsx", tipo: "xlsx", tamanho_kb: 44 },
      { nome: "foto_placa_43.jpg", tipo: "jpg", tamanho_kb: 980 },
    ],
    analise_automatica:
      "7 das 9 placas batem com o cadastro do GP após remoção de hífen. Restam 2 placas indexadas por chassi no Infleet; conferir com o coordenador de frota.",
  },

  // --- CONCLUIDAS (4) ------------------------------------------------------
  {
    id: "INV-2026-030",
    coluna: "concluidas",
    nf: "8108",
    obra: "CONSÓRCIO ARCO JP",
    tipo: "Outlier de consumo",
    prioridade: "baixa",
    responsavel: { nome: "Diego Pacheco", iniciais: "DP" },
    aberta_ha_dias: 15,
    resumo: "Outlier explicado por mobilização temporária de retroescavadeira.",
    timeline: [
      { data: "31/03 14:00", texto: "Outlier detectado.", marca: "sistema" },
      { data: "01/04 09:30", texto: "Coordenador confirmou mobilização temporária.", marca: "obra" },
      { data: "01/04 10:00", texto: "Investigação encerrada como justificada.", marca: "auditor" },
    ],
    evidencias: [],
    analise_automatica:
      "Encerrada sem irregularidade. Contexto operacional confirmado por evidência da obra.",
  },
  {
    id: "INV-2026-028",
    coluna: "concluidas",
    nf: "8108",
    obra: "CONSÓRCIO ARCO JP",
    tipo: "Duplicidade",
    prioridade: "media",
    responsavel: { nome: "Camila Souza", iniciais: "CS" },
    aberta_ha_dias: 18,
    resumo: "Duplicidade real corrigida com invalidação no Infleet.",
    timeline: [
      { data: "28/03 11:30", texto: "Alerta gerado.", marca: "sistema" },
      { data: "29/03 15:00", texto: "Obra confirmou erro de lançamento.", marca: "obra" },
      { data: "30/03 08:15", texto: "Registro invalidado no Infleet pelo coordenador.", marca: "obra" },
    ],
    evidencias: [{ nome: "comprovante_invalidacao.pdf", tipo: "pdf", tamanho_kb: 64 }],
    analise_automatica: "Corrigida com sucesso. Sugerido reforço de procedimento.",
  },
  {
    id: "INV-2026-026",
    coluna: "concluidas",
    nf: "8108",
    obra: "CONSÓRCIO ARCO JP",
    tipo: "Diferença de saídas",
    prioridade: "media",
    responsavel: { nome: "Renata Lima", iniciais: "RL" },
    aberta_ha_dias: 22,
    resumo: "Saldo final reconciliado com checklist físico.",
    timeline: [
      { data: "25/03 08:45", texto: "Diferença detectada.", marca: "sistema" },
      { data: "26/03 10:00", texto: "Checklist físico apresentado pela obra.", marca: "obra" },
      { data: "27/03 14:30", texto: "Reconciliada e encerrada.", marca: "auditor" },
    ],
    evidencias: [{ nome: "checklist_fisico_anterior.pdf", tipo: "pdf", tamanho_kb: 198 }],
    analise_automatica:
      "Diferença explicada por erro de digitação do estoque inicial. Procedimento revisado.",
  },
  {
    id: "INV-2026-022",
    coluna: "concluidas",
    nf: "8108",
    obra: "CONSÓRCIO ARCO JP",
    tipo: "Não cadastrado",
    prioridade: "alta",
    responsavel: { nome: "Camila Souza", iniciais: "CS" },
    aberta_ha_dias: 27,
    resumo: "12 cadastros pendentes incluídos no GP retroativamente.",
    timeline: [
      { data: "20/03 09:00", texto: "Solicitação formal enviada.", marca: "auditor" },
      { data: "25/03 11:00", texto: "Obra incluiu cadastros no GP.", marca: "obra" },
      { data: "25/03 16:30", texto: "Investigação encerrada.", marca: "auditor" },
    ],
    evidencias: [{ nome: "evidencia_cadastros_gp.xlsx", tipo: "xlsx", tamanho_kb: 56 }],
    analise_automatica:
      "Falha procedimental confirmada. Aderência futura será monitorada via Padrões detectados.",
  },
];

export const COLUNAS: { id: ColunaKanban; titulo: string }[] = [
  { id: "abertas", titulo: "Abertas" },
  { id: "aguardando_obra", titulo: "Aguardando obra" },
  { id: "em_analise", titulo: "Em análise" },
  { id: "concluidas", titulo: "Concluídas" },
];

export const RESPONSAVEIS = [
  "Camila Souza",
  "Diego Pacheco",
  "Renata Lima",
] as const;

export const TIPOS: TipoInconsistencia[] = [
  "Não cadastrado",
  "Pós-desmobilização",
  "Outlier de consumo",
  "Diferença de saídas",
  "Duplicidade",
];

export const OBRAS = ["CONSÓRCIO ARCO JP"] as const;
