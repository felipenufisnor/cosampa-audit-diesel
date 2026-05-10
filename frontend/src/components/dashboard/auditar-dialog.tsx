"use client";

import * as React from "react";

import {
  Dialog,
  DialogBody,
  DialogFooter,
  DialogHeader,
  DialogSubtitle,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

import { useAuditoriasDaNf, useCriarAuditoria } from "@/hooks/use-auditoria";
import type { ModoAuditoria, NFListItem } from "@/lib/types";
import { formatBRL, formatDateBR, formatDateTimeBR, formatLitros } from "@/lib/format";

interface Props {
  alvo: NFListItem | null;
  candidatos: NFListItem[];
  onClose: () => void;
}

export function AuditarDialog({ alvo, candidatos, onClose }: Props) {
  if (!alvo) return null;
  return (
    <AuditarDialogInner
      key={alvo.nota_fiscal}
      alvo={alvo}
      candidatos={candidatos}
      onClose={onClose}
    />
  );
}

function AuditarDialogInner({
  alvo,
  candidatos,
  onClose,
}: {
  alvo: NFListItem;
  candidatos: NFListItem[];
  onClose: () => void;
}) {
  const mutation = useCriarAuditoria();
  const historico = useAuditoriasDaNf(alvo.nota_fiscal);
  const possuiHistorico = (historico.data?.length ?? 0) > 0;

  const sugestaoDefault = React.useMemo(() => {
    const anteriores = candidatos
      .filter((c) => c.nota_fiscal !== alvo.nota_fiscal)
      .filter((c) => c.data_recebimento < alvo.data_recebimento)
      .sort((a, b) => b.data_recebimento.localeCompare(a.data_recebimento));
    return anteriores[0]?.nota_fiscal ?? null;
  }, [alvo, candidatos]);
  const [anteriorNf, setAnteriorNf] = React.useState<string | null>(sugestaoDefault);
  const [modo, setModo] = React.useState<ModoAuditoria>("nova_versao");

  return (
    <Dialog open={Boolean(alvo)} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <div>
          <DialogTitle>Auditar NF {alvo.nota_fiscal}</DialogTitle>
          <DialogSubtitle>
            {formatDateBR(alvo.data_recebimento)} | {formatLitros(alvo.qtd_litros, 0)} | {formatBRL(alvo.valor_total)}
          </DialogSubtitle>
        </div>
      </DialogHeader>
      <DialogBody>
        {possuiHistorico && (
          <section className="mb-4 rounded-xl border border-amber-200 bg-amber-50/70 p-3.5">
            <p className="text-xs font-semibold text-amber-900">
              Esta NF já possui {historico.data?.length} auditoria
              {historico.data && historico.data.length === 1 ? "" : "s"} anterior
              {historico.data && historico.data.length === 1 ? "" : "es"}.
            </p>
            {historico.data && historico.data[0] && (
              <p className="text-[11px] text-amber-800 mt-0.5">
                Última em {formatDateTimeBR(historico.data[0].criada_em)} (NF anterior {historico.data[0].nf_anterior}).
              </p>
            )}
            <fieldset className="mt-2.5 space-y-1.5">
              <legend className="sr-only">Modo de criação</legend>
              <label className="flex items-start gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="modo-auditoria"
                  className="mt-0.5 accent-brand-primary"
                  checked={modo === "nova_versao"}
                  onChange={() => setModo("nova_versao")}
                />
                <span className="text-xs text-zinc-800">
                  <span className="font-medium">Criar nova versão</span> · mantém
                  o histórico e marca esta como a auditoria atual.
                </span>
              </label>
              <label className="flex items-start gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="modo-auditoria"
                  className="mt-0.5 accent-brand-primary"
                  checked={modo === "sobrescrever_ultima"}
                  onChange={() => setModo("sobrescrever_ultima")}
                />
                <span className="text-xs text-zinc-800">
                  <span className="font-medium">Sobrescrever última</span> ·
                  apaga a auditoria mais recente desta NF antes de criar a nova.
                </span>
              </label>
            </fieldset>
          </section>
        )}
        <p className="mb-3 text-zinc-700">
          Escolha a NF anterior. A janela de auditoria será o intervalo entre o
          fim do descarregamento da NF anterior e o desta NF.
        </p>
        <div className="space-y-1.5">
          {candidatos
            .filter((c) => c.nota_fiscal !== alvo.nota_fiscal)
            .map((c) => {
              const selected = anteriorNf === c.nota_fiscal;
              return (
                <label
                  key={c.nota_fiscal}
                  className={`flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2.5 transition-colors ${
                    selected
                      ? "border-brand-primary bg-brand-primary-light"
                      : "border-zinc-200 bg-white hover:bg-zinc-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="nf-anterior"
                    className="accent-brand-primary"
                    checked={selected}
                    onChange={() => setAnteriorNf(c.nota_fiscal)}
                  />
                  <span className="font-semibold tabular text-zinc-950">
                    NF {c.nota_fiscal}
                  </span>
                  <span className="text-zinc-500">{formatDateBR(c.data_recebimento)}</span>
                  <span className="ml-auto tabular text-zinc-700">
                    {formatLitros(c.qtd_litros, 0)}
                  </span>
                </label>
              );
            })}
        </div>
      </DialogBody>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
          Cancelar
        </Button>
        <Button
          disabled={!anteriorNf || mutation.isPending}
          onClick={() => {
            if (!anteriorNf) return;
            mutation.mutate({
              nf_anterior: anteriorNf,
              nf_atual: alvo.nota_fiscal,
              gerar_parecer: true,
              modo,
            });
          }}
        >
          {mutation.isPending ? "Auditando..." : "Auditar"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
