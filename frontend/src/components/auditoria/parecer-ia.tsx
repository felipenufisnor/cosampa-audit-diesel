"use client";

import ReactMarkdown from "react-markdown";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTimeBR } from "@/lib/format";
import type { ParecerMeta } from "@/lib/types";

interface Props {
  markdown: string | null;
  meta: ParecerMeta | null;
  criadaEm: string;
}

export function ParecerIA({ markdown, meta, criadaEm }: Props) {
  return (
    <Card className="sticky top-4 border-brand-primary/25 bg-white">
      <CardHeader className="border-brand-primary/15 bg-brand-primary-light/55">
        <div>
          <CardTitle className="text-brand-primary-dark">Parecer técnico - IA</CardTitle>
          <p className="mt-1 text-sm text-zinc-600">
            Síntese gerada automaticamente a partir dos indicadores e alertas desta auditoria.
          </p>
        </div>
        {meta?.offline && (
          <Badge variant="muted" className="shrink-0">offline</Badge>
        )}
      </CardHeader>
      <CardContent>
        {markdown ? (
          <div className="markdown-tight">
            <ReactMarkdown>{markdown}</ReactMarkdown>
          </div>
        ) : (
          <div className="space-y-2">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-5/6" />
            <Skeleton className="h-3 w-1/4 mt-3" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        )}
      </CardContent>
      <CardFooter>
        <div className="flex items-center justify-between w-full">
          <span>Gerado em {formatDateTimeBR(criadaEm)}</span>
          {meta && (
            <span className="tabular text-zinc-400">
              {meta.provider} · {meta.model ?? "?"} · {Math.round(meta.latency_s * 1000)}ms · {meta.prompt_tokens + meta.completion_tokens} tok
            </span>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}
