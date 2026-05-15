"use client";

import * as React from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { AlertaItem } from "./alerta-item";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FilterTabs } from "@/components/ui/filter-tabs";

import {
  ALERTA_TIPO_BADGE_VARIANT,
  ALERTA_TIPO_COUNT_CLASS,
  ALERTA_TIPO_LABEL,
} from "@/lib/alertas";
import { formatBRL } from "@/lib/format";
import { useAuditoriaStore } from "@/stores/auditoria-store";
import type { Alerta, SeveridadeAlerta, TipoAlerta } from "@/lib/types";

interface Props {
  alertas: Alerta[];
  onReconciliar: (abastecimentoId: number) => void;
}

const ORDEM_SEV: Record<SeveridadeAlerta, number> = { alta: 0, media: 1, baixa: 2 };
const SEV_BADGE_VARIANT: Record<SeveridadeAlerta, "danger" | "warn" | "info"> = {
  alta: "danger",
  media: "warn",
  baixa: "info",
};

type FiltroTipoAlerta = "TODOS" | TipoAlerta;

const FILTROS: Array<{ value: FiltroTipoAlerta; label: string }> = [
  { value: "TODOS", label: "Todos" },
  { value: "NAO_CADASTRADO", label: ALERTA_TIPO_LABEL.NAO_CADASTRADO },
  { value: "POS_DESMOB", label: ALERTA_TIPO_LABEL.POS_DESMOB },
  { value: "OUTLIER", label: ALERTA_TIPO_LABEL.OUTLIER },
  { value: "DUPLICIDADE", label: ALERTA_TIPO_LABEL.DUPLICIDADE },
];

const PAGE_SIZE = 8;

// ---------------------------------------------------------------------------
// Agrupamento
// ---------------------------------------------------------------------------

interface GrupoData {
  key: string;
  tipo: TipoAlerta;
  severidade: SeveridadeAlerta;
  veiculo: string | null;
  alertas: Alerta[];
  totalImpacto: number | null;
}

function veiculoDaAlerta(a: Alerta): string | null {
  return (
    (a.payload.veiculo_raw as string | undefined) ??
    (a.payload.veiculo_normalizado as string | undefined) ??
    null
  );
}

function buildGrupos(alertas: Alerta[]): GrupoData[] {
  const map = new Map<string, GrupoData>();
  for (const a of alertas) {
    const veiculo = veiculoDaAlerta(a);
    const key = `${a.tipo}||${veiculo ?? String(a.id)}`;
    if (!map.has(key)) {
      map.set(key, { key, tipo: a.tipo, severidade: a.severidade, veiculo, alertas: [], totalImpacto: null });
    }
    const g = map.get(key)!;
    g.alertas.push(a);
    if (ORDEM_SEV[a.severidade] < ORDEM_SEV[g.severidade]) g.severidade = a.severidade;
    if (a.impacto_financeiro != null) g.totalImpacto = (g.totalImpacto ?? 0) + a.impacto_financeiro;
  }
  return Array.from(map.values());
}

// ---------------------------------------------------------------------------
// Componente de grupo
// ---------------------------------------------------------------------------

