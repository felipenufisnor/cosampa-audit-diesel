"use client";

import { RefreshCw, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTimeBR } from "@/lib/format";
import type { ParecerMeta } from "@/lib/types";

type ParecerStatus = "ok" | "placeholder" | "ausente";

interface Props {
  markdown: string | null;
  status: ParecerStatus;
  meta: ParecerMeta | null;
  criadaEm: string;
  onRegenerar?: () => void;
  regenerando?: boolean;
}

export function ParecerIA({
  markdown,
  status,
  meta,
  criadaEm,
  onRegenerar,
  regenerando = false,
}: Props) {
  const isOk = status === "ok" && !!markdown;

  return (
    <Card className="sticky top-4 border-brand-primary/25 bg-white">
      <CardHeader className="border-brand-primary/15 bg-brand-primary-light/55">
        <div>
          <CardTitle className="flex items-center gap-1.5 text-brand-primary-dark">
            Recomendação Técnica - IA
            <Sparkles className="ml-2 h-5 w-5 shrink-0 text-brand-primary/50" aria-hidden />
          </CardTitle>
          <p className="mt-1 text-sm text-zinc-600">
            Síntese gerada automaticamente a partir dos indicadores e alertas desta auditoria.{" "}
            <span className="font-medium text-zinc-700">Valores financeiros referentes exclusivamente à janela desta NF.</span>
          </p>
        </div>
        {meta?.offline && (
          <Badge variant="muted" className="shrink-0">offline</Badge>
        )}
      </CardHeader>
      <CardContent>
        {isOk ? (
          <div className="markdown-tight">
            <ReactMarkdown>{markdown}</ReactMarkdown>
          </div>
        ) : (
          <EmptyParecer
            status={status}
            onRegenerar={onRegenerar}
            regenerando={regenerando}
          />
        )}
      </CardContent>
      {isOk && (
        <CardFooter>
          <div className="w-full whitespace-nowrap">
            <span>Gerado em {formatDateTimeBR(criadaEm)}</span>
          </div>
        </CardFooter>
      )}
    </Card>
  );
}

function EmptyParecer({
  status,
  onRegenerar,
  regenerando,
}: {
  status: ParecerStatus;
  onRegenerar?: () => void;
  regenerando?: boolean;
}) {
  const isPlaceholder = status === "placeholder";
  const titulo = isPlaceholder
    ? "Parecer da IA indisponível para esta auditoria"
    : "Parecer ainda não gerado para esta auditoria";
  const detalhe = isPlaceholder
    ? "O texto registrado é um template e foi ocultado para não induzir o auditor a erro. Regenere o parecer quando o serviço de IA estiver disponível."
    : "Use o botão de regeneração quando o serviço de IA estiver disponível para produzir a síntese técnica.";

  return (
    <div className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-4 text-sm text-zinc-700">
      <p className="font-medium text-zinc-800">{titulo}</p>
      <p className="mt-1 text-zinc-600">{detalhe}</p>
      {onRegenerar && (
        <Button
          variant="secondary"
          size="sm"
          className="mt-3"
          onClick={onRegenerar}
          disabled={regenerando}
        >
          <RefreshCw
            className={regenerando ? "h-4 w-4 mr-2 animate-spin" : "h-4 w-4 mr-2"}
          />
          {regenerando ? "Regenerando..." : "Regenerar parecer"}
        </Button>
      )}
    </div>
  );
}
