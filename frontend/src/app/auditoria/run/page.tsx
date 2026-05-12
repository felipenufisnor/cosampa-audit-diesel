"use client";

/**
 * Reasoning Stream (Feature A da v2).
 *
 * Consome POST /auditorias/stream em SSE e renderiza um log narrado
 * passo a passo. Recebe `?ant=NF&atual=NF` via query string.
 *
 * Ao receber `final_result`, redireciona para /auditoria/{id}.
 */

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertCircle, CheckCircle2, Loader2, Sparkle } from "lucide-react";

import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { StreamEvent } from "@/lib/types";

type StepStatus = "running" | "done" | "pending";

interface StepInsight {
  tipo: string;
  descricao: string;
  severidade: "info" | "warning" | "alta" | string;
}

interface ThinkingBlock {
  id: string;
  contexto: string;
  modelo: string;
  texto: string;
  endedAt: number | null;
}

interface StepRow {
  key: string;
  kind: "step" | "thinking";
  title: string;
  status: StepStatus;
  resumo?: string;
  duracaoMs?: number;
  insights: StepInsight[];
  thinking?: ThinkingBlock;
}

export default function RunPage() {
  return (
    <React.Suspense fallback={<RunPageSkeleton />}>
      <RunPageInner />
    </React.Suspense>
  );
}

function RunPageSkeleton() {
  return (
    <div className="mx-auto max-w-[1100px] space-y-6">
      <div className="h-9 w-48 rounded-md bg-zinc-100" />
      <div className="h-24 w-full rounded-2xl bg-zinc-100" />
    </div>
  );
}

