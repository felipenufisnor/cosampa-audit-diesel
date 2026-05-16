import { ArrowRight } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateBR, formatLitros } from "@/lib/format";

interface Props {
  nfAnterior: string | null | undefined;
  dataAnterior?: string;
  qtdAnterior?: number;
  isLoadingAnterior?: boolean;
  nfAtual: string;
  dataAtual?: string;
  qtdAtual?: number;
  isLoadingAtual?: boolean;
}

export function JanelaTemporal({
  nfAnterior,
  dataAnterior,
  qtdAnterior,
  isLoadingAnterior,
  nfAtual,
  dataAtual,
  qtdAtual,
  isLoadingAtual,
}: Props) {
  const semAnterior = !nfAnterior || nfAnterior.startsWith("CORTE:");

  return (
    <Card>
      <CardContent className="py-6">
        <p className="mb-5 text-center text-sm font-bold uppercase tracking-[0.09em] text-zinc-500">
          Janela auditada
        </p>
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 sm:gap-4">
          <div className="min-w-0 text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500">
              NF anterior
            </p>
            {semAnterior ? (
              <p className="mt-2 text-sm italic text-zinc-400">Sem NF anterior</p>
            ) : (
              <>
                <p className="mt-1 tabular text-3xl font-bold tracking-tight text-zinc-950">
                  {nfAnterior}
                </p>
                <div className="mt-2 text-sm tabular text-zinc-500">
                  {isLoadingAnterior ? (
                    <Skeleton className="mx-auto h-4 w-36" />
                  ) : (
                    <JanelaMetadata data={dataAnterior} qtd={qtdAnterior} />
                  )}
                </div>
              </>
            )}
          </div>
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-primary-light text-brand-primary-dark sm:h-12 sm:w-12">
            <ArrowRight className="h-5 w-5 sm:h-6 sm:w-6" aria-hidden />
          </span>
          <div className="min-w-0 text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-zinc-500">
              NF atual
            </p>
            <p className="mt-1 tabular text-3xl font-bold tracking-tight text-zinc-950">
              {nfAtual}
            </p>
            <div className="mt-2 text-sm tabular text-zinc-500">
              {isLoadingAtual ? (
                <div className="flex justify-center">
                  <Skeleton className="h-4 w-36" />
                </div>
              ) : (
                <JanelaMetadata data={dataAtual} qtd={qtdAtual} />
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function JanelaMetadata({
  data,
  qtd,
}: {
  data?: string;
  qtd?: number;
}) {
  const partes: string[] = [];
  if (data) partes.push(formatDateBR(data));
  if (qtd !== undefined && qtd !== null) partes.push(formatLitros(qtd, 0));

  if (partes.length === 0) {
    return <span className="italic text-zinc-400">Detalhes indisponíveis</span>;
  }

  return <span>{partes.join(" · ")}</span>;
}
