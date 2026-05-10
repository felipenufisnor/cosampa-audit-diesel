"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { formatBRL, formatLitros, formatPct } from "@/lib/format";
import type { AuditoriaIndicadores } from "@/lib/types";

interface Props {
  ind: AuditoriaIndicadores;
}

/**
 * Replica o layout da aba `AUDITORIA DO DIESEL_0` da planilha original:
 * duas colunas (NF anterior | NF atual) com estoques antes/apos
 * descarregamento + bloco de saidas teorica/registrada/diferenca.
 */
export function IndicadoresCard({ ind }: Props) {
  const linhasNF = [
    { label: "Estoque inicial (tanque + comboio)", anterior: ind.estoque_inicial_anterior, atual: ind.estoque_inicial_atual },
    { label: "Quantidade descarregada (NF)", anterior: ind.quantidade_descarregada_anterior, atual: undefined },
    {
      label: "Estoque após descarregamento (teórico)",
      anterior: ind.estoque_final_teorico_anterior,
      atual: undefined,
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Indicadores do §4 (auditoria do diesel)</CardTitle>
        <p className="text-sm text-zinc-500">
          Replica a aba &laquo;Auditoria do Diesel&raquo; da planilha. Valores em litros e em R$.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="overflow-hidden rounded-xl border border-app-border">
          <div className="grid grid-cols-[1.6fr_1fr_1fr] border-b border-app-border bg-zinc-50 text-[11px] font-bold uppercase tracking-[0.08em] text-zinc-500">
            <div className="px-4 py-3">Item</div>
            <div className="px-4 py-3 text-right">NF {ind.nf_anterior}</div>
            <div className="px-4 py-3 text-right">NF {ind.nf_atual}</div>
          </div>
          {linhasNF.map((l) => (
            <div
              key={l.label}
              className="grid grid-cols-[1.6fr_1fr_1fr] border-b border-zinc-100 transition-colors last:border-b-0 hover:bg-brand-primary-light/30"
            >
              <div className="px-4 py-3 text-sm text-zinc-700">{l.label}</div>
              <div className="px-4 py-3 text-right tabular text-sm font-medium text-zinc-950">
                {formatLitros(l.anterior)}
              </div>
              <div className="px-4 py-3 text-right tabular text-sm font-medium text-zinc-950">
                {l.atual !== undefined ? formatLitros(l.atual) : "-"}
              </div>
            </div>
          ))}
        </div>

        <Separator />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
          <Linha label="Saída teórica" value={formatLitros(ind.saida_teorica_litros)} />
          <Linha label="Saídas registradas (Infleet)" value={formatLitros(ind.saidas_registradas_litros)} />
          <Linha label="Saídas registradas (custo)" value={formatBRL(ind.saidas_registradas_custo)} />
          <Linha
            label="Diferença (litros)"
            value={formatLitros(ind.diferenca_litros)}
            emphasis={Math.abs(ind.diferenca_percentual) >= 0.02 ? "danger" : undefined}
          />
          <Linha
            label="Diferença (%)"
            value={formatPct(ind.diferenca_percentual)}
            emphasis={Math.abs(ind.diferenca_percentual) >= 0.02 ? "danger" : undefined}
          />
          <Linha
            label="Equipamentos não cadastrados"
            value={String(ind.qtd_equipamentos_nao_cadastrados)}
            emphasis={ind.qtd_equipamentos_nao_cadastrados > 0 ? "danger" : undefined}
          />
        </div>
      </CardContent>
    </Card>
  );
}

function Linha({
  label,
  value,
  emphasis,
}: {
  label: string;
  value: string;
  emphasis?: "danger";
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-dotted border-zinc-200 pb-2">
      <span className="text-xs text-zinc-500">{label}</span>
      <span
        className={`tabular text-sm font-semibold ${
          emphasis === "danger" ? "text-red-700" : "text-zinc-950"
        }`}
      >
        {value}
      </span>
    </div>
  );
}
