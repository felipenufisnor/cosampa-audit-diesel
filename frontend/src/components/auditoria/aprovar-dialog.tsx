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

import { useAprovarAuditoria } from "@/hooks/use-auditoria";

interface Props {
  auditoriaId: number;
  nfAtual: string;
  open: boolean;
  onClose: () => void;
}

export function AprovarDialog({ auditoriaId, nfAtual, open, onClose }: Props) {
  const [observacao, setObservacao] = React.useState("");
  const mutation = useAprovarAuditoria(auditoriaId);

  // Reset do textarea quando o modal fecha, no padrao "derive state during render".
  const [prevOpen, setPrevOpen] = React.useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (!open) setObservacao("");
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogHeader>
        <div>
          <DialogTitle>Aprovar auditoria da NF {nfAtual}</DialogTitle>
          <DialogSubtitle>
            A auditoria continua com pendências. Confirme a aprovação manual
            apenas após validar com a obra.
          </DialogSubtitle>
        </div>
      </DialogHeader>
      <DialogBody>
        <p className="text-sm text-zinc-700 mb-3">
          Esta ação registra o auditor responsável e o horário da aprovação. As
          inconsistências detectadas continuam visíveis no histórico.
        </p>
        <label className="block text-xs font-medium text-zinc-700 mb-1">
          Observação (opcional)
        </label>
        <textarea
          rows={4}
          value={observacao}
          onChange={(e) => setObservacao(e.target.value)}
          placeholder="Ex.: divergência confirmada por relatório da operação em campo."
          className="w-full rounded-lg border border-app-border bg-white px-3 py-2 text-sm text-zinc-800 placeholder:text-zinc-400 shadow-sm focus:outline-none focus:border-brand-primary focus:ring-2 focus:ring-brand-primary/20"
        />
      </DialogBody>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose} disabled={mutation.isPending}>
          Cancelar
        </Button>
        <Button
          disabled={mutation.isPending}
          onClick={() => {
            mutation.mutate(
              {
                auditor: "demo",
                observacao: observacao.trim() || undefined,
              },
              { onSuccess: () => onClose() },
            );
          }}
        >
          {mutation.isPending ? "Aprovando..." : "Confirmar aprovação"}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
