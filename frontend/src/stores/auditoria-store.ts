"use client";

import { create } from "zustand";

interface AuditoriaSession {
  /** Abastecimento alvo do modal de reconciliação (null = modal fechado). */
  reconciliacaoTargetAbastecimentoId: number | null;
  setReconciliacaoTarget: (id: number | null) => void;

  /** IDs de abastecimentos reconciliados com sucesso na sessão atual. */
  reconciliadosIds: number[];
  marcarReconciliado: (id: number) => void;

  /** Filtro ativo na lista de alertas da página /auditoria/[id]. */
  alertaFiltroTipo: "TODOS" | "NAO_CADASTRADO" | "POS_DESMOB" | "OUTLIER" | "DUPLICIDADE";
  setAlertaFiltroTipo: (
    tipo: AuditoriaSession["alertaFiltroTipo"],
  ) => void;

  alertaOrdenacao: "severidade" | "impacto";
  setAlertaOrdenacao: (o: AuditoriaSession["alertaOrdenacao"]) => void;
}

export const useAuditoriaStore = create<AuditoriaSession>((set) => ({
  reconciliacaoTargetAbastecimentoId: null,
  setReconciliacaoTarget: (id) => set({ reconciliacaoTargetAbastecimentoId: id }),

  reconciliadosIds: [],
  marcarReconciliado: (id) =>
    set((s) => ({ reconciliadosIds: [...s.reconciliadosIds, id] })),

  alertaFiltroTipo: "TODOS",
  setAlertaFiltroTipo: (alertaFiltroTipo) => set({ alertaFiltroTipo }),

  alertaOrdenacao: "severidade",
  setAlertaOrdenacao: (alertaOrdenacao) => set({ alertaOrdenacao }),
}));
