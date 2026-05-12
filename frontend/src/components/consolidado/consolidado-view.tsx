"use client";

import * as React from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Download,
  FileWarning,
  Scale,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { FilterTabs } from "@/components/ui/filter-tabs";
import { MetricCard } from "@/components/ui/metric-card";
import type { MetricTone } from "@/components/ui/metric-card";
import { SearchInput } from "@/components/ui/search-input";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/dashboard/status-badge";

import { api } from "@/lib/api";
import { ALERTA_TIPO_BADGE_VARIANT, ALERTA_TIPO_LABEL } from "@/lib/alertas";
import { useConsolidado } from "@/hooks/use-consolidado";
import { cn } from "@/lib/utils";
import { formatBRL, formatDateBR, formatLitros, formatNomeObra, formatNumero, formatPct } from "@/lib/format";
import type { NFConsolidadoItem, ValidacaoFinal } from "@/lib/types";

type FiltroStatus = "todas" | "APROVADO" | "INCONSISTENTE" | "NAO_AUDITADA";

type SortKey =
  | "nota_fiscal"
  | "data_recebimento"
  | "qtd_litros"
  | "valor_total"
  | "diferenca_percentual"
  | "qtd_alertas";

export function ConsolidadoView() {
  const { data, isLoading, isError } = useConsolidado();
  const [filtro, setFiltro] = React.useState<FiltroStatus>("todas");
  const [busca, setBusca] = React.useState("");
  const [sortKey, setSortKey] = React.useState<SortKey>("data_recebimento");
  const [sortAsc, setSortAsc] = React.useState(true);

  const items = React.useMemo<NFConsolidadoItem[]>(() => {
    if (!data) return [];
    let list = data.items.slice();
    if (filtro !== "todas") {
      list = list.filter((i) => {
        const status: FiltroStatus = i.validacao_final ?? "NAO_AUDITADA";
        return status === filtro;
      });
    }
    if (busca.trim()) {
      const q = busca.trim().toLowerCase();
      list = list.filter(
        (i) =>
          i.nota_fiscal.toLowerCase().includes(q) ||
          i.nome_obra.toLowerCase().includes(q),
      );
    }
    list.sort((a, b) => {
      const va = a[sortKey] as number | string | null;
      const vb = b[sortKey] as number | string | null;
      const av = va ?? "";
      const bv = vb ?? "";
      if (av < bv) return sortAsc ? -1 : 1;
      if (av > bv) return sortAsc ? 1 : -1;
      return 0;
    });
    return list;
  }, [data, filtro, busca, sortKey, sortAsc]);

  const periodo =
    data?.periodo_inicio && data?.periodo_fim
      ? `${formatDateBR(data.periodo_inicio)} a ${formatDateBR(data.periodo_fim)}`
      : "-";

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc((v) => !v);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  return (
    <>
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
          Controle consolidado
        </p>
        <h2 className="mt-1 text-[26px] font-bold tracking-tight text-zinc-950">
          Visão consolidada
        </h2>
        <p className="mt-1 text-[16px] text-zinc-500">
          Período das NFs recebidas: {periodo}
        </p>
      </header>

      <StatsConsolidadoCards />

      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 px-5 py-4">
            <FiltroChips ativo={filtro} onChange={setFiltro} totals={data ?? null} />
            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
              <SearchInput
                className="w-full sm:w-64"
                label="Buscar por NF ou obra"
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Buscar por NF ou obra"
              />
              <a
                href={api.csvConsolidadoUrl()}
                download
                className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-app-border bg-white px-3 text-sm font-semibold text-zinc-900 shadow-sm transition-colors hover:bg-zinc-50 hover:border-zinc-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary/25"
              >
                <Download className="h-3.5 w-3.5" aria-hidden />
                Exportar CSV
              </a>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[1080px] text-sm">
              <caption className="sr-only">
                Lista consolidada das NFs auditadas, com diferença, alertas e status.
              </caption>
              <thead>
                <tr className="border-b border-app-border bg-zinc-50/90 text-zinc-500">
                  <Th onClick={() => toggleSort("nota_fiscal")} active={sortKey === "nota_fiscal"} asc={sortAsc}>NF</Th>
                  <Th onClick={() => toggleSort("data_recebimento")} active={sortKey === "data_recebimento"} asc={sortAsc}>DATA</Th>
                  <th scope="col" className="th-base text-center">OBRA</th>
                  <Th onClick={() => toggleSort("qtd_litros")} active={sortKey === "qtd_litros"} asc={sortAsc}>QUANTIDADE</Th>
                  <Th onClick={() => toggleSort("valor_total")} active={sortKey === "valor_total"} asc={sortAsc}>VALOR</Th>
                  <Th onClick={() => toggleSort("diferenca_percentual")} active={sortKey === "diferenca_percentual"} asc={sortAsc}>DIFERENÇA</Th>
                  <Th onClick={() => toggleSort("qtd_alertas")} active={sortKey === "qtd_alertas"} asc={sortAsc}>ALERTAS</Th>
                  <th scope="col" className="th-base text-center">STATUS</th>
                  <th scope="col" className="th-base text-center">AÇÕES</th>
                </tr>
              </thead>
              <tbody>
                {isLoading &&
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i} className="border-b border-zinc-100">
                      <td colSpan={9} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>
                    </tr>
                  ))}
                {isError && (
                  <tr><td colSpan={9} className="px-4 py-6 text-center text-sm text-red-700">Não foi possível carregar a visão consolidada.</td></tr>
                )}
                {!isLoading && items.length === 0 && (
                  <tr><td colSpan={9} className="px-4 py-6 text-center text-sm text-zinc-500">Nenhuma NF corresponde ao filtro atual.</td></tr>
                )}
                {items.map((it) => {
                  const clickable = it.auditoria_id !== null;
                  const RowEl = clickable ? "tr" : "tr";
                  return (
                    <RowEl
                      key={it.nota_fiscal}
                      className={cn(
                        "border-b border-zinc-100",
                        clickable && "transition-colors hover:bg-brand-primary-light/35",
                      )}
                    >
                      <td className="td-base text-center font-semibold tabular text-zinc-950">{it.nota_fiscal}</td>
                      <td className="td-base text-center tabular text-zinc-700">{formatDateBR(it.data_recebimento)}</td>
                      <td className="td-base max-w-[20rem] truncate text-center text-zinc-700" title={formatNomeObra(it.nome_obra)}>{formatNomeObra(it.nome_obra)}</td>
                      <td className="td-base text-center tabular text-zinc-700">{formatLitros(it.qtd_litros, 0)}</td>
                      <td className="td-base text-center tabular text-zinc-700">{formatBRL(it.valor_total)}</td>
                      <td className="td-base text-center tabular">
                        {it.diferenca_percentual !== null
                          ? <span className={cn("font-medium", Math.abs(it.diferenca_percentual) >= 0.02 ? "text-red-700" : "text-zinc-700")}>{formatPct(it.diferenca_percentual)}</span>
                          : <span className="text-zinc-400">-</span>}
                      </td>
                      <td className="td-base text-center">
                        <div className="flex flex-wrap items-center justify-center gap-1">
                          {it.alertas.length === 0 && <span className="text-zinc-400">-</span>}
                          {it.alertas.map((a) => (
                            <Badge
                              key={a.tipo}
                              variant={ALERTA_TIPO_BADGE_VARIANT[a.tipo]}
                              title={`${ALERTA_TIPO_LABEL[a.tipo]} · severidade ${a.severidade}`}
                            >
                              {ALERTA_TIPO_LABEL[a.tipo]} <span className="font-mono">{a.qtd}</span>
                            </Badge>
                          ))}
                        </div>
                      </td>
                      <td className="td-base text-center">
                        <div className="flex justify-center">
                          <StatusBadge status={it.validacao_final as ValidacaoFinal | null} />
                        </div>
                      </td>
                      <td className="td-base text-center">
                        {it.auditoria_id !== null ? (
                          <Link
                            href={`/auditoria/${it.auditoria_id}`}
                            className="inline-flex h-8 items-center rounded-lg px-3 text-sm font-semibold text-brand-primary-dark transition-colors hover:bg-brand-primary-light hover:text-brand-primary-dark"
                          >
                            Abrir
                          </Link>
                        ) : (
                          <span className="text-sm text-zinc-400">Sem auditoria</span>
                        )}
                      </td>
                    </RowEl>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </>
  );
}

function Th({
  children,
  onClick,
  active,
  asc,
  align = "center",
}: {
  children: React.ReactNode;
  onClick: () => void;
  active: boolean;
  asc: boolean;
  align?: "left" | "right" | "center";
}) {
  const alignClass =
    align === "right"
      ? "text-right"
      : align === "center"
        ? "text-center"
        : "text-left";
  return (
    <th scope="col" className={cn("th-base", alignClass)}>
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "inline-flex w-full items-center justify-center gap-1 transition-colors hover:text-zinc-900",
          active && "text-zinc-800",
        )}
      >
        {children}
        {active && <span aria-hidden>{asc ? "↑" : "↓"}</span>}
      </button>
    </th>
  );
}

