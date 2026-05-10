"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/**
 * Indicador discreto, fixo no canto inferior direito, exibido apenas quando
 * o backend reporta DEMO_MODE ativo. Mensagem-tooltip explica que as
 * respostas da IA estao pre-computadas, evitando suspeita de "magica" ou
 * de mock improvisado durante a apresentacao.
 */
export function DemoModeBadge() {
  const { data } = useQuery({
    queryKey: ["healthz"],
    queryFn: () => api.healthz(),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
  if (!data?.demo_mode) return null;
  return (
    <div
      className="fixed bottom-3 right-4 z-40 select-none"
      role="status"
      aria-label="Modo demonstração ativo"
    >
      <span
        className="inline-flex items-center gap-1.5 rounded-full border border-app-border bg-white/95 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500 shadow-sm"
        title="Respostas da IA pré-computadas para apresentação. O sistema não depende de internet enquanto este modo está ativo."
      >
        <span className="h-1.5 w-1.5 rounded-full bg-brand-primary" aria-hidden />
        Modo demonstração
      </span>
    </div>
  );
}
