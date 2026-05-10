"use client";

import * as React from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatBRL, formatDateBR, formatLitros } from "@/lib/format";
import { cn } from "@/lib/utils";

import type { Alerta, SeveridadeAlerta, TipoAlerta } from "@/lib/types";

const SEVERIDADE_VARIANT: Record<SeveridadeAlerta, "danger" | "warn" | "info"> = {
  alta: "danger",
  media: "warn",
  baixa: "info",
};

const TIPO_LABEL: Record<TipoAlerta, string> = {
  NAO_CADASTRADO: "Não cadastrado",
  POS_DESMOB: "Pós-desmobilização",
  OUTLIER: "Outlier de consumo",
  DUPLICIDADE: "Duplicidade",
};

interface Props {
  alerta: Alerta;
  onReconciliar?: (abastecimentoId: number) => void;
}

export function AlertaItem({ alerta, onReconciliar }: Props) {
  const [expand, setExpand] = React.useState(false);
  return (
    <div className="rounded-xl border border-app-border bg-white shadow-sm transition-colors hover:border-zinc-300">
      <div className="flex items-start justify-between gap-3 px-3 py-2.5">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge variant={SEVERIDADE_VARIANT[alerta.severidade]}>
              {alerta.severidade}
            </Badge>
            <span className="text-[11px] uppercase tracking-wide text-zinc-500">
              {TIPO_LABEL[alerta.tipo]}
            </span>
          </div>
          <p className="truncate text-sm font-semibold text-zinc-950">{alerta.titulo}</p>
          <p className="mt-0.5 text-xs text-zinc-600 line-clamp-2">{alerta.descricao}</p>
        </div>
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          {alerta.impacto_financeiro != null && (
            <span className="tabular text-sm font-semibold text-zinc-950">
              {formatBRL(alerta.impacto_financeiro)}
            </span>
          )}
          <div className="flex items-center gap-1">
            {alerta.tipo === "NAO_CADASTRADO" && alerta.abastecimento_id && onReconciliar && (
              <Button
                size="sm"
                variant="primary"
                className="bg-brand-sidebar text-brand-primary-dark hover:bg-brand-sidebar/90 focus-visible:ring-brand-sidebar/35"
                onClick={() => onReconciliar(alerta.abastecimento_id as number)}
              >
                Reconciliar
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setExpand((v) => !v)}
              aria-expanded={expand}
              aria-label={expand ? "Recolher detalhes" : "Expandir detalhes"}
            >
              {expand ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            </Button>
          </div>
        </div>
      </div>
      <div
        className={cn(
          "border-t border-zinc-100 bg-zinc-50/70 px-3 py-2",
          !expand && "hidden",
        )}
      >
        <AlertaPayload alerta={alerta} />
      </div>
    </div>
  );
}

function AlertaPayload({ alerta }: { alerta: Alerta }) {
  if (alerta.tipo === "POS_DESMOB") {
    return <PosDesmobDetalhes payload={alerta.payload} />;
  }
  return <PayloadGenerico payload={alerta.payload} />;
}

function PosDesmobDetalhes({ payload }: { payload: Record<string, unknown> }) {
  const veiculo = (payload.veiculo_raw as string | undefined) ?? "-";
  const dataDesmob = payload.data_desmobilizacao as string | undefined;
  const dataAbast = payload.data_abastecimento as string | undefined;
  const deltaDias = (payload.delta_dias as number | undefined) ?? null;
  const litros = (payload.quantidade_litros as number | undefined) ?? null;

  return (
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
      <Linha label="Veículo" value={veiculo} mono />
      <Linha
        label="Data da desmobilização"
        value={dataDesmob ? formatDateBR(dataDesmob.slice(0, 10)) : "-"}
      />
      <Linha
        label="Data do abastecimento"
        value={dataAbast ? formatDateBR(dataAbast.slice(0, 10)) : "-"}
      />
      <Linha
        label="Diferença"
        value={deltaDias !== null ? `${deltaDias} dia${deltaDias === 1 ? "" : "s"}` : "-"}
      />
      <Linha
        label="Quantidade abastecida"
        value={litros !== null ? formatLitros(litros) : "-"}
      />
    </dl>
  );
}

function Linha({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between gap-2 border-b border-dotted border-zinc-200 pb-1 last:border-b-0">
      <dt className="text-zinc-500">{label}</dt>
      <dd
        className={cn(
          "text-zinc-800 text-right",
          mono ? "font-mono tabular" : "tabular",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function PayloadGenerico({ payload }: { payload: Record<string, unknown> }) {
  const entradas = Object.entries(payload);
  if (entradas.length === 0) {
    return <p className="text-xs text-zinc-500">Sem detalhes adicionais.</p>;
  }
  return (
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
      {entradas.map(([k, v]) => (
        <div
          key={k}
          className="flex justify-between gap-2 border-b border-dotted border-zinc-200 pb-1 last:border-b-0"
        >
          <dt className="text-zinc-500">{k}</dt>
          <dd className="text-zinc-800 font-mono break-all text-right">
            {formatValor(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function formatValor(v: unknown): string {
  if (v === null || v === undefined) return "-";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
