"use client";

import { AlertTriangle, FileText, Fuel, Truck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import type { MetricTone } from "@/components/ui/metric-card";
import { Skeleton } from "@/components/ui/skeleton";

import { useStats } from "@/hooks/use-nfs";
import { formatBRL, formatDateBR, formatLitros, formatNumero } from "@/lib/format";

interface StatTile {
  label: string;
  value: string;
  hint?: string;
  tone: MetricTone;
  icon: LucideIcon;
  tooltip?: string;
}

export function StatsCards() {
  const { data, isLoading, isError } = useStats();

  let tiles: StatTile[] = [];
  if (data) {
    const periodoAb =
      data.periodo_inicio && data.periodo_fim
        ? `${formatDateBR(data.periodo_inicio)} a ${formatDateBR(data.periodo_fim)}`
        : null;
    const periodoNfs =
      data.periodo_nfs_inicio && data.periodo_nfs_fim
        ? `${formatDateBR(data.periodo_nfs_inicio)} a ${formatDateBR(data.periodo_nfs_fim)}`
        : null;
    const tooltipAb = periodoAb
      ? `Janela coberta pelos registros de abastecimento do Infleet (${periodoAb}). Pode diferir do período das NFs.`
      : "Janela coberta pelos registros de abastecimento do Infleet.";
    const tooltipNfs = periodoNfs
      ? `Janela coberta pelas datas de recebimento das NFs (${periodoNfs}). Pode diferir do período de abastecimentos.`
      : "Janela coberta pelas datas de recebimento das NFs.";
    tiles = [
      {
        label: "Total abastecido",
        value: formatLitros(data.total_litros, 0),
        hint: `${formatNumero(data.total_abastecimentos)} abastecimentos · ${formatBRL(data.total_custo_brl)}`,
        tone: "info",
        icon: Fuel,
        tooltip: tooltipAb,
      },
      {
        label: "Custo com equipamentos não cadastrados",
        value: `${formatNumero(data.pct_custo_nao_cadastrado, 2)}%`,
        hint: `${formatBRL(data.custo_nao_cadastrado_brl)} em ${formatNumero(data.abastecimentos_nao_cadastrados)} abastecimentos`,
        tone: "danger",
        icon: AlertTriangle,
        tooltip: tooltipAb,
      },
      {
        label: "NFs no período",
        value: formatNumero(data.total_nfs),
        hint: periodoNfs ?? "-",
        tone: "info",
        icon: FileText,
        tooltip: tooltipNfs,
      },
      {
        label: "Equipamentos cadastrados",
        value: formatNumero(data.mobilizados_ativos),
        hint: `${formatNumero(data.total_mobilizados)} no total · ${formatNumero(data.veiculos_distintos_infleet)} veículos no Infleet`,
        tone: "neutral",
        icon: Truck,
        tooltip:
          "Ativos: equipamentos com situação MOBILIZADO. Total: todo o cadastro. Veículos no Infleet: placas distintas que apareceram em algum abastecimento.",
      },
    ];
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {isLoading
        ? Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="min-h-[150px] space-y-4 px-5 py-5">
                <Skeleton className="h-4 w-36" />
                <Skeleton className="h-10 w-28" />
                <Skeleton className="h-4 w-44" />
              </CardContent>
            </Card>
          ))
        : isError
          ? (
            <Card className="col-span-full">
              <CardContent className="text-sm text-red-700">
                Não foi possível carregar as estatísticas. Tente novamente em
                instantes.
              </CardContent>
            </Card>
          )
          : tiles.map((t) => (
              <MetricCard
                key={t.label}
                label={t.label}
                value={t.value}
                hint={t.hint}
                icon={t.icon}
                tone={t.tone}
                tooltip={t.tooltip}
              />
            ))}
    </div>
  );
}