function FiltroChips({
  ativo,
  onChange,
  totals,
}: {
  ativo: FiltroStatus;
  onChange: (v: FiltroStatus) => void;
  totals: { qtd_aprovadas: number; qtd_inconsistentes: number; qtd_nao_auditadas: number; items: { length: number } } | null;
}) {
  const opts: { key: FiltroStatus; label: string; count: number | undefined }[] = [
    { key: "todas", label: "Todas", count: totals?.items.length },
    { key: "APROVADO", label: "Aprovadas", count: totals?.qtd_aprovadas },
    { key: "INCONSISTENTE", label: "Inconsistentes", count: totals?.qtd_inconsistentes },
    { key: "NAO_AUDITADA", label: "Não auditadas", count: totals?.qtd_nao_auditadas },
  ];
  return (
    <FilterTabs
      value={ativo}
      options={opts.map((o) => ({ value: o.key, label: o.label, count: o.count }))}
      onChange={onChange}
      label="Filtro por status"
    />
  );
}

function StatsConsolidadoCards() {
  const { data, isLoading } = useConsolidado();

  const tiles: {
    label: string;
    value: string;
    hint?: string;
    tone: MetricTone;
    icon: LucideIcon;
  }[] = data
    ? [
        {
          label: "Total auditado",
          value: formatBRL(data.total_auditado_brl),
          hint: `${data.items.length} NF${data.items.length === 1 ? "" : "s"} no período`,
          tone: "info",
          icon: ClipboardList,
        },
        {
          label: "Divergência total detectada",
          value: formatLitros(data.diferenca_total_litros, 0),
          hint: formatBRL(data.diferenca_total_brl),
          tone: Math.abs(data.diferenca_total_brl) > 0 ? "danger" : "success",
          icon: Scale,
        },
        {
          label: "Alertas gerados",
          value: formatNumero(data.total_alertas),
          hint: "Alta + Média + Baixa severidade",
          tone: data.total_alertas > 0 ? "warn" : "success",
          icon: AlertTriangle,
        },
        {
          label: "NFs aprovadas",
          value: `${data.qtd_aprovadas} / ${data.items.length}`,
          hint:
            data.items.length > 0
              ? `${formatNumero((data.qtd_aprovadas / data.items.length) * 100, 0)}%`
              : "-",
          tone: "success",
          icon: CheckCircle2,
        },
        {
          label: "NFs inconsistentes",
          value: `${data.qtd_inconsistentes} / ${data.items.length}`,
          hint:
            data.items.length > 0
              ? `${formatNumero((data.qtd_inconsistentes / data.items.length) * 100, 0)}%`
              : "-",
          tone: data.qtd_inconsistentes > 0 ? "danger" : "neutral",
          icon: FileWarning,
        },
        {
          label: "Reconciliações pendentes",
          value: formatNumero(data.qtd_reconciliacoes_pendentes),
          hint: "Equipamentos não cadastrados ainda não tratados",
          tone: data.qtd_reconciliacoes_pendentes > 0 ? "warn" : "success",
          icon: Activity,
        },
      ]
    : [];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {isLoading
        ? Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="min-h-[150px] space-y-4 px-5 py-5">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-10 w-28" />
                <Skeleton className="h-4 w-40" />
              </CardContent>
            </Card>
          ))
        : tiles.map((t) => (
            <MetricCard
              key={t.label}
              label={t.label}
              value={t.value}
              hint={t.hint}
              icon={t.icon}
              tone={t.tone}
            />
          ))}
    </div>
  );
}
