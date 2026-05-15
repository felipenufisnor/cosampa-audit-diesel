"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { useAuditoriaStore } from "@/stores/auditoria-store";

export function useSugestoes(auditoriaId: number | null | undefined) {
  return useQuery({
    queryKey: ["reconciliacao", "sugestoes", auditoriaId],
    queryFn: () => api.sugerirReconciliacao(auditoriaId as number),
    enabled: Boolean(auditoriaId),
    staleTime: 5 * 60 * 1000,
  });
}

export function useContextoReconciliacao(
  abastecimentoId: number | null | undefined,
  auditoriaId: number | null | undefined,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["reconciliacao", "contexto", abastecimentoId, auditoriaId],
    queryFn: () =>
      api.contextoReconciliacao(abastecimentoId as number, auditoriaId as number),
    enabled: Boolean(abastecimentoId && auditoriaId) && enabled,
    staleTime: 60 * 1000,
  });
}

export function useAprovarReconciliacao(auditoriaId: number | null | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.aprovarReconciliacao,
    onSuccess: (resp, variables) => {
      useAuditoriaStore.getState().marcarReconciliado(variables.abastecimento_id);
      if (resp.auditoria_atualizada) {
        qc.setQueryData(
          ["auditorias", resp.auditoria_atualizada.auditoria.id],
          resp.auditoria_atualizada,
        );
      }
      qc.invalidateQueries({ queryKey: ["reconciliacao", "sugestoes", auditoriaId] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      qc.invalidateQueries({ queryKey: ["consolidado"] });
      toast.success("Alerta reconciliado com sucesso");
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof ApiError ? err.message : "Falha ao reconciliar alerta.";
      toast.error(msg);
    },
  });
}
