"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";

export function useAuditoria(id: number | null | undefined) {
  return useQuery({
    queryKey: ["auditorias", id],
    queryFn: () => api.getAuditoria(id as number),
    enabled: Boolean(id),
  });
}

export function useAuditoriasDaNf(nf: string | null | undefined) {
  return useQuery({
    queryKey: ["nfs", nf, "auditorias"],
    queryFn: () => api.listarAuditoriasDaNf(nf as string),
    enabled: Boolean(nf),
  });
}

export function useCriarAuditoria() {
  const router = useRouter();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.criarAuditoria,
    onSuccess: (resp) => {
      qc.setQueryData(["auditorias", resp.auditoria.id], resp);
      qc.invalidateQueries({ queryKey: ["nfs"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      qc.invalidateQueries({ queryKey: ["consolidado"] });
      toast.success("Auditoria criada com sucesso");
      router.push(`/auditoria/${resp.auditoria.id}`);
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof ApiError ? err.message : "Falha ao gerar auditoria.";
      toast.error(msg);
    },
  });
}

export function useAprovarAuditoria(auditoriaId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { auditor?: string; observacao?: string }) =>
      api.aprovarAuditoria(auditoriaId, body),
    onSuccess: (resp) => {
      qc.setQueryData(["auditorias", resp.auditoria.id], resp);
      qc.invalidateQueries({ queryKey: ["nfs"] });
      qc.invalidateQueries({ queryKey: ["consolidado"] });
      toast.success("Auditoria aprovada");
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof ApiError ? err.message : "Falha ao aprovar auditoria.";
      toast.error(msg);
    },
  });
}
