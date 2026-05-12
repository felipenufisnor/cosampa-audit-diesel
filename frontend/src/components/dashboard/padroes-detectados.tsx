"use client";

/**
 * PadroesDetectados (Feature C da v2).
 *
 * Ocupa o topo do dashboard, ANTES de stats e tabela. Cada card e' um
 * padrao detectado proativamente pelo backend (job + LLM); o botao
 * "Investigar" leva ao Assistente da Feature B com a pergunta inicial
 * ja preenchida no contexto da auditoria alvo.
 *
 * Quando nao ha padroes ou o backend retorna lista vazia, o componente nao
 * renderiza nada -- evita poluir a UI com placeholder vazio.
 */

import * as React from "react";
import { useRouter } from "next/navigation";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { usePadroes } from "@/hooks/use-nfs";
import { formatDateTimeBR } from "@/lib/format";
import type { Padrao, PadraoSeveridade } from "@/lib/types";

export function PadroesDetectados() {
  const { data, isLoading, isError } = usePadroes();

  if (isLoading) return <PadroesSkeleton />;
  if (isError) return null;
  if (!data || data.padroes.length === 0) return null;

  return (
    <section id="padroes" aria-label="Padrões detectados" className="scroll-mt-24">
      <header className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
            Análise proativa
          </p>
          <h3 className="mt-1 text-lg font-semibold text-zinc-950">
            Padrões detectados
          </h3>
          <p className="text-sm text-zinc-500">
            {data.padroes.length} padrão(s) priorizado(s) pelo sistema com base
            no histórico de auditorias e abastecimentos.
          </p>
        </div>
        {data.atualizado_em && (
          <p className="text-xs text-zinc-400">
            atualizado em {formatDateTimeBR(data.atualizado_em)}
          </p>
        )}
      </header>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
        {data.padroes.map((p) => (
          <PadraoCard key={p.id} padrao={p} />
        ))}
      </div>
    </section>
  );
}

function PadraoCard({ padrao }: { padrao: Padrao }) {
  const router = useRouter();
  const sevColor = sevToColor(padrao.severidade);
  const pergunta = encodeURIComponent(
    `Investigue o seguinte padrão detectado pelo sistema: ${padrao.titulo}. ` +
      `Detalhes: ${padrao.descricao}`,
  );
  const podeInvestigar = padrao.auditoria_alvo_id !== null;
  return (
    <Card className="relative overflow-hidden">
      <span
        aria-hidden
        className={`absolute inset-y-0 left-0 w-1 ${sevColor}`}
      />
      <CardContent className="pl-5">
        <div className="flex items-start justify-between gap-3">
          <p className="font-medium leading-snug text-zinc-900">
            {padrao.titulo}
          </p>
          <Badge variant="muted" className="shrink-0">
            {labelSev(padrao.severidade)}
          </Badge>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-zinc-600">
          {padrao.descricao}
        </p>
        <div className="mt-3 flex items-center justify-between">
          <div>
            <Badge variant="neutral">
              {padrao.tipo.replace(/_/g, " ")}
            </Badge>
            {padrao.auditoria_alvo_nf && (
              <p className="mt-0.5 text-[11px] text-zinc-500">
                Investiga NF {padrao.auditoria_alvo_nf}
              </p>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            disabled={!podeInvestigar}
            title={
              podeInvestigar
                ? "Abrir o assistente na auditoria relacionada"
                : "Sem auditoria relacionada a este padrão"
            }
            onClick={() => {
              if (!padrao.auditoria_alvo_id) return;
              router.push(
                `/auditoria/${padrao.auditoria_alvo_id}?assistente=open&ask=${pergunta}`,
              );
            }}
          >
            Investigar
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function PadroesSkeleton() {
  return (
    <section>
      <div className="mb-3 flex items-end justify-between">
        <div>
          <Skeleton className="h-3 w-32" />
          <Skeleton className="mt-2 h-5 w-48" />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28 w-full rounded-2xl" />
        ))}
      </div>
    </section>
  );
}

function sevToColor(s: PadraoSeveridade): string {
  switch (s) {
    case "alta":
      return "bg-red-500";
    case "media":
      return "bg-amber-500";
    case "baixa":
    default:
      return "bg-zinc-400";
  }
}

function labelSev(s: PadraoSeveridade): string {
  switch (s) {
    case "alta":
      return "Severidade alta";
    case "media":
      return "Severidade media";
    case "baixa":
    default:
      return "Severidade baixa";
  }
}
