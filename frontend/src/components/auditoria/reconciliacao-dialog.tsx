"use client";

import * as React from "react";
import { History, Lightbulb, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogFooter,
  DialogHeader,
  DialogSubtitle,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { SearchInput } from "@/components/ui/search-input";

import {
  useAprovarReconciliacao,
  useContextoReconciliacao,
  useSugestoes,
} from "@/hooks/use-reconciliacao";
import type {
  AuditoriaCompleta,
  CandidatoGP,
  HistoricoReconciliacaoItem,
  MatchAproximado,
  SugestaoReconciliacao,
} from "@/lib/types";

interface Props {
  auditoria: AuditoriaCompleta;
  abastecimentoId: number | null;
  onClose: () => void;
}

export function ReconciliacaoDialog({ auditoria, abastecimentoId, onClose }: Props) {
  const open = Boolean(abastecimentoId);
  const auditoriaId = auditoria.auditoria.id;
  const { data, isLoading } = useSugestoes(open ? auditoriaId : null);
  const aprovar = useAprovarReconciliacao(auditoriaId);

  const [busca, setBusca] = React.useState("");
  const [observacao, setObservacao] = React.useState("");

  // Reset dos inputs ao fechar, padrao "derive state during render".
  const [prevOpen, setPrevOpen] = React.useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (!open) {
      setBusca("");
      setObservacao("");
    }
  }

  const alerta = abastecimentoId
    ? auditoria.alertas.find(
        (a) => a.tipo === "NAO_CADASTRADO" && a.abastecimento_id === abastecimentoId,
      ) ?? null
    : null;
  const veiculoRaw = (alerta?.payload?.veiculo_raw as string | undefined) ?? "";

  const sugestoesDoAlvo = React.useMemo(
    () =>
      data?.sugestoes.filter((s) => s.abastecimento_id === abastecimentoId) ?? [],
    [data, abastecimentoId],
  );

  const sugestoesFiltradas = React.useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return sugestoesDoAlvo;
    return sugestoesDoAlvo.filter((s) => {
      const c = s.candidato_gp;
      const haystack = [
        s.veiculo_infleet,
        s.apelido_infleet ?? "",
        s.justificativa,
        c?.placa_ativo ?? "",
        c?.equipamento ?? "",
        c?.marca ?? "",
        c?.modelo ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [sugestoesDoAlvo, busca]);

  const semCandidatos =
    !isLoading && sugestoesDoAlvo.every((s) => !s.candidato_gp);

  // Carrega contexto deterministico (matches por similaridade + historico)
  // apenas quando a IA nao retornou candidato confiavel. Ver achado AI-09.
  const contextoQuery = useContextoReconciliacao(
    abastecimentoId,
    auditoriaId,
    semCandidatos,
  );
  const contexto = contextoQuery.data ?? null;

  const aprovarComMobilizado = (
    mobilizadoId: number,
    confianca: number,
    origem: string,
  ) => {
    if (!abastecimentoId) return;
    const justificativa = [
      observacao.trim(),
      `Aprovado a partir de ${origem}.`,
    ]
      .filter(Boolean)
      .join(" | ");
    aprovar.mutate(
      {
        abastecimento_id: abastecimentoId,
        mobilizado_id: mobilizadoId,
        auditor: "demo",
        confianca,
        justificativa,
        auditoria_id: auditoriaId,
      },
      { onSuccess: onClose },
    );
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <div>
          <DialogTitle>Reconciliar {veiculoRaw}</DialogTitle>
          <DialogSubtitle>{alerta?.descricao}</DialogSubtitle>
        </div>
      </DialogHeader>
      <DialogBody>
        {sugestoesDoAlvo.length > 0 && !semCandidatos && (
          <SearchInput
            className="mb-3"
            label="Buscar nas sugestões"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por placa, equipamento, marca ou modelo"
          />
        )}

        {isLoading && <SugestoesSkeleton />}

        {!isLoading && sugestoesDoAlvo.length === 0 && (
          <p className="text-sm text-zinc-600">
            Nenhuma sugestão disponível para este abastecimento.
          </p>
        )}

        {!isLoading && semCandidatos && sugestoesDoAlvo.length > 0 && (
          <FallbackSemCandidatos
            loadingContexto={contextoQuery.isLoading}
            contexto={contexto}
            veiculoRaw={veiculoRaw}
            aprovando={aprovar.isPending}
            onAprovarHistorico={(h) =>
              aprovarComMobilizado(
                h.mobilizado.id,
                h.confianca ?? 0.6,
                "histórico de reconciliações anteriores",
              )
            }
            onAprovarMatch={(m) =>
              aprovarComMobilizado(
                m.candidato.id,
                m.similaridade,
                `match aproximado (similaridade ${Math.round(m.similaridade * 100)}%)`,
              )
            }
          />
        )}

        {!isLoading && !semCandidatos && (
          <div className="space-y-2">
            {sugestoesFiltradas.length === 0 && (
              <p className="text-xs text-zinc-500">
                Nenhuma sugestão corresponde ao termo buscado.
              </p>
            )}
            {sugestoesFiltradas.map((s) => (
              <SugestaoCard
                key={`${s.abastecimento_id}-${s.candidato_gp?.id ?? "n"}`}
                sugestao={s}
                onAprovar={() => {
                  if (!s.candidato_gp) return;
                  const justificativa = [observacao.trim(), s.justificativa]
                    .filter(Boolean)
                    .join(" | ");
                  aprovar.mutate(
                    {
                      abastecimento_id: s.abastecimento_id,
                      mobilizado_id: s.candidato_gp.id,
                      auditor: "demo",
                      confianca: s.confianca,
                      justificativa: justificativa || undefined,
                      auditoria_id: auditoriaId,
                    },
                    { onSuccess: onClose },
                  );
                }}
                loading={aprovar.isPending}
              />
            ))}
          </div>
        )}

        <div className="mt-4">
          <label className="block text-xs font-medium text-zinc-700 mb-1">
            Observação do auditor (opcional)
          </label>
          <textarea
            rows={3}
            value={observacao}
            onChange={(e) => setObservacao(e.target.value)}
            placeholder="Justificativa da decisão, contato com a obra, etc."
            className="w-full rounded-lg border border-app-border bg-white px-3 py-2 text-sm text-zinc-800 placeholder:text-zinc-400 shadow-sm focus:outline-none focus:border-brand-primary focus:ring-2 focus:ring-brand-primary/20"
          />
        </div>
      </DialogBody>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>
          Fechar
        </Button>
        {semCandidatos && (
          <Button
            variant="secondary"
            onClick={() => {
              toast.success("Alerta marcado como sem correspondência");
              onClose();
            }}
          >
            Confirmar sem correspondência
          </Button>
        )}
      </DialogFooter>
    </Dialog>
  );
}

function SugestaoCard({
  sugestao,
  onAprovar,
  loading,
}: {
  sugestao: SugestaoReconciliacao;
  onAprovar: () => void;
  loading: boolean;
}) {
  const cand = sugestao.candidato_gp;
  const conf = sugestao.confianca;
  const variant = conf >= 0.85 ? "success" : conf >= 0.65 ? "warn" : "muted";
  const podeAprovar = Boolean(cand) && conf >= 0.4;
  return (
    <div className="rounded-xl border border-app-border bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {cand ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-zinc-950 tabular">
                  {cand.placa_ativo}
                </span>
                <Badge variant={variant}>confiança {Math.round(conf * 100)}%</Badge>
                <Badge variant="neutral">{cand.situacao}</Badge>
              </div>
              <p className="text-xs text-zinc-700 mt-1">
                {cand.equipamento ?? "-"}
                {cand.marca ? ` · ${cand.marca}` : ""}
                {cand.modelo ? ` ${cand.modelo}` : ""}
                {cand.capacidade_litros ? ` · ${cand.capacidade_litros} L` : ""}
              </p>
            </>
          ) : (
            <p className="text-sm text-zinc-700">Sem candidato plausível</p>
          )}
          <p className="mt-2 text-xs text-zinc-500">{sugestao.justificativa}</p>
        </div>
        <Button size="sm" disabled={!podeAprovar || loading} onClick={onAprovar}>
          {loading ? (
            <span className="inline-flex items-center gap-1">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Aprovando...
            </span>
          ) : (
            "Aprovar"
          )}
        </Button>
      </div>
    </div>
  );
}

