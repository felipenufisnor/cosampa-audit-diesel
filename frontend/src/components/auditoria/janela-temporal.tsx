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
      <CardContent>
        <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.09em] text-zinc-500">
          Janela auditada
        </p>
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          <div>
            <p className="text-xs text-zinc-500">NF anterior</p>
            {semAnterior ? (
              <p className="text-sm text-zinc-400 italic mt-1">Sem NF anterior</p>
            ) : (
              <>
                <p className="text-2xl font-bold tabular text-zinc-950">{nfAnterior}</p>
                <div className="mt-1 text-xs tabular text-zinc-500">
                  {isLoadingAnterior ? (
                    <Skeleton className="h-3 w-28" />
                  ) : (
                    <JanelaMetadata data={dataAnterior} qtd={qtdAnterior} />
                  )}
                </div>
              </>
            )}
          </div>
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-brand-primary-light text-brand-primary-dark">
            <ArrowRight className="h-4 w-4" aria-hidden />
          </span>
          <div className="text-right">
            <p className="text-xs text-zinc-500">NF atual</p>
            <p className="text-2xl font-bold tabular text-zinc-950">{nfAtual}</p>
            <div className="mt-1 text-xs tabular text-zinc-500">
              {isLoadingAtual ? (
                <div className="flex justify-end">
                  <Skeleton className="h-3 w-28" />
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
