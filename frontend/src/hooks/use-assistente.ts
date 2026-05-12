"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/**
 * Status do servico de IA. Consultado quando o drawer do assistente abre
 * para que o usuario saiba ANTES de digitar se as perguntas livres vao
 * funcionar — em vez de descobrir a indisponibilidade apos enviar.
 */
export function useAssistenteStatus(enabled: boolean) {
  return useQuery({
    queryKey: ["healthz", "assistente"],
    queryFn: () => api.healthz(),
    enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

/**
 * Perguntas com resposta pre-cacheada para a auditoria. Quando o servico
 * de IA esta offline, sao a unica via funcional.
 */
export function usePerguntasSugeridas(
  auditoriaId: number | null | undefined,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ["assistente", "perguntas-sugeridas", auditoriaId],
    queryFn: () => api.listarPerguntasSugeridas(auditoriaId as number),
    enabled: Boolean(auditoriaId) && enabled,
    staleTime: 60_000,
  });
}
