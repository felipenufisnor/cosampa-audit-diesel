/**
 * Cliente fetch tipado para o backend FastAPI. Le NEXT_PUBLIC_API_URL.
 *
 * Sem server actions: tudo roda no cliente, react-query gerencia cache e
 * estados (loading/error). Erros sao normalizados em ApiError para que toasts
 * mostrem detail.
 */

import type {
  AprovarReconciliacaoResponse,
  AssistantStreamEvent,
  AssistenteHistorico,
  AuditoriaCompleta,
  AuditoriaResumo,
  ConsolidadoResponse,
  ContextoReconciliacaoResponse,
  CriarAuditoriaPayload,
  Healthz,
  NFDetail,
  NFListItem,
  PadroesResponse,
  PerguntasSugeridasResponse,
  RecalcularPadroesResponse,
  Stats,
  StreamEvent,
  SugerirReconciliacaoResponse,
} from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8001";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  let body: BodyInit | undefined;
  if (init?.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const res = await fetch(`${BASE_URL}${path}`, { ...init, body, headers });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = await res.json();
    } catch {
      // sem body
    }
    const msg =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `HTTP ${res.status}`;
    throw new ApiError(res.status, detail, msg);
  }
  return (await res.json()) as T;
}

export const api = {
  healthz: () => request<Healthz>("/healthz"),
  stats: () => request<Stats>("/stats"),
  listarNfs: () => request<NFListItem[]>("/nfs"),
  detalheNf: (nf: string) => request<NFDetail>(`/nfs/${encodeURIComponent(nf)}`),
  criarAuditoria: (input: CriarAuditoriaPayload) =>
    request<AuditoriaCompleta>("/auditorias", {
      method: "POST",
      json: { gerar_parecer: true, modo: "nova_versao", ...input },
    }),
  getAuditoria: (id: number) => request<AuditoriaCompleta>(`/auditorias/${id}`),
  aprovarAuditoria: (
    id: number,
    body: { auditor?: string; observacao?: string },
  ) =>
    request<AuditoriaCompleta>(`/auditorias/${id}/aprovar`, {
      method: "PATCH",
      json: body,
    }),
  regenerarParecer: (id: number) =>
    request<AuditoriaCompleta>(`/auditorias/${id}/parecer/regenerar`, {
      method: "POST",
    }),
  listarAuditoriasDaNf: (nf: string) =>
    request<AuditoriaResumo[]>(
      `/nfs/${encodeURIComponent(nf)}/auditorias`,
    ),
  consolidado: () => request<ConsolidadoResponse>("/auditorias/consolidado"),
  baixarPdf: async (id: number): Promise<Blob> => {
    const res = await fetch(`${BASE_URL}/auditorias/${id}/pdf`, {
      headers: { Accept: "application/pdf" },
    });
    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        detail = await res.json();
      } catch {
        // sem body json
      }
      throw new ApiError(res.status, detail, `HTTP ${res.status}`);
    }
    return await res.blob();
  },
  csvConsolidadoUrl: () => `${BASE_URL}/auditorias/consolidado.csv`,
  listarPadroes: () => request<PadroesResponse>("/padroes"),
  recalcularPadroes: () =>
    request<RecalcularPadroesResponse>("/padroes/recalcular", { method: "POST" }),
  listarMensagensAssistente: (auditoriaId: number) =>
    request<AssistenteHistorico>(`/auditorias/${auditoriaId}/mensagens`),
  listarPerguntasSugeridas: (auditoriaId: number) =>
    request<PerguntasSugeridasResponse>(
      `/auditorias/${auditoriaId}/perguntas-sugeridas`,
    ),
  streamPergunta: async (
    auditoriaId: number,
    pergunta: string,
    onEvent: (event: AssistantStreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> => {
    const res = await fetch(`${BASE_URL}/auditorias/${auditoriaId}/perguntar`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ pergunta }),
      signal,
    });
    if (!res.ok || !res.body) {
      let detail: unknown = res.statusText;
      try {
        detail = await res.json();
      } catch {
        // sem body json
      }
      throw new ApiError(res.status, detail, `HTTP ${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const line = raw.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        try {
          const parsed = JSON.parse(line.slice(6)) as AssistantStreamEvent;
          onEvent(parsed);
        } catch {
          // ignora linhas malformadas
        }
      }
    }
  },
  streamAuditoria: async (
    input: { nf_anterior: string; nf_atual: string },
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> => {
    const res = await fetch(`${BASE_URL}/auditorias/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(input),
      signal,
    });
    if (!res.ok || !res.body) {
      let detail: unknown = res.statusText;
      try {
        detail = await res.json();
      } catch {
        // sem body json
      }
      throw new ApiError(res.status, detail, `HTTP ${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const line = raw.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        try {
          const parsed = JSON.parse(line.slice(6)) as StreamEvent;
          onEvent(parsed);
        } catch {
          // ignora linhas malformadas (keepalives)
        }
      }
    }
  },
  sugerirReconciliacao: (auditoria_id: number) =>
    request<SugerirReconciliacaoResponse>("/reconciliacao/sugerir", {
      method: "POST",
      json: { auditoria_id },
    }),
  contextoReconciliacao: (abastecimento_id: number, auditoria_id: number) =>
    request<ContextoReconciliacaoResponse>(
      `/reconciliacao/contexto?abastecimento_id=${abastecimento_id}&auditoria_id=${auditoria_id}`,
    ),
  aprovarReconciliacao: (input: {
    abastecimento_id: number;
    mobilizado_id: number;
    auditor?: string;
    confianca?: number;
    justificativa?: string;
    auditoria_id?: number;
  }) =>
    request<AprovarReconciliacaoResponse>("/reconciliacao/aprovar", {
      method: "POST",
      json: { auditor: "demo", ...input },
    }),
};
