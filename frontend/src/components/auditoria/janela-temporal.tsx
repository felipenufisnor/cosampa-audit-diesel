import { ArrowRight } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { formatDateBR, formatLitros } from "@/lib/format";

interface Props {
  nfAnterior: string;
  dataAnterior?: string;
  qtdAnterior?: number;
  nfAtual: string;
  dataAtual?: string;
  qtdAtual?: number;
}

export function JanelaTemporal({
  nfAnterior,
  dataAnterior,
  qtdAnterior,
  nfAtual,
  dataAtual,
  qtdAtual,
}: Props) {
  return (
    <Card>
      <CardContent>
        <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.09em] text-zinc-500">
          Janela auditada
        </p>
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          <div>
            <p className="text-xs text-zinc-500">NF anterior</p>
            <p className="text-2xl font-bold tabular text-zinc-950">{nfAnterior}</p>
            <p className="mt-1 text-xs tabular text-zinc-500">
              {formatDateBR(dataAnterior)} · {formatLitros(qtdAnterior, 0)}
            </p>
          </div>
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-brand-primary-light text-brand-primary-dark">
            <ArrowRight className="h-4 w-4" aria-hidden />
          </span>
          <div className="text-right">
            <p className="text-xs text-zinc-500">NF atual</p>
            <p className="text-2xl font-bold tabular text-zinc-950">{nfAtual}</p>
            <p className="mt-1 text-xs tabular text-zinc-500">
              {formatDateBR(dataAtual)} · {formatLitros(qtdAtual, 0)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
