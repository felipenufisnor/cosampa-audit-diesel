"use client";

import * as React from "react";
import { use } from "react";
import { CheckCircle2, FileDown } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { AlertasList } from "@/components/auditoria/alertas-list";
import { AprovarDialog } from "@/components/auditoria/aprovar-dialog";
import { IndicadoresCard } from "@/components/auditoria/indicadores-card";
import { JanelaTemporal } from "@/components/auditoria/janela-temporal";
import { ParecerIA } from "@/components/auditoria/parecer-ia";
import { ReconciliacaoDialog } from "@/components/auditoria/reconciliacao-dialog";
import { StatusBadge } from "@/components/dashboard/status-badge";
import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

import { useAuditoria } from "@/hooks/use-auditoria";
import { useNF } from "@/hooks/use-nfs";
import { useAuditoriaStore } from "@/stores/auditoria-store";
import { api, ApiError } from "@/lib/api";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function AuditoriaPage({ params }: PageProps) {
  const { id } = use(params);
  const auditoriaId = Number(id);
  const { data, isLoading, isError, error } = useAuditoria(auditoriaId);

  const reconciliacaoTarget = useAuditoriaStore(
    (s) => s.reconciliacaoTargetAbastecimentoId,
  );
  const setReconciliacaoTarget = useAuditoriaStore(
    (s) => s.setReconciliacaoTarget,
  );

  return (
    <div className="mx-auto max-w-[1500px] space-y-6">
      <Breadcrumbs
        items={[
          { label: "Dashboard", href: "/" },
          { label: data ? `Auditoria NF ${data.auditoria.nf_atual}` : "Auditoria" },
        ]}
      />
      {isLoading && <PageSkeleton />}
      {isError && <ErroEstado erro={error} />}
      {data && (
        <>
          <Header auditoriaId={auditoriaId} ind={data.auditoria} />
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
            <div className="min-w-0 space-y-6 xl:col-span-8">
              <JanelaConDados anteriorNF={data.auditoria.nf_anterior} atualNF={data.auditoria.nf_atual} />
              <IndicadoresCard ind={data.auditoria} />
              <AlertasList
                alertas={data.alertas}
                onReconciliar={(id_) => setReconciliacaoTarget(id_)}
              />
            </div>
            <div className="min-w-0 xl:col-span-4">
              <ParecerIA
                markdown={data.auditoria.parecer_ia}
                meta={data.parecer_meta}
                criadaEm={data.auditoria.criada_em}
              />
            </div>
          </div>
          <ReconciliacaoDialog
            auditoria={data}
            abastecimentoId={reconciliacaoTarget}
            onClose={() => setReconciliacaoTarget(null)}
          />
        </>
      )}
    </div>
  );
}

function ErroEstado({ erro }: { erro: unknown }) {
  if (erro instanceof ApiError && erro.status === 404) {
    return (
      <Card>
        <CardContent className="space-y-3 text-center py-8">
          <h2 className="text-lg font-semibold text-zinc-900">
            Auditoria não encontrada
          </h2>
          <p className="text-sm text-zinc-600">
            Esta auditoria pode ter sido removida ou nunca existiu.
          </p>
          <div className="pt-2 flex justify-center">
            <Link href="/">
              <Button>Voltar ao Dashboard</Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <CardContent className="text-sm text-red-700">
        Não foi possível carregar a auditoria. Tente novamente em instantes.
      </CardContent>
    </Card>
  );
}

function Header({
  auditoriaId,
  ind,
}: {
  auditoriaId: number;
  ind: import("@/lib/types").AuditoriaIndicadores;
}) {
  const [aprovarOpen, setAprovarOpen] = React.useState(false);
  const podeAprovar = ind.validacao_final === "INCONSISTENTE";
  const aprovadaManualmente = Boolean(ind.aprovada_em);

  async function handleBaixarPdf() {
    try {
      const blob = await api.baixarPdf(auditoriaId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `auditoria_${auditoriaId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Erro ao gerar PDF");
    }
  }

  return (
    <header className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-app-border bg-white px-5 py-5 shadow-[0_4px_14px_rgba(15,23,42,0.06)]">
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
          Auditoria #{auditoriaId}
        </p>
        <h2 className="mt-1 text-3xl font-bold tabular tracking-tight text-zinc-950">
          NF {ind.nf_atual}
        </h2>
        <p className="mt-1 max-w-2xl truncate text-sm text-zinc-500">
          {ind.nome_obra}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        {podeAprovar && (
          <Button
            variant="secondary"
            onClick={() => setAprovarOpen(true)}
            aria-label="Aprovar auditoria manualmente"
            title="Marca a auditoria como aprovada após validação manual com a obra"
          >
            <CheckCircle2 className="h-4 w-4" aria-hidden />
            Aprovar
          </Button>
        )}
        <Button
          variant="primary"
          type="button"
          onClick={handleBaixarPdf}
          aria-label="Baixar PDF de auditoria"
          title="Gera o relatório em PDF pronto para arquivamento"
        >
          <FileDown className="h-4 w-4" aria-hidden />
          Gerar PDF
        </Button>
        <StatusBadge
          status={ind.validacao_final}
          aprovadaManualmente={aprovadaManualmente}
          className="h-9 min-w-[190px] justify-center px-4 text-sm"
        />
      </div>
      <AprovarDialog
        auditoriaId={auditoriaId}
        nfAtual={ind.nf_atual}
        open={aprovarOpen}
        onClose={() => setAprovarOpen(false)}
      />
    </header>
  );
}

function JanelaConDados({
  anteriorNF,
  atualNF,
}: {
  anteriorNF: string;
  atualNF: string;
}) {
  const ant = useNF(anteriorNF);
  const atu = useNF(atualNF);
  return (
    <JanelaTemporal
      nfAnterior={anteriorNF}
      dataAnterior={ant.data?.data_recebimento}
      qtdAnterior={ant.data?.quantidade_nf_litros}
      nfAtual={atualNF}
      dataAtual={atu.data?.data_recebimento}
      qtdAtual={atu.data?.quantidade_nf_litros}
    />
  );
}

function PageSkeleton() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-9 w-48" />
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="space-y-5 xl:col-span-8">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
        <div className="xl:col-span-4">
          <Skeleton className="h-96 w-full" />
        </div>
      </div>
    </div>
  );
}