function RunPageInner() {
  const router = useRouter();
  const search = useSearchParams();
  const nfAnterior = search.get("ant") ?? "";
  const nfAtual = search.get("atual") ?? "";

  const paramError =
    !nfAnterior || !nfAtual
      ? "Parâmetros ausentes: ant e atual são obrigatórios."
      : null;

  const [rows, setRows] = React.useState<StepRow[]>([]);
  const [erro, setErro] = React.useState<string | null>(paramError);
  const [done, setDone] = React.useState(false);
  const [finalId, setFinalId] = React.useState<number | null>(null);
  const [meta, setMeta] = React.useState<{ duracao: number; offline: boolean } | null>(null);
  const startedRef = React.useRef(false);

  React.useEffect(() => {
    if (startedRef.current) return;
    if (!nfAnterior || !nfAtual) return;
    startedRef.current = true;

    const controller = new AbortController();
    let currentThinkingKey: string | null = null;
    let recebeuEvento = false;
    const firstEventTimer = window.setTimeout(() => {
      if (!recebeuEvento) {
        setErro(
          "Nenhum evento recebido do backend. Verifique se a API atual está rodando e reinicie o frontend para recarregar NEXT_PUBLIC_API_URL.",
        );
        controller.abort();
      }
    }, 8000);

    function handle(ev: StreamEvent) {
      if (!recebeuEvento) {
        recebeuEvento = true;
        window.clearTimeout(firstEventTimer);
      }
      setRows((prev) => {
        const next = [...prev];
        switch (ev.event) {
          case "step_started": {
            const step = String(ev.payload["step"] ?? "");
            next.push({
              key: `step-${next.length}-${step}`,
              kind: "step",
              title: step,
              status: "running",
              insights: [],
            });
            return next;
          }
          case "step_completed": {
            const step = String(ev.payload["step"] ?? "");
            const idx = next.findLastIndex((r) => r.kind === "step" && r.title === step);
            if (idx >= 0) {
              next[idx] = {
                ...next[idx],
                status: "done",
                resumo: ev.payload["resumo"] ? String(ev.payload["resumo"]) : undefined,
                duracaoMs: Number(ev.payload["duracao_ms"] ?? 0),
              };
            }
            return next;
          }
          case "insight_found": {
            const target = next.findLastIndex((r) => r.status !== "done");
            const row = target >= 0 ? next[target] : next[next.length - 1];
            if (!row) return next;
            row.insights = [
              ...row.insights,
              {
                tipo: String(ev.payload["tipo"] ?? ""),
                descricao: String(ev.payload["descricao"] ?? ""),
                severidade: String(ev.payload["severidade"] ?? "info"),
              },
            ];
            return next;
          }
          case "ia_thinking_start": {
            const key = `th-${next.length}`;
            currentThinkingKey = key;
            next.push({
              key,
              kind: "thinking",
              title: String(ev.payload["contexto"] ?? "A IA esta analisando"),
              status: "running",
              insights: [],
              thinking: {
                id: key,
                contexto: String(ev.payload["contexto"] ?? ""),
                modelo: String(ev.payload["modelo"] ?? ""),
                texto: "",
                endedAt: null,
              },
            });
            return next;
          }
          case "ia_thinking_chunk": {
            if (!currentThinkingKey) return next;
            const idx = next.findIndex((r) => r.key === currentThinkingKey);
            if (idx < 0 || !next[idx].thinking) return next;
            const before = next[idx];
            next[idx] = {
              ...before,
              thinking: {
                ...before.thinking!,
                texto: before.thinking!.texto + String(ev.payload["texto"] ?? ""),
              },
            };
            return next;
          }
          case "ia_thinking_end": {
            if (!currentThinkingKey) return next;
            const idx = next.findIndex((r) => r.key === currentThinkingKey);
            if (idx >= 0 && next[idx].thinking) {
              next[idx] = {
                ...next[idx],
                status: "done",
                duracaoMs: Number(ev.payload["duracao_ms"] ?? 0),
                thinking: { ...next[idx].thinking!, endedAt: Date.now() },
              };
            }
            currentThinkingKey = null;
            return next;
          }
          case "final_result": {
            const aud = (ev.payload["auditoria"] ?? {}) as { id?: number };
            const streamingMeta = (ev.payload["streaming_meta"] ?? {}) as {
              duracao_total_s?: number;
              modo_offline?: boolean;
            };
            if (typeof aud.id === "number") setFinalId(aud.id);
            setMeta({
              duracao: streamingMeta.duracao_total_s ?? 0,
              offline: Boolean(streamingMeta.modo_offline),
            });
            setDone(true);
            return next;
          }
          case "error": {
            setErro(String(ev.payload["mensagem"] ?? "Erro indefinido."));
            return next;
          }
          default:
            return next;
        }
      });
    }

    api
      .streamAuditoria({ nf_anterior: nfAnterior, nf_atual: nfAtual }, handle, controller.signal)
      .catch((e) => {
        if (controller.signal.aborted) return;
        setErro(e instanceof Error ? e.message : "Falha na conexao SSE");
      });
    return () => {
      window.clearTimeout(firstEventTimer);
      controller.abort();
    };
  }, [nfAnterior, nfAtual]);

  // Redireciona suavemente apos concluir
  React.useEffect(() => {
    if (done && finalId) {
      const t = setTimeout(() => router.push(`/auditoria/${finalId}`), 1800);
      return () => clearTimeout(t);
    }
  }, [done, finalId, router]);

  return (
    <div className="mx-auto max-w-[1100px] space-y-6">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/" },
          { label: "Auditoria em andamento" },
        ]}
      />

      <header className="rounded-2xl border border-app-border bg-white px-6 py-5 shadow-[0_4px_14px_rgba(15,23,42,0.06)]">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
          Auditoria em andamento
        </p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-zinc-950">
          NF {nfAtual || "?"} <span className="text-zinc-400">vs.</span> NF {nfAnterior || "?"}
        </h2>
        <p className="mt-1 text-sm text-zinc-500">
          O sistema executa as etapas deterministicas e narra os trechos onde a
          analise automatica intervem.
        </p>
      </header>

      {erro && (
        <Card>
          <CardContent className="flex items-start gap-3 py-4 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <div>
              <p className="font-medium">{erro}</p>
              <p className="mt-1 text-zinc-500">
                <Link href="/" className="underline">
                  Voltar ao Dashboard
                </Link>
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <section
        aria-label="Log da auditoria"
        className="space-y-3 rounded-2xl border border-app-border bg-zinc-50 p-5"
      >
        {rows.length === 0 && !erro && (
          <div className="flex items-center gap-3 text-sm text-zinc-500">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            Conectando ao servico de auditoria...
          </div>
        )}
        {rows.map((row) => (
          <StepCard key={row.key} row={row} />
        ))}
      </section>

      {done && (
        <Card>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
            <div className="flex items-center gap-3 text-sm text-zinc-700">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden />
              <span>
                Auditoria concluida em <strong>{meta?.duracao.toFixed(1)}s</strong>
                {meta?.offline && (
                  <Badge variant="muted" className="ml-2 align-middle">
                    modo offline
                  </Badge>
                )}
              </span>
            </div>
            {finalId !== null && (
              <Link href={`/auditoria/${finalId}`}>
                <Button variant="primary">Abrir auditoria</Button>
              </Link>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StepCard({ row }: { row: StepRow }) {
  const isThinking = row.kind === "thinking";
  return (
    <div className="rounded-xl border border-app-border bg-white px-4 py-3 shadow-sm">
      <div className="flex items-start gap-3">
        <StatusIcon status={row.status} thinking={isThinking} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <p
              className={
                isThinking
                  ? "text-[15px] font-medium text-zinc-900"
                  : "font-mono text-[13.5px] font-medium text-zinc-800"
              }
            >
              {row.title}
            </p>
            {row.resumo && (
              <p className="text-xs text-zinc-500">{row.resumo}</p>
            )}
            {row.duracaoMs !== undefined && row.status === "done" && (
              <p className="text-xs text-zinc-400 tabular-nums">
                {row.duracaoMs}ms
              </p>
            )}
            {row.thinking?.modelo && (
              <p className="text-xs text-zinc-400">{row.thinking.modelo}</p>
            )}
          </div>

          {row.insights.length > 0 && (
            <ul className="mt-2 space-y-1">
              {row.insights.map((ins, i) => (
                <li
                  key={`${row.key}-i-${i}`}
                  className="flex items-start gap-2 text-sm text-zinc-700"
                >
                  <span
                    className={[
                      "mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full",
                      ins.severidade === "alta"
                        ? "bg-red-500"
                        : ins.severidade === "warning"
                          ? "bg-amber-500"
                          : "bg-zinc-400",
                    ].join(" ")}
                  />
                  <span>{ins.descricao}</span>
                </li>
              ))}
            </ul>
          )}

          {row.thinking && (
            <div className="mt-2 rounded-lg bg-zinc-100/70 px-3 py-2 text-[14.5px] leading-relaxed text-zinc-700">
              {row.thinking.texto || (
                <span className="text-zinc-400">A análise automática está gerando o texto...</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusIcon({ status, thinking }: { status: StepStatus; thinking: boolean }) {
  if (status === "done") {
    return (
      <span className="mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
      </span>
    );
  }
  if (status === "running") {
    return (
      <span className="mt-1 inline-flex h-5 w-5 shrink-0 items-center justify-center">
        {thinking ? (
          <Sparkle className="h-4 w-4 animate-pulse text-brand-primary-dark" aria-hidden />
        ) : (
          <Loader2 className="h-4 w-4 animate-spin text-zinc-500" aria-hidden />
        )}
      </span>
    );
  }
  return (
    <span className="mt-1 inline-block h-5 w-5 shrink-0 rounded-full border border-dashed border-zinc-300" />
  );
}