function FallbackSemCandidatos({
  loadingContexto,
  contexto,
  veiculoRaw,
  aprovando,
  onAprovarHistorico,
  onAprovarMatch,
}: {
  loadingContexto: boolean;
  contexto: {
    termo_busca_sugerido: string;
    matches_aproximados: MatchAproximado[];
    historico: HistoricoReconciliacaoItem[];
  } | null;
  veiculoRaw: string;
  aprovando: boolean;
  onAprovarHistorico: (h: HistoricoReconciliacaoItem) => void;
  onAprovarMatch: (m: MatchAproximado) => void;
}) {
  const historico = contexto?.historico ?? [];
  const matches = contexto?.matches_aproximados ?? [];
  const termo = contexto?.termo_busca_sugerido ?? veiculoRaw;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
        <p>
          A IA não encontrou correspondência provável para{" "}
          <span className="font-semibold">{veiculoRaw}</span>. Considere as
          alternativas abaixo antes de confirmar sem correspondência.
        </p>
      </div>

      {loadingContexto && (
        <div className="space-y-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      )}

      {!loadingContexto && historico.length > 0 && (
        <section>
          <header className="mb-2 flex items-center gap-2">
            <History className="h-4 w-4 text-zinc-500" />
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-700">
              Histórico de reconciliações deste veículo
            </h3>
            <Badge variant="info">{historico.length}</Badge>
          </header>
          <p className="mb-2 text-xs text-zinc-500">
            Decisões anteriores aprovadas para o mesmo identificador. Reaproveite
            se ainda for o veículo correto.
          </p>
          <div className="space-y-2">
            {historico.map((h) => (
              <HistoricoCard
                key={h.reconciliacao_id}
                historico={h}
                onAprovar={() => onAprovarHistorico(h)}
                loading={aprovando}
              />
            ))}
          </div>
        </section>
      )}

      {!loadingContexto && matches.length > 0 && (
        <section>
          <header className="mb-2 flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-zinc-500" />
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-700">
              Matches aproximados (similaridade textual)
            </h3>
            <Badge variant="muted">{matches.length}</Badge>
          </header>
          <p className="mb-2 text-xs text-zinc-500">
            Ranqueado por similaridade de placa, equipamento, marca e modelo
            contra mobilizados da mesma obra. Use como ponto de partida — valide
            antes de aprovar.
          </p>
          <div className="space-y-2">
            {matches.map((m) => (
              <MatchAproximadoCard
                key={m.candidato.id}
                match={m}
                onAprovar={() => onAprovarMatch(m)}
                loading={aprovando}
              />
            ))}
          </div>
        </section>
      )}

      {!loadingContexto && historico.length === 0 && matches.length === 0 && (
        <p className="text-sm text-zinc-600">
          Sem matches aproximados na obra e sem histórico para este identificador.
          Valide manualmente com a obra antes de confirmar sem correspondência.
        </p>
      )}

      {!loadingContexto && termo && (
        <div className="rounded-lg border border-app-border bg-zinc-50 px-3 py-2 text-xs text-zinc-700">
          <div className="flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-zinc-500" />
            <span className="font-semibold">Sugestão de busca no GP:</span>
            <code className="rounded bg-white px-1.5 py-0.5 font-mono text-[11px] text-zinc-800 border border-app-border">
              {termo}
            </code>
          </div>
        </div>
      )}
    </div>
  );
}

function HistoricoCard({
  historico,
  onAprovar,
  loading,
}: {
  historico: HistoricoReconciliacaoItem;
  onAprovar: () => void;
  loading: boolean;
}) {
  const dataFmt = new Date(historico.criada_em).toLocaleDateString("pt-BR");
  return (
    <div className="rounded-xl border border-app-border bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <CandidatoLinha candidato={historico.mobilizado} />
            <Badge variant="info">aprovado em {dataFmt}</Badge>
          </div>
          <p className="mt-1 text-xs text-zinc-600">
            Por <span className="font-medium">{historico.auditor}</span>
            {historico.confianca != null && (
              <> · confiança {Math.round(historico.confianca * 100)}%</>
            )}
          </p>
          {historico.justificativa && (
            <p className="mt-1 text-xs text-zinc-500 line-clamp-2">
              {historico.justificativa}
            </p>
          )}
        </div>
        <Button size="sm" disabled={loading} onClick={onAprovar}>
          {loading ? (
            <span className="inline-flex items-center gap-1">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Aprovando...
            </span>
          ) : (
            "Aplicar"
          )}
        </Button>
      </div>
    </div>
  );
}

function MatchAproximadoCard({
  match,
  onAprovar,
  loading,
}: {
  match: MatchAproximado;
  onAprovar: () => void;
  loading: boolean;
}) {
  const sim = match.similaridade;
  const variant = sim >= 0.7 ? "success" : sim >= 0.5 ? "warn" : "muted";
  return (
    <div className="rounded-xl border border-app-border bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <CandidatoLinha candidato={match.candidato} />
            <Badge variant={variant}>
              similaridade {Math.round(sim * 100)}%
            </Badge>
          </div>
          <p className="mt-1 text-xs text-zinc-500">{match.motivo}</p>
        </div>
        <Button size="sm" disabled={loading} onClick={onAprovar}>
          {loading ? (
            <span className="inline-flex items-center gap-1">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Aprovando...
            </span>
          ) : (
            "Aprovar"
          )}
        </Button>
      </div>
    </div>
  );
}

function CandidatoLinha({ candidato }: { candidato: CandidatoGP }) {
  return (
    <>
      <span className="text-sm font-semibold text-zinc-950 tabular">
        {candidato.placa_ativo}
      </span>
      <Badge variant="neutral">{candidato.situacao}</Badge>
      <span className="text-xs text-zinc-600 truncate">
        {candidato.equipamento ?? "-"}
        {candidato.marca ? ` · ${candidato.marca}` : ""}
        {candidato.modelo ? ` ${candidato.modelo}` : ""}
      </span>
    </>
  );
}

function SugestoesSkeleton() {
  return (
    <div className="space-y-2">
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-xl border border-app-border bg-white p-3">
          <Skeleton className="h-3.5 w-32 mb-2" />
          <Skeleton className="h-3 w-2/3 mb-1" />
          <Skeleton className="h-3 w-5/6" />
        </div>
      ))}
    </div>
  );
}
