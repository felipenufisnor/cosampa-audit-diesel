"use client";

import * as React from "react";
import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";

import { AuditarDialog } from "./auditar-dialog";
import { StatusBadge } from "./status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

import { useNFs } from "@/hooks/use-nfs";
import { api } from "@/lib/api";
import type { NFListItem } from "@/lib/types";
import { formatBRL, formatDateBR, formatLitros } from "@/lib/format";

export function NFsTable() {
  const { data, isLoading, isError } = useNFs();
  const [alvo, setAlvo] = React.useState<NFListItem | null>(null);
  const qc = useQueryClient();

  // Prefetch da auditoria existente quando o auditor passa o mouse na linha.
  // Reduz para zero a latencia percebida ao clicar em "ver" durante a demo.
  function prefetchAuditoria(id: number | null) {
    if (id === null) return;
    qc.prefetchQuery({
      queryKey: ["auditoria", id],
      queryFn: () => api.getAuditoria(id),
      staleTime: 30_000,
    });
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="px-5 py-4">
        <div>
          <CardTitle className="text-[18px]">Notas fiscais</CardTitle>
          <p className="mt-1 text-[16px] text-zinc-500">
            Janela de auditoria definida entre duas NFs sequenciais.
          </p>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b border-app-border bg-zinc-50/90 text-zinc-500">
                <th className="px-5 py-3.5 text-center text-[13px] font-bold uppercase tracking-[0.08em]">
                  NF
                </th>
                <th className="px-5 py-3.5 text-center text-[13px] font-bold uppercase tracking-[0.08em]">
                  DATA
                </th>
                <th className="px-5 py-3.5 text-center text-[13px] font-bold uppercase tracking-[0.08em]">
                  OBRA
                </th>
                <th className="px-5 py-3.5 text-center text-[13px] font-bold uppercase tracking-[0.08em]">
                  QUANTIDADE
                </th>
                <th className="px-5 py-3.5 text-center text-[13px] font-bold uppercase tracking-[0.08em]">
                  VALOR
                </th>
                <th className="px-5 py-3.5 text-center text-[13px] font-bold uppercase tracking-[0.08em]">
                  ÚLTIMA AUDITORIA
                </th>
                <th className="px-5 py-3.5 text-center text-[13px] font-bold uppercase tracking-[0.08em]">
                  AÇÕES
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading &&
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="border-b border-zinc-100">
                    <td colSpan={7} className="px-4 py-3">
                      <Skeleton className="h-4 w-full" />
                    </td>
                  </tr>
                ))}
              {isError && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-sm text-red-700">
                    Não foi possível carregar as notas fiscais. Tente novamente em instantes.
                  </td>
                </tr>
              )}
              {data?.map((nf) => (
                <tr
                  key={nf.nota_fiscal}
                  onMouseEnter={() => prefetchAuditoria(nf.ultima_auditoria_id)}
                  className="border-b border-zinc-100 transition-colors hover:bg-brand-primary-light/35"
                >
                  <td className="px-5 py-4 text-center font-semibold tabular text-zinc-950">
                    {nf.nota_fiscal}
                  </td>
                  <td className="px-5 py-4 text-center tabular text-zinc-700">
                    {formatDateBR(nf.data_recebimento)}
                  </td>
                  <td
                    className="max-w-[320px] truncate px-5 py-4 text-center text-zinc-700"
                    title={nf.nome_obra}
                  >
                    {nf.nome_obra}
                  </td>
                  <td className="px-5 py-4 text-center tabular text-zinc-700">
                    {formatLitros(nf.qtd_litros, 0)}
                  </td>
                  <td className="px-5 py-4 text-center tabular text-zinc-700">
                    {formatBRL(nf.valor_total)}
                  </td>
                  <td className="px-5 py-4 text-center">
                    <div className="relative flex min-h-7 items-center justify-center">
                      <StatusBadge status={nf.ultima_validacao} />
                      {nf.ultima_auditoria_id && (
                        <Link
                          className="absolute right-0 inline-flex translate-x-10 items-center gap-1 rounded-full px-2 py-1 text-sm font-semibold text-brand-primary-dark transition-colors hover:bg-brand-primary-light"
                          href={`/auditoria/${nf.ultima_auditoria_id}`}
                        >
                          Ver
                          <ExternalLink className="h-3 w-3" aria-hidden />
                        </Link>
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-4 text-center">
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => setAlvo(nf)}
                    >
                      Auditar
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
      <AuditarDialog alvo={alvo} candidatos={data ?? []} onClose={() => setAlvo(null)} />
    </Card>
  );
}
