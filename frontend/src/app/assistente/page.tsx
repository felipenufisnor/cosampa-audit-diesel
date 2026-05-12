"use client";

import * as React from "react";
import { MessageSquare, Search } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { AssistenteDrawer } from "@/components/auditoria/assistente-drawer";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardSubtitle,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuditoria } from "@/hooks/use-auditoria";
import { useNFs } from "@/hooks/use-nfs";
import { formatBRL, formatDateBR, formatLitros } from "@/lib/format";
import type { NFListItem } from "@/lib/types";

export default function AssistentePage() {
  return (
    <React.Suspense fallback={<PageSkeleton />}>
      <AssistentePageInner />
    </React.Suspense>
  );
}

function AssistentePageInner() {
  const search = useSearchParams();
  const auditoriaIdInicial = parseAuditoriaId(
    search.get("auditoria_id") ?? search.get("id"),
  );
  const perguntaInicial = search.get("pergunta") ?? search.get("ask") ?? null;

  const nfsQuery = useNFs();
  const auditoriasDisponiveis = React.useMemo(
    () => (nfsQuery.data ?? []).filter((nf) => nf.ultima_auditoria_id),
    [nfsQuery.data],
  );
  const [auditoriaId, setAuditoriaId] = React.useState<number | null>(
    auditoriaIdInicial,
  );
  const [drawerAberto, setDrawerAberto] = React.useState(Boolean(auditoriaIdInicial));
  const [busca, setBusca] = React.useState("");

  const auditoriaQuery = useAuditoria(auditoriaId);
  const auditoria = auditoriaQuery.data?.auditoria;
  const nfSelecionada = auditoriasDisponiveis.find(
    (nf) => nf.ultima_auditoria_id === auditoriaId,
  );
  const auditoriasFiltradas = filtrarAuditorias(auditoriasDisponiveis, busca);

  function selecionar(id: number) {
    setAuditoriaId(id);
    setDrawerAberto(false);
  }

  return (
    <div className="mx-auto max-w-[1300px] space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
            Assistente
          </p>
          <h2 className="mt-1 text-[26px] font-bold tracking-tight text-zinc-950">
            Assistente de investigação
          </h2>
          <p className="mt-1 max-w-3xl text-[16px] text-zinc-500">
            Escolha uma auditoria para contextualizar a conversa sem sair desta
            página.
          </p>
        </div>
        {auditoria && (
          <Button onClick={() => setDrawerAberto(true)}>
            <MessageSquare className="h-4 w-4" aria-hidden />
            Abrir conversa
          </Button>
        )}
      </header>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(320px,420px)_1fr]">
        <Card>
          <CardHeader className="block space-y-1">
            <CardTitle>Contexto</CardTitle>
            <CardSubtitle>Auditorias disponíveis para consulta</CardSubtitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.1em] text-zinc-500">
                Selecionar NF auditada
              </span>
              <select
                value={auditoriaId ?? ""}
                onChange={(e) => selecionar(Number(e.target.value))}
                disabled={nfsQuery.isLoading || auditoriasDisponiveis.length === 0}
                className="h-10 w-full rounded-lg border border-app-border bg-white px-3 text-sm font-medium text-zinc-900 shadow-sm focus:border-brand-primary focus:outline-none focus:ring-2 focus:ring-brand-primary/20 disabled:cursor-not-allowed disabled:bg-zinc-50 disabled:text-zinc-400"
              >
                <option value="" disabled>
                  Escolha uma auditoria
                </option>
                {auditoriasDisponiveis.map((nf) => (
                  <option key={nf.ultima_auditoria_id} value={nf.ultima_auditoria_id ?? ""}>
                    NF {nf.nota_fiscal} - Auditoria #{nf.ultima_auditoria_id}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-[0.1em] text-zinc-500">
                Buscar
              </span>
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"
                  aria-hidden
                />
                <input
                  value={busca}
                  onChange={(e) => setBusca(e.target.value)}
                  placeholder="NF ou obra"
                  className="h-10 w-full rounded-lg border border-app-border bg-white pl-9 pr-3 text-sm text-zinc-900 shadow-sm placeholder:text-zinc-400 focus:border-brand-primary focus:outline-none focus:ring-2 focus:ring-brand-primary/20"
                />
              </div>
            </label>

            <div className="max-h-[460px] space-y-2 overflow-y-auto pr-1">
              {nfsQuery.isLoading && <ListaSkeleton />}
              {!nfsQuery.isLoading && auditoriasFiltradas.length === 0 && (
                <p className="rounded-lg border border-dashed border-zinc-200 px-3 py-4 text-sm text-zinc-500">
                  Nenhuma NF auditada encontrada.
                </p>
              )}
              {auditoriasFiltradas.map((nf) => {
                const selected = nf.ultima_auditoria_id === auditoriaId;
                return (
                  <button
                    key={nf.ultima_auditoria_id}
                    type="button"
                    onClick={() => selecionar(nf.ultima_auditoria_id as number)}
                    className={[
                      "w-full rounded-lg border px-3 py-3 text-left transition-colors",
                      selected
                        ? "border-brand-primary bg-brand-primary-light/70"
                        : "border-app-border bg-white hover:border-zinc-300 hover:bg-zinc-50",
                    ].join(" ")}
                  >
                    <span className="flex items-start justify-between gap-3">
                      <span className="min-w-0">
                        <span className="block text-sm font-semibold tabular text-zinc-950">
                          NF {nf.nota_fiscal}
                        </span>
                        <span className="mt-0.5 block truncate text-xs text-zinc-500">
                          {nf.nome_obra}
                        </span>
                      </span>
                      {nf.ultima_validacao && (
                        <StatusBadge status={nf.ultima_validacao} className="shrink-0" />
                      )}
                    </span>
                    <span className="mt-2 block text-xs tabular text-zinc-500">
                      {formatDateBR(nf.data_recebimento)} · {formatLitros(nf.qtd_litros, 0)}
                    </span>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="block space-y-1">
            <CardTitle>Conversa</CardTitle>
            <CardSubtitle>
              O assistente usa os dados, alertas e histórico da auditoria
              selecionada.
            </CardSubtitle>
          </CardHeader>
          <CardContent>
            {!auditoriaId && (
              <EstadoVazio />
            )}
            {auditoriaId && auditoriaQuery.isLoading && (
              <div className="space-y-3">
                <Skeleton className="h-7 w-48" />
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-10 w-36" />
              </div>
            )}
            {auditoriaId && auditoriaQuery.isError && (
              <div className="space-y-3 rounded-lg border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-800">
                <p className="font-semibold">Não foi possível carregar a auditoria.</p>
                <p>Selecione outra NF auditada ou tente novamente em instantes.</p>
              </div>
            )}
            {auditoria && (
              <div className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <ResumoItem label="NF atual" valor={`NF ${auditoria.nf_atual}`} />
                  <ResumoItem
                    label="NF anterior"
                    valor={
                      auditoria.nf_anterior.startsWith("CORTE:")
                        ? "Sem NF anterior"
                        : `NF ${auditoria.nf_anterior}`
                    }
                  />
                  <ResumoItem
                    label="Recebimento"
                    valor={formatDateBR(nfSelecionada?.data_recebimento)}
                  />
                  <ResumoItem
                    label="Valor da NF"
                    valor={formatBRL(nfSelecionada?.valor_total)}
                  />
                </div>
                <div className="rounded-lg border border-app-border bg-zinc-50 px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-zinc-950">
                        Auditoria #{auditoria.id}
                      </p>
                      <p className="mt-0.5 truncate text-sm text-zinc-500">
                        {auditoria.nome_obra}
                      </p>
                    </div>
                    <StatusBadge
                      status={auditoria.validacao_final}
                      aprovadaManualmente={Boolean(auditoria.aprovada_em)}
                    />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button onClick={() => setDrawerAberto(true)}>
                      <MessageSquare className="h-4 w-4" aria-hidden />
                      Abrir assistente
                    </Button>
                    <Link href={`/auditoria/${auditoria.id}`}>
                      <Button variant="secondary">Abrir auditoria</Button>
                    </Link>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {auditoria && (
        <AssistenteDrawer
          open={drawerAberto}
          onClose={() => setDrawerAberto(false)}
          auditoria={auditoria}
          perguntaInicial={perguntaInicial}
        />
      )}
    </div>
  );
}

function EstadoVazio() {
  return (
    <div className="flex min-h-64 items-center justify-center rounded-lg border border-dashed border-zinc-200 bg-zinc-50 px-4 py-8 text-center">
      <div className="max-w-md">
        <MessageSquare className="mx-auto h-8 w-8 text-brand-primary" aria-hidden />
        <h3 className="mt-3 text-base font-semibold text-zinc-950">
          Selecione uma auditoria
        </h3>
        <p className="mt-1 text-sm text-zinc-500">
          A conversa precisa de uma NF auditada para carregar contexto,
          perguntas sugeridas e histórico.
        </p>
      </div>
    </div>
  );
}

function ResumoItem({ label, valor }: { label: string; valor: string }) {
  return (
    <div className="rounded-lg border border-app-border bg-white px-3 py-3">
      <p className="text-xs font-medium text-zinc-500">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold tabular text-zinc-950">
        {valor}
      </p>
    </div>
  );
}

function PageSkeleton() {
  return (
    <div className="mx-auto max-w-[1300px] space-y-6">
      <Skeleton className="h-16 w-full" />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(320px,420px)_1fr]">
        <Skeleton className="h-[620px] w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    </div>
  );
}

function ListaSkeleton() {
  return (
    <>
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-20 w-full" />
    </>
  );
}

function parseAuditoriaId(raw: string | null): number | null {
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function filtrarAuditorias(nfs: NFListItem[], busca: string): NFListItem[] {
  const termo = busca.trim().toLowerCase();
  if (!termo) return nfs;
  return nfs.filter((nf) => {
    return (
      nf.nota_fiscal.toLowerCase().includes(termo) ||
      nf.nome_obra.toLowerCase().includes(termo)
    );
  });
}
