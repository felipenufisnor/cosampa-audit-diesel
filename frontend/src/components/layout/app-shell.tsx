"use client";

import * as React from "react";
import {
  AlertTriangle,
  LayoutDashboard,
  ListChecks,
  Menu,
  MessageSquare,
  Network,
  Sparkle,
  TableProperties,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { DemoModeBadge } from "./demo-mode-badge";
import { OnboardingTour } from "./onboarding-tour";
import {
  BACKEND_CONTRACT_ERROR,
  hasAssistantHealthContract,
} from "@/lib/assistant-contract";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  match?: (pathname: string) => boolean;
}

interface NavSection {
  titulo: string;
  items: NavItem[];
  preview?: boolean;
}

const NAV_SECTIONS: NavSection[] = [
  {
    titulo: "Auditoria",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/consolidado", label: "Consolidado", icon: ListChecks },
    ],
  },
  {
    titulo: "Inteligência",
    items: [
      {
        href: "/#padroes",
        label: "Padrões detectados",
        icon: Sparkle,
        // ativo somente quando pathname for "/" e existir hash padroes
        match: (p) => p === "/" && typeof window !== "undefined" && window.location.hash === "#padroes",
      },
      { href: "/assistente", label: "Assistente", icon: MessageSquare },
    ],
  },
  {
    titulo: "Preview",
    preview: true,
    items: [
      { href: "/investigacoes", label: "Investigações", icon: TableProperties },
      { href: "/rede", label: "Análise de rede", icon: Network },
    ],
  },
];

const APP_TITLE = "PLATAFORMA DE AUDITORIA E CONTROLE - Arco Metropolitano JP";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [drawerAberto, setDrawerAberto] = React.useState(false);

  // Fecha o drawer ao trocar de rota usando o padrao "derive state during
  // render" (React 19): comparamos o pathname com o anterior; quando muda,
  // forcamos o drawer a fechar sem precisar de useEffect.
  const [prevPathname, setPrevPathname] = React.useState(pathname);
  if (pathname !== prevPathname) {
    setPrevPathname(pathname);
    setDrawerAberto(false);
  }

  return (
    <div className="min-h-screen bg-app-bg md:grid md:grid-cols-[240px_1fr]">
      <SidebarConteudo
        pathname={pathname}
        className="hidden md:flex md:flex-col bg-brand-primary-light/55 text-brand-primary-dark"
      />

      {drawerAberto && (
        <div
          className="fixed inset-0 z-40 bg-zinc-900/40 md:hidden"
          aria-hidden
          onClick={() => setDrawerAberto(false)}
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 bg-brand-primary-light/55 text-brand-primary-dark shadow-2xl transition-transform duration-200 md:hidden",
          drawerAberto ? "translate-x-0" : "-translate-x-full",
        )}
        aria-hidden={!drawerAberto}
        aria-label="Menu lateral"
      >
        <div className="flex items-center justify-between border-b border-brand-primary-dark/15 px-4 py-4">
          <div className="flex flex-col gap-1.5 min-w-0">
            <CosampaLogo width={140} height={28} />
            <p className="text-[11px] font-semibold uppercase tracking-wider text-brand-primary-dark">
              Auditoria e Controle
            </p>
          </div>
          <button
            type="button"
            onClick={() => setDrawerAberto(false)}
            aria-label="Fechar menu"
            className="rounded-md p-1.5 text-brand-primary-dark hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary-dark/35"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <NavLista pathname={pathname} />
      </aside>

      <div className="flex flex-col min-h-screen">
        <header className="min-h-16 border-b border-app-border bg-brand-primary-light/55 px-4 py-3 shadow-[0_1px_0_rgba(15,23,42,0.03)] backdrop-blur md:px-8 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <button
              type="button"
              onClick={() => setDrawerAberto(true)}
              aria-label="Abrir menu"
              aria-expanded={drawerAberto}
              className="md:hidden rounded-lg p-2 text-zinc-700 hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary/30"
            >
              <Menu className="h-5 w-5" aria-hidden />
            </button>
            <CosampaLogo
              width={106}
              height={24}
              className="hidden sm:block md:hidden shrink-0"
            />
            <div className="min-w-0 flex-1">
              <h1 className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-primary-dark/70">
                {APP_TITLE}
              </h1>
            </div>
          </div>
        </header>
        <AiStatusBanner />
        <main className="flex-1 px-4 py-5 sm:px-6 md:px-8 md:py-8">{children}</main>
        <AppFooter />
      </div>
      <DemoModeBadge />
      <OnboardingTour />
    </div>
  );
}

