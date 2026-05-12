"use client";

import * as React from "react";

import { AlertaItem } from "./alerta-item";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FilterTabs } from "@/components/ui/filter-tabs";

import { ALERTA_TIPO_COUNT_CLASS, ALERTA_TIPO_LABEL } from "@/lib/alertas";
import { useAuditoriaStore } from "@/stores/auditoria-store";
import type { Alerta, SeveridadeAlerta, TipoAlerta } from "@/lib/types";

interface Props {
  alertas: Alerta[];
  onReconciliar: (abastecimentoId: number) => void;
}

const ORDEM_SEV: Record<SeveridadeAlerta, number> = { alta: 0, media: 1, baixa: 2 };
type FiltroTipoAlerta = "TODOS" | TipoAlerta;

const FILTROS: Array<{
  value: FiltroTipoAlerta;
  label: string;
}> = [
  { value: "TODOS", label: "Todos" },
  { value: "NAO_CADASTRADO", label: ALERTA_TIPO_LABEL.NAO_CADASTRADO },
  { value: "POS_DESMOB", label: ALERTA_TIPO_LABEL.POS_DESMOB },
  { value: "OUTLIER", label: ALERTA_TIPO_LABEL.OUTLIER },
  { value: "DUPLICIDADE", label: ALERTA_TIPO_LABEL.DUPLICIDADE },
];

export function AlertasList({ alertas, onReconciliar }: Props) {
  const filtroTipo = useAuditoriaStore((s) => s.alertaFiltroTipo);
  const setFiltroTipo = useAuditoriaStore((s) => s.setAlertaFiltroTipo);
  const ordenacao = useAuditoriaStore((s) => s.alertaOrdenacao);
  const setOrdenacao = useAuditoriaStore((s) => s.setAlertaOrdenacao);

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
        {visiveis.length === 0 ? (
          <p className="text-sm text-zinc-500">Nenhum alerta nesta categoria.</p>
        ) : (
          <div className="space-y-1.5">
            {visiveis.map((a) => (
              <AlertaItem key={a.id} alerta={a} onReconciliar={onReconciliar} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
