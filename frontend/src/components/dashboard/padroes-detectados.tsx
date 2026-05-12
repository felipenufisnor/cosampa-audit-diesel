"use client";

/**
 * PadroesDetectados (Feature C da v2).
 *
 * Lista os padroes detectados proativamente pelo backend; o botao
 * "Investigar" leva ao Assistente da Feature B com a pergunta inicial
 * ja preenchida no contexto da auditoria alvo.
 */

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, BrainCircuit } from "lucide-react";

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
  if (isError) return <PadroesEmpty message="Não foi possível carregar os padrões detectados." />;
  if (!data || data.padroes.length === 0) {
    return <PadroesEmpty message="Nenhum padrão com evidência suficiente foi detectado." />;
  }
  const altas = data.padroes.filter((p) => p.severidade === "alta").length;
  const medias = data.padroes.filter((p) => p.severidade === "media").length;

  return (
    <section aria-label="Padrões detectados" className="space-y-5">
      <header className="flex flex-col gap-3 border-b border-app-border pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
            Análise proativa
          </p>
          <h2 className="mt-1 text-[26px] font-bold tracking-tight text-zinc-950">
            Padrões detectados
          </h2>
          <p className="mt-1 max-w-3xl text-[16px] text-zinc-500">
            {data.padroes.length} padrão(s) priorizado(s) antes da abertura de qualquer NF,
            a partir do histórico de auditorias, abastecimentos e cadastro GP.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {altas > 0 && <Badge variant="danger">{altas} alta</Badge>}
          {medias > 0 && <Badge variant="warn">{medias} média</Badge>}
          {data.atualizado_em && (
            <span className="text-xs text-zinc-400">
              atualizado em {formatDateTimeBR(data.atualizado_em)}
            </span>
          )}
        </div>
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
  const sevStyle = sevToStyle(padrao.severidade);
  const pergunta = encodeURIComponent(
    `Investigue o seguinte padrão detectado pelo sistema: ${padrao.titulo}. ` +
      `Detalhes: ${padrao.descricao}`,
  );
  const podeInvestigar = padrao.auditoria_alvo_id !== null;
  return (
    <Card className={`relative overflow-hidden ${sevStyle.card}`}>
      <span
        aria-hidden
        className={`absolute inset-y-0 left-0 w-1 ${sevStyle.bar}`}
      />
      <CardContent className="flex min-h-48 flex-col pl-5">
        <div className="flex items-start justify-between gap-3">
          <p className="text-base font-semibold leading-snug text-zinc-950">
            {padrao.titulo}
          </p>
          <Badge variant={sevStyle.badge} className="shrink-0">
            {labelSev(padrao.severidade)}
          </Badge>
        </div>
        <p className="mt-2 flex-1 text-sm leading-relaxed text-zinc-600">
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
            className="shrink-0"
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
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function PadroesSkeleton() {
  return (
    <section className="space-y-5">
      <div className="border-b border-app-border pb-5">
        <div>
          <Skeleton className="h-3 w-32" />
          <Skeleton className="mt-2 h-8 w-60" />
          <Skeleton className="mt-2 h-4 w-full max-w-xl" />
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

function PadroesEmpty({ message }: { message: string }) {
  return (
    <section aria-label="Padrões detectados" className="space-y-5">
      <header className="border-b border-app-border pb-5">
        <p className="text-sm font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
          Análise proativa
        </p>
        <h2 className="mt-1 text-[26px] font-bold tracking-tight text-zinc-950">
          Padrões detectados
        </h2>
      </header>
      <Card>
        <CardContent className="flex items-center gap-3 text-sm text-zinc-600">
          <BrainCircuit className="h-5 w-5 text-brand-primary-dark" aria-hidden />
          {message}
        </CardContent>
      </Card>
    </section>
  );
}

function sevToStyle(s: PadraoSeveridade): {
  bar: string;
  badge: "danger" | "warn" | "muted";
  card: string;
} {
  switch (s) {
    case "alta":
      return {
        bar: "bg-red-500",
        badge: "danger",
        card: "border-red-200 bg-red-50/35",
      };
    case "media":
      return {
        bar: "bg-amber-500",
        badge: "warn",
        card: "border-amber-200 bg-amber-50/35",
      };
    case "baixa":
    default:
      return {
        bar: "bg-zinc-400",
        badge: "muted",
        card: "",
      };
  }
}

function labelSev(s: PadraoSeveridade): string {
  switch (s) {
    case "alta":
      return "Severidade alta";
    case "media":
      return "Severidade média";
    case "baixa":
    default:
      return "Severidade baixa";
  }
}
