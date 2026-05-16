"use client";

import { AlertTriangle, FileText, Fuel, Truck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import type { MetricTone } from "@/components/ui/metric-card";
import { Skeleton } from "@/components/ui/skeleton";

import { useStats } from "@/hooks/use-nfs";
import { formatBRL, formatLitros, formatNumero } from "@/lib/format";

interface StatTile {
  label: string;
  value: string;
  hint?: string;
  tone: MetricTone;
  icon: LucideIcon;
}

export function StatsCards() {
  const { data, isLoading, isError } = useStats();

  let tiles: StatTile[] = [];
  if (data) {
    tiles = [
      {
        label: "Total abastecido",
        value: formatLitros(data.total_litros, 0),
        hint: `${formatNumero(data.total_abastecimentos)} abastecimentos\n${formatBRL(data.total_custo_brl)}`,
        tone: "info",
        icon: Fuel,
      },
      {
        label: "Custo com equipamentos não cadastrados",
        value: `${formatNumero(data.pct_custo_nao_cadastrado, 2)}%`,
        hint: `${formatNumero(data.abastecimentos_nao_cadastrados)} abastecimentos\n${formatBRL(data.custo_nao_cadastrado_brl)}`,
        tone: "danger",
        icon: AlertTriangle,
      },
      {
        label: "NFs recebidas",
        value: formatNumero(data.total_nfs),
        hint: `${formatNumero(data.nfs_auditadas)} auditada${data.nfs_auditadas !== 1 ? "s" : ""}\n${formatNumero(data.nfs_nao_auditadas)} não auditada${data.nfs_nao_auditadas !== 1 ? "s" : ""}`,
        tone: data.nfs_nao_auditadas > 0 ? "warn" : "success",
        icon: FileText,
      },
      {
        label: "Equipamentos cadastrados",
        value: formatNumero(data.mobilizados_ativos),
        hint: `${formatNumero(data.total_mobilizados)} no total\n${formatNumero(data.veiculos_distintos_infleet)} veículos no Infleet`,
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
