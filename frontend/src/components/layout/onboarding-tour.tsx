"use client";

/**
 * Tour de onboarding da v2.
 *
 * Aparece automaticamente na PRIMEIRA visita ao app (controlado por
 * localStorage). 5 passos descrevendo as novidades da v2. O usuario pode
 * pular a qualquer momento ou rever pelo header "Tour" no rodape.
 *
 * SSR-safe: nada renderiza ate o componente montar no cliente, garantindo
 * que o localStorage seja consultado apenas em runtime.
 */

import * as React from "react";
import {
  ArrowRight,
  CheckCircle2,
  LayoutDashboard,
  MessageSquare,
  Network,
  Sparkle,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";

const STORAGE_KEY = "audit_diesel.onboarding.v2.seen";

interface Passo {
  titulo: string;
  texto: string;
  icone: LucideIcon;
  destaque: string;
}

const PASSOS: Passo[] = [
  {
    titulo: "Bem-vindo à v2",
    texto:
      "Esta versão adiciona três frentes de IA ao seu fluxo de auditoria. Em menos de 1 minuto você conhece o que mudou.",
    destaque: "Visão geral",
    icone: LayoutDashboard,
  },
  {
    titulo: "Padrões detectados (no topo do dashboard)",
    texto:
      "Antes de você abrir qualquer NF, o sistema já analisou o histórico e listou até 5 padrões proativos. Comece pelos cards vermelhos.",
    destaque: "Análise proativa",
    icone: Sparkle,
  },
  {
    titulo: "Auditar com narração em tempo real",
    texto:
      "Ao clicar em 'Auditar com narração' em uma NF, você vê cada etapa determinística + os trechos onde a IA intervém, em streaming.",
    destaque: "Reasoning stream",
    icone: ArrowRight,
  },
  {
    titulo: "Assistente de investigação",
    texto:
      "Em qualquer auditoria, abra o drawer 'Assistente' para conversar sobre AQUELA NF. O assistente pode consultar o cadastro do GP, histórico de veículos e comparar auditorias.",
    destaque: "Chat contextual",
    icone: MessageSquare,
  },
  {
    titulo: "Previews da fase 2",
    texto:
      "A seção 'Preview' da sidebar (Investigações + Análise de Rede) ilustra funcionalidades planejadas para a próxima fase. São mocks navegáveis, marcados com marca d'água.",
    destaque: "Em breve",
    icone: Network,
  },
];

function lerVisto(): boolean {
  try {
    return Boolean(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return true; // sem localStorage -> nao mostra tour
  }
}

export function OnboardingTour() {
  // useSyncExternalStore lida com SSR vs cliente sem disparar setState
  // dentro de useEffect (evita a regra react-hooks/set-state-in-effect).
  const visto = React.useSyncExternalStore(
    () => () => {},
    lerVisto,
    () => true, // snapshot do servidor: assume visto (nao renderiza modal)
  );
  const [fechado, setFechado] = React.useState(false);
  const [passo, setPasso] = React.useState(0);

  React.useEffect(() => {
    function onOpenTour() {
      setPasso(0);
      setFechado(false);
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch {
        // ok
      }
    }
    if (typeof window === "undefined") return;
    window.addEventListener("audit-diesel:open-tour", onOpenTour);
    return () =>
      window.removeEventListener("audit-diesel:open-tour", onOpenTour);
  }, []);

  const aberto = !visto && !fechado;
  if (!aberto) return null;

  function fechar() {
    setFechado(true);
    try {
      window.localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      // ok
    }
  }

  const p = PASSOS[passo];
  const ultimo = passo === PASSOS.length - 1;
  const Icon = p.icone;

  return (
    <>
      <div
        aria-hidden
        className="fixed inset-0 z-[60] bg-zinc-900/35"
        onClick={fechar}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-titulo"
        className="fixed inset-0 z-[70] flex items-center justify-center p-4"
      >
        <div className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl">
          <div className="flex items-start justify-between gap-3 border-b border-app-border px-5 py-4">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-primary-dark">
              <Icon className="h-4 w-4" aria-hidden />
              {p.destaque}
            </div>
            <button
              type="button"
              onClick={fechar}
              aria-label="Pular tour"
              className="rounded-md p-1 text-zinc-500 hover:bg-zinc-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="px-5 py-5">
            <h2 id="tour-titulo" className="text-lg font-semibold text-zinc-950">
              {p.titulo}
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-zinc-600">
              {p.texto}
            </p>
            <div className="mt-5 flex items-center gap-1.5">
              {PASSOS.map((_, i) => (
                <span
                  key={i}
                  aria-hidden
                  className={
                    i === passo
                      ? "h-1.5 w-6 rounded-full bg-brand-primary-dark"
                      : i < passo
                        ? "h-1.5 w-1.5 rounded-full bg-brand-primary-dark/60"
                        : "h-1.5 w-1.5 rounded-full bg-zinc-300"
                  }
                />
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between gap-3 border-t border-app-border bg-zinc-50/60 px-5 py-3">
            <Button variant="ghost" size="sm" onClick={fechar}>
              Pular
            </Button>
            <div className="flex items-center gap-2">
              {passo > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPasso((p) => p - 1)}
                >
                  Voltar
                </Button>
              )}
              {ultimo ? (
                <Button size="sm" onClick={fechar}>
                  <CheckCircle2 className="h-4 w-4" aria-hidden />
                  Entendi
                </Button>
              ) : (
                <Button size="sm" onClick={() => setPasso((p) => p + 1)}>
                  Próximo
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