function AlertaGrupo({ grupo, onReconciliar }: { grupo: GrupoData; onReconciliar: (id: number) => void }) {
  const defaultExpanded = grupo.severidade !== "baixa";
  const [expanded, setExpanded] = React.useState(defaultExpanded);

  if (grupo.alertas.length === 1) {
    return <AlertaItem alerta={grupo.alertas[0]} onReconciliar={onReconciliar} />;
  }

  return (
    <div className="rounded-xl border border-app-border bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex w-full items-start justify-between gap-3 px-3 py-2.5 text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <Badge variant={SEV_BADGE_VARIANT[grupo.severidade]}>{grupo.severidade}</Badge>
            <Badge variant={ALERTA_TIPO_BADGE_VARIANT[grupo.tipo]}>
              {ALERTA_TIPO_LABEL[grupo.tipo]}
            </Badge>
            <span className="rounded-full bg-zinc-100 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-zinc-600">
              {grupo.alertas.length}×
            </span>
          </div>
          <p className="truncate text-sm font-semibold text-zinc-950">
            {grupo.veiculo ?? ALERTA_TIPO_LABEL[grupo.tipo]} — {grupo.alertas.length} ocorrências
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          {grupo.totalImpacto != null && (
            <span className="tabular text-sm font-semibold text-zinc-950">
              {formatBRL(grupo.totalImpacto)}
            </span>
          )}
          {expanded
            ? <ChevronUp className="h-3.5 w-3.5 text-zinc-500" aria-hidden />
            : <ChevronDown className="h-3.5 w-3.5 text-zinc-500" aria-hidden />}
        </div>
      </button>
      {expanded && (
        <div className="space-y-1.5 border-t border-zinc-100 px-2 pb-2 pt-1.5">
          {grupo.alertas.map((a) => (
            <AlertaItem key={a.id} alerta={a} onReconciliar={onReconciliar} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Lista principal
// ---------------------------------------------------------------------------

export function AlertasList({ alertas, onReconciliar }: Props) {
  const filtroTipo = useAuditoriaStore((s) => s.alertaFiltroTipo);
  const setFiltroTipo = useAuditoriaStore((s) => s.setAlertaFiltroTipo);
  const ordenacao = useAuditoriaStore((s) => s.alertaOrdenacao);
  const setOrdenacao = useAuditoriaStore((s) => s.setAlertaOrdenacao);
  const paginaKey = `${filtroTipo}:${ordenacao}`;
  const [paginacao, setPaginacao] = React.useState({ key: paginaKey, pagina: 1 });
  const pagina = paginacao.key === paginaKey ? paginacao.pagina : 1;

  const visiveis = React.useMemo(() => {
    let arr = [...alertas];
    if (filtroTipo !== "TODOS") arr = arr.filter((a) => a.tipo === filtroTipo);
    arr.sort((a, b) => {
      if (ordenacao === "severidade") {
        const dif = ORDEM_SEV[a.severidade] - ORDEM_SEV[b.severidade];
        if (dif !== 0) return dif;
        return (b.impacto_financeiro ?? 0) - (a.impacto_financeiro ?? 0);
      }
      return (b.impacto_financeiro ?? 0) - (a.impacto_financeiro ?? 0);
    });
    return arr;
  }, [alertas, filtroTipo, ordenacao]);

  const grupos = React.useMemo(() => buildGrupos(visiveis), [visiveis]);
  const gruposVisiveis = grupos.slice(0, pagina * PAGE_SIZE);
  const restantes = grupos.length - pagina * PAGE_SIZE;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Alertas detectados ({alertas.length})</CardTitle>
          <p className="mt-1 text-sm text-zinc-500">
            Disparados por checagens determinísticas no engine; reconciliação usa IA.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="h-9 rounded-lg border border-app-border bg-white px-3 text-xs font-medium text-zinc-700 shadow-sm focus:outline-none focus:border-brand-primary focus:ring-2 focus:ring-brand-primary/20"
            value={ordenacao}
            onChange={(e) => setOrdenacao(e.target.value as "severidade" | "impacto")}
          >
            <option value="severidade">Ordem: severidade</option>
            <option value="impacto">Ordem: impacto financeiro</option>
          </select>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <FilterTabs
          compact
          value={filtroTipo}
          onChange={setFiltroTipo}
          label="Filtro por tipo de alerta"
          options={FILTROS.map((f) => ({
            value: f.value,
            label: f.label,
            count:
              f.value === "TODOS"
                ? alertas.length
                : alertas.filter((a) => a.tipo === f.value).length,
            countClassName:
              f.value === "TODOS" ? undefined : ALERTA_TIPO_COUNT_CLASS[f.value],
          }))}
        />
        {grupos.length === 0 ? (
          <p className="text-sm text-zinc-500">Nenhum alerta nesta categoria.</p>
        ) : (
          <>
            {grupos.length !== visiveis.length && (
              <p className="text-xs text-zinc-400">
                {grupos.length} grupo{grupos.length !== 1 ? "s" : ""} de alertas ({visiveis.length} ocorrências)
              </p>
            )}
            <div className="space-y-1.5">
              {gruposVisiveis.map((g) => (
                <AlertaGrupo key={g.key} grupo={g} onReconciliar={onReconciliar} />
              ))}
            </div>
            {restantes > 0 && (
              <button
                type="button"
                onClick={() => setPaginacao({ key: paginaKey, pagina: pagina + 1 })}
                className="w-full rounded-lg border border-dashed border-zinc-300 py-2 text-sm text-zinc-500 transition-colors hover:border-zinc-400 hover:text-zinc-700"
              >
                Ver mais {Math.min(PAGE_SIZE, restantes)} grupo{Math.min(PAGE_SIZE, restantes) !== 1 ? "s" : ""}
              </button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
