"use client";

import * as React from "react";
import { LayoutDashboard, ListChecks, Menu, X } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { DemoModeBadge } from "./demo-mode-badge";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/consolidado", label: "Consolidado", icon: ListChecks },
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
        className="hidden md:flex md:flex-col bg-brand-sidebar text-brand-primary-dark"
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
          "fixed inset-y-0 left-0 z-50 w-64 bg-brand-sidebar text-brand-primary-dark shadow-2xl transition-transform duration-200 md:hidden",
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
        <header className="min-h-16 border-b border-app-border bg-white/95 px-4 py-3 shadow-[0_1px_0_rgba(15,23,42,0.03)] backdrop-blur md:px-8 flex items-center justify-between gap-4">
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
              <h1 className="text-base font-bold leading-snug tracking-tight text-zinc-950 sm:text-xl lg:text-2xl">
                {APP_TITLE}
              </h1>
            </div>
          </div>
        </header>
        <main className="flex-1 px-4 py-5 sm:px-6 md:px-8 md:py-8">{children}</main>
        <AppFooter />
      </div>
      <DemoModeBadge />
    </div>
  );
}

function SidebarConteudo({
  pathname,
  className,
}: {
  pathname: string;
  className?: string;
}) {
  return (
    <aside className={className} aria-label="Navegacao principal">
      <div className="border-b border-brand-primary-dark/15 px-5 py-5">
        <CosampaLogo width={158} height={34} />
        <p className="mt-4 text-[11px] font-semibold uppercase tracking-[0.12em] text-brand-primary-dark/70">
          Controle técnico
        </p>
        <p className="mt-1 text-sm font-semibold leading-snug text-brand-primary-dark">
          Auditoria de diesel
        </p>
      </div>
      <NavLista pathname={pathname} />
    </aside>
  );
}

function NavLista({ pathname }: { pathname: string }) {
  return (
    <nav className="px-3 py-4 space-y-1.5" aria-label="Itens de navegacao">
      {NAV_ITEMS.map((it) => {
        const Icon = it.icon;
        const active =
          pathname === it.href ||
          (it.href !== "/" && pathname.startsWith(it.href));
        return (
          <Link
            key={it.href}
            href={it.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary-dark/35",
              active
                ? "bg-white/75 text-brand-primary-dark font-semibold shadow-sm"
                : "text-brand-primary-dark/75 hover:bg-white/25 hover:text-brand-primary-dark",
            )}
          >
            <Icon className="h-4 w-4" aria-hidden />
            {it.label}
          </Link>
        );
      })}
    </nav>
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
    <footer className="mt-auto border-t border-app-border bg-white/70 px-4 py-3 md:px-8">
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
