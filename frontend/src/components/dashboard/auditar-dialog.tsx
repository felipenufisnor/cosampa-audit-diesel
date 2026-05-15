"use client";

import * as React from "react";
import Link from "next/link";

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

  const candidatosAnteriores = React.useMemo(
    () =>
      candidatos
        .filter((c) => c.nota_fiscal !== alvo.nota_fiscal)
        .filter((c) => c.data_recebimento < alvo.data_recebimento)
        .sort((a, b) => b.data_recebimento.localeCompare(a.data_recebimento)),
    [alvo.data_recebimento, alvo.nota_fiscal, candidatos],
  );
  const semNfAnterior = candidatosAnteriores.length === 0;
  const sugestaoDefault = candidatosAnteriores[0]?.nota_fiscal ?? null;
  const [anteriorNf, setAnteriorNf] = React.useState<string | null>(sugestaoDefault);
  const [modo, setModo] = React.useState<ModoAuditoria>("nova_versao");
  const anteriorNfValida = anteriorNf !== null && candidatosAnteriores.some(
    (c) => c.nota_fiscal === anteriorNf,
  );
  const anteriorNfEfetiva = anteriorNfValida ? anteriorNf : sugestaoDefault;
  const anteriorSelecionadaValida = candidatosAnteriores.some(
    (c) => c.nota_fiscal === anteriorNfEfetiva,
  );

  // Estado do "ponto de corte manual" — usado apenas quando nao ha NF anterior.
  // Default: dia anterior a data da NF alvo, 08:00, estoques zerados.
  const pcDataDefault = React.useMemo(() => {
    const d = new Date(`${alvo.data_recebimento}T00:00:00`);
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
  }, [alvo.data_recebimento]);
  const [pcData, setPcData] = React.useState(pcDataDefault);
  const [pcHora, setPcHora] = React.useState("08:00");
  const [pcTanque, setPcTanque] = React.useState("0");
  const [pcComboio, setPcComboio] = React.useState("0");
  const [pcMotivo, setPcMotivo] = React.useState("");

  const pcTanqueNum = Number.parseFloat(pcTanque);
  const pcComboioNum = Number.parseFloat(pcComboio);
  const pcDataValida = pcData && pcData < alvo.data_recebimento;
  const pcEstoquesValidos =
    Number.isFinite(pcTanqueNum) &&
    Number.isFinite(pcComboioNum) &&
    pcTanqueNum >= 0 &&
    pcComboioNum >= 0;
  const pcMotivoValido = pcMotivo.trim().length > 0;
  const pcFormValido = Boolean(pcDataValida && pcEstoquesValidos && pcMotivoValido);

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
            {historico.data && historico.data.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {historico.data.map((a) => (
                  <div
                    key={a.id}
                    className="flex items-center gap-2 rounded-md bg-white/65 px-2 py-1.5 text-[11px] text-amber-900"
                  >
                    <span className="font-semibold">
                      {a.is_atual ? "Atual" : "Histórica"} v{a.versao} de {a.total_versoes}
                    </span>
                    <span>NF anterior {a.nf_anterior}</span>
                    <span className="text-amber-700">
                      {formatDateTimeBR(a.criada_em)}
                    </span>
                    <Link
                      href={`/auditoria/${a.id}`}
                      className="ml-auto font-semibold text-brand-primary-dark underline-offset-2 hover:underline"
                    >
                      Abrir
                    </Link>
                  </div>
                ))}
              </div>
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
        {semNfAnterior ? (
          <>
            <div className="mb-3 rounded-xl border border-amber-200 bg-amber-50/70 p-3 text-sm text-amber-900">
              <p className="font-semibold">Nenhuma NF anterior disponível.</p>
              <p className="mt-0.5 text-[12px] text-amber-800">
                NF {alvo.nota_fiscal} é a mais antiga do conjunto. Defina manualmente
                o ponto de corte (data, hora e estoques iniciais) para abrir a janela
                de auditoria.
              </p>
            </div>
            <fieldset className="space-y-3 rounded-xl border border-zinc-200 bg-white p-3">
              <legend className="px-1 text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
                Ponto de corte manual
              </legend>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1 text-xs font-medium text-zinc-700">
                  Data
                  <input
                    type="date"
                    max={alvo.data_recebimento}
                    value={pcData}
                    onChange={(e) => setPcData(e.target.value)}
                    className="rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-sm text-zinc-900 focus:border-brand-primary focus:outline-none focus:ring-2 focus:ring-brand-primary/25"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium text-zinc-700">
                  Hora
                  <input
                    type="time"
                    value={pcHora}
                    onChange={(e) => setPcHora(e.target.value)}
                    className="rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-sm text-zinc-900 focus:border-brand-primary focus:outline-none focus:ring-2 focus:ring-brand-primary/25"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium text-zinc-700">
                  Estoque inicial — tanque (L)
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    value={pcTanque}
                    onChange={(e) => setPcTanque(e.target.value)}
                    className="rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-sm text-zinc-900 tabular focus:border-brand-primary focus:outline-none focus:ring-2 focus:ring-brand-primary/25"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs font-medium text-zinc-700">
                  Estoque inicial — comboio (L)
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    value={pcComboio}
                    onChange={(e) => setPcComboio(e.target.value)}
                    className="rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-sm text-zinc-900 tabular focus:border-brand-primary focus:outline-none focus:ring-2 focus:ring-brand-primary/25"
                  />
                </label>
              </div>
              <label className="flex flex-col gap-1 text-xs font-medium text-zinc-700">
                Motivo / referência
                <textarea
                  rows={2}
                  value={pcMotivo}
                  onChange={(e) => setPcMotivo(e.target.value)}
                  placeholder="Ex: medição manual do tanque em 01/03/2026 às 08:00."
                  className="rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-sm text-zinc-900 focus:border-brand-primary focus:outline-none focus:ring-2 focus:ring-brand-primary/25"
                />
              </label>
              {pcData && !pcDataValida && (
                <p className="text-[11px] font-medium text-red-700">
                  A data do corte precisa ser anterior a {formatDateBR(alvo.data_recebimento)}.
                </p>
              )}
            </fieldset>
          </>
        ) : (
          <p className="mb-3 text-zinc-700">
            Escolha a NF anterior. A janela de auditoria será o intervalo entre o
            fim do descarregamento da NF anterior e o desta NF.
          </p>
        )}
        <div className={semNfAnterior ? "hidden" : "space-y-1.5"}>
          {candidatosAnteriores.map((c) => {
            const selected = anteriorNfEfetiva === c.nota_fiscal;
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
          variant="primary"
          disabled={
            (semNfAnterior ? !pcFormValido : !anteriorSelecionadaValida) ||
            mutation.isPending
          }
          onClick={() => {
            if (semNfAnterior) {
              if (!pcFormValido) return;
              mutation.mutate({
                nf_atual: alvo.nota_fiscal,
                gerar_parecer: true,
                modo,
                ponto_corte: {
                  data_inicio: `${pcData}T${pcHora}:00`,
                  estoque_tanque_inicial_litros: pcTanqueNum,
                  estoque_comboio_inicial_litros: pcComboioNum,
                  motivo: pcMotivo.trim(),
                },
              });
              return;
            }
            if (!anteriorNfEfetiva || !anteriorSelecionadaValida) return;
            mutation.mutate({
              nf_anterior: anteriorNfEfetiva,
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
