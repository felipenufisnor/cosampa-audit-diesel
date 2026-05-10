"use client";

import { AlertTriangle, FileText, Fuel, Truck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { Skeleton } from "@/components/ui/skeleton";

import { useStats } from "@/hooks/use-nfs";
import { formatBRL, formatDateBR, formatLitros, formatNumero } from "@/lib/format";

interface StatTile {
  label: string;
  value: string;
  hint?: string;
  tone: "success" | "danger" | "info" | "neutral";
  icon: LucideIcon;
}

export function StatsCards() {
  const { data, isLoading, isError } = useStats();

  let tiles: StatTile[] = [];
  if (data) {
    const periodo =
      data.periodo_inicio && data.periodo_fim
        ? `${formatDateBR(data.periodo_inicio)} - ${formatDateBR(data.periodo_fim)}`
        : "-";
    tiles = [
      {
        label: "Total abastecido",
        value: formatLitros(data.total_litros, 0),
        hint: `${formatNumero(data.total_abastecimentos)} abastecimentos · ${formatBRL(data.total_custo_brl)}`,
        tone: "success",
        icon: Fuel,
      },
      {
        label: "Custo em abastecimentos não cadastrados",
        value: `${formatNumero(data.pct_custo_nao_cadastrado, 2)}%`,
        hint: `${formatBRL(data.custo_nao_cadastrado_brl)} em ${formatNumero(data.abastecimentos_nao_cadastrados)} abastecimentos`,
        tone: "danger",
        icon: AlertTriangle,
      },
      {
        label: "NFs no período",
        value: formatNumero(data.total_nfs),
        hint: periodo,
        tone: "info",
        icon: FileText,
      },
      {
        label: "Equipamentos cadastrados",
        value: formatNumero(data.mobilizados_ativos),
        hint: `${formatNumero(data.total_mobilizados)} no total · ${formatNumero(data.veiculos_distintos_infleet)} veículos no Infleet`,
        tone: "neutral",
        icon: Truck,
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
              />
            ))}
    </div>
  );
}
