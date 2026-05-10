/**
 * Cliente fetch tipado para o backend FastAPI. Le NEXT_PUBLIC_API_URL.
 *
 * Sem server actions: tudo roda no cliente, react-query gerencia cache e
 * estados (loading/error). Erros sao normalizados em ApiError para que toasts
 * mostrem detail.
 */

import type {
  AprovarReconciliacaoResponse,
  AuditoriaCompleta,
  AuditoriaResumo,
  ConsolidadoResponse,
  Healthz,
  ModoAuditoria,
  NFDetail,
  NFListItem,
  Stats,
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
  criarAuditoria: (input: {
    nf_anterior: string;
    nf_atual: string;
    gerar_parecer?: boolean;
    modo?: ModoAuditoria;
  }) =>
    request<AuditoriaCompleta>("/auditorias", {
      method: "POST",
      json: { gerar_parecer: true, modo: "nova_versao" as ModoAuditoria, ...input },
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
  sugerirReconciliacao: (auditoria_id: number) =>
    request<SugerirReconciliacaoResponse>("/reconciliacao/sugerir", {
      method: "POST",
      json: { auditoria_id },
    }),
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
