"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useStats() {
  return useQuery({ queryKey: ["stats"], queryFn: api.stats });
}

export function useNFs() {
  return useQuery({ queryKey: ["nfs"], queryFn: api.listarNfs });
}

export function useNF(notaFiscal: string | null | undefined) {
  return useQuery({
    queryKey: ["nfs", notaFiscal],
    queryFn: () => api.detalheNf(notaFiscal as string),
    enabled: Boolean(notaFiscal),
  });
}

export function usePadroes() {
  return useQuery({ queryKey: ["padroes"], queryFn: api.listarPadroes });
}