function AiStatusBanner() {
  const health = useQuery({
    queryKey: ["healthz"],
    queryFn: () => api.healthz(),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
  const healthData = health.data;
  const contratoOk = hasAssistantHealthContract(healthData);
  const contratoInvalido = Boolean(healthData && !contratoOk);
  const status = contratoOk ? healthData.assistant_status : undefined;
  const showBanner =
    health.isError ||
    contratoInvalido ||
    (status !== undefined && status !== "available");

  if (!showBanner) return null;

  const copy = contratoInvalido
    ? {
        title: "Backend desatualizado",
        detail: BACKEND_CONTRACT_ERROR,
      }
    : health.isError
    ? {
        title: "Status da IA não pôde ser verificado",
        detail:
          "As auditorias e alertas continuam disponíveis. Verifique a conexão com o backend para usar o assistente.",
      }
    : bannerCopy(
        status ?? "provider_error",
        contratoOk ? healthData.assistant_has_cached_answers : false,
        contratoOk ? healthData.assistant_reason : undefined,
      );

  return (
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-3 md:px-8">
      <div className="flex items-start gap-2 text-sm text-amber-900">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
        <div>
          <p className="font-semibold">{copy.title}</p>
          <p className="mt-0.5 text-amber-800">
            {copy.detail}
          </p>
        </div>
      </div>
    </div>
  );
}

function bannerCopy(
  status: NonNullable<import("@/lib/types").Healthz["assistant_status"]>,
  hasCache: boolean,
  reason?: string,
) {
  if (status === "degraded_cache") {
    return {
      title: "Assistente de IA em modo degradado",
      detail:
        "Perguntas livres estão temporariamente indisponíveis, mas respostas pré-carregadas podem ser usadas nas auditorias com cache.",
    };
  }
  if (status === "offline_fixture") {
    return {
      title: "Assistente de IA offline por configuração",
      detail: hasCache
        ? "Perguntas livres estão desativadas. Use as respostas pré-carregadas disponíveis nas auditorias."
        : "Configure a IA real ou gere respostas pré-carregadas para usar o assistente.",
    };
  }
  if (status === "missing_key") {
    return {
      title: "Assistente de IA sem chave configurada",
      detail: hasCache
        ? "Configure LLM_API_KEY para perguntas livres. Enquanto isso, use respostas pré-carregadas quando disponíveis."
        : "Configure LLM_API_KEY para restabelecer perguntas livres no assistente.",
    };
  }
  return {
    title: "Assistente de IA indisponível temporariamente",
    detail:
      reason ||
      "O provider de IA não respondeu ao healthcheck. As auditorias e alertas continuam disponíveis.",
  };
}

function SidebarConteudo({
  pathname,
  className,
}: {
  pathname: string;
  className?: string;
}) {
  return (
    <aside className={className} aria-label="Navegação principal">
      <div className="border-b border-brand-primary-dark/15 px-5 py-5">
        <CosampaLogo width={158} height={34} />
        <p className="mt-4 text-[11px] font-semibold uppercase tracking-[0.12em] text-brand-primary-dark/70">
          Controle técnico
        </p>
        <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-brand-primary-dark/70">
          Auditoria de diesel
        </p>
      </div>
      <NavLista pathname={pathname} />
    </aside>
  );
}

function NavLista({ pathname }: { pathname: string }) {
  return (
    <nav className="px-3 py-3 space-y-5" aria-label="Itens de navegação">
      {NAV_SECTIONS.map((sec) => (
        <NavSecao key={sec.titulo} secao={sec} pathname={pathname} />
      ))}
    </nav>
  );
}

function NavSecao({
  secao,
  pathname,
}: {
  secao: NavSection;
  pathname: string;
}) {
  const tituloCor = secao.preview
    ? "text-zinc-500"
    : "text-brand-primary-dark/60";
  return (
    <div>
      <p
        className={cn(
          "mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.14em]",
          tituloCor,
        )}
      >
        {secao.titulo}
      </p>
      <ul className="space-y-0.5">
        {secao.items.map((it) => (
          <li key={it.href}>
            <NavLink item={it} pathname={pathname} preview={secao.preview} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function NavLink({
  item,
  pathname,
  preview,
}: {
  item: NavItem;
  pathname: string;
  preview?: boolean;
}) {
  const Icon = item.icon;
  const baseHref = item.href.split("#")[0] || "/";
  const active = item.match
    ? item.match(pathname)
    : baseHref === "/"
      ? pathname === "/" && !item.href.includes("#")
      : pathname === baseHref || pathname.startsWith(baseHref + "/");
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-xl px-3 py-2 text-[13.5px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary-dark/35",
        preview
          ? active
            ? "bg-white/55 text-zinc-700 font-medium"
            : "text-zinc-600 hover:bg-white/25 hover:text-zinc-800"
          : active
            ? "bg-white/75 text-brand-primary-dark font-semibold shadow-sm"
            : "text-brand-primary-dark/75 hover:bg-white/25 hover:text-brand-primary-dark",
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4",
          preview ? "text-zinc-500" : undefined,
        )}
        aria-hidden
      />
      <span className="flex-1">{item.label}</span>
      {preview && (
        <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-amber-700">
          Preview
        </span>
      )}
    </Link>
  );
}

function CosampaLogo({
  width,
  height,
  className,
}: {
  width: number;
  height: number;
  className?: string;
}) {
  return (
    <Image
      src="/brand/logo-cosampa.png"
      alt="COSAMPA"
      width={width}
      height={height}
      priority
      className={cn("object-contain", className)}
      style={{ width, height }}
    />
  );
}

function AppFooter() {
  return (
    <footer className="mt-auto border-t border-app-border bg-brand-primary-light/55 px-4 py-3 md:px-8">
      <div className="flex items-center justify-center">
        <Image
          src="/brand/logo-tarea.svg"
          alt="Tarea"
          width={112}
          height={32}
          className="h-8 w-auto object-contain"
        />
      </div>
    </footer>
  );
}
