"use client";

/**
 * Preview da funcionalidade "Investigações" (Tarefa 4 da v2).
 *
 * Tela 100% client-side, SEM backend, SEM persistência. Estado local
 * permite drag-and-drop entre colunas e abertura do drawer de detalhe.
 * Marca d'água "PREVIEW" sutil no fundo deixa claro que é simulação.
 *
 * Rota acessível: /investigacoes
 */

import * as React from "react";
import { ChevronRight, Filter, Inbox, Paperclip, X } from "lucide-react";

import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { formatNomeObra } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import {
  COLUNAS,
  type ColunaKanban,
  INVESTIGACOES_MOCK,
  type Investigacao,
  OBRAS,
  type PrioridadeInvestigacao,
  RESPONSAVEIS,
  TIPOS,
  type TipoInconsistencia,
} from "./mock-data";

interface Filtros {
  obra: string | null;
  tipo: TipoInconsistencia | null;
  responsavel: string | null;
  prioridade: PrioridadeInvestigacao | null;
}

export default function InvestigacoesPage() {
  const [cards, setCards] = React.useState<Investigacao[]>(INVESTIGACOES_MOCK);
  const [aberto, setAberto] = React.useState<Investigacao | null>(null);
  const [filtros, setFiltros] = React.useState<Filtros>({
    obra: null,
    tipo: null,
    responsavel: null,
    prioridade: null,
  });

  function moverPara(id: string, destino: ColunaKanban) {
    setCards((prev) =>
      prev.map((c) => (c.id === id ? { ...c, coluna: destino } : c)),
    );
  }

  const filtrados = React.useMemo(() => {
    return cards.filter((c) => {
      if (filtros.obra && c.obra !== filtros.obra) return false;
      if (filtros.tipo && c.tipo !== filtros.tipo) return false;
      if (filtros.responsavel && c.responsavel.nome !== filtros.responsavel)
        return false;
      if (filtros.prioridade && c.prioridade !== filtros.prioridade)
        return false;
      return true;
    });
  }, [cards, filtros]);

  return (
    <div className="relative mx-auto max-w-[1500px] space-y-5">
      <Marcadagua />

      <Breadcrumbs
        items={[{ label: "Dashboard", href: "/" }, { label: "Investigações" }]}
      />

      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
            Preview
          </p>
          <h2 className="mt-1 text-[24px] font-bold tracking-tight text-zinc-950">
            Investigações em andamento
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Kanban para tratativa de inconsistências.
          </p>
        </div>
        <Badge variant="muted" className="text-[12px]">
          Preview - Disponível em versão futura
        </Badge>
      </header>

      <FiltrosBar filtros={filtros} onChange={setFiltros} />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {COLUNAS.map((col) => (
          <Coluna
            key={col.id}
            id={col.id}
            titulo={col.titulo}
            cards={filtrados.filter((c) => c.coluna === col.id)}
            onMover={moverPara}
            onAbrir={(c) => setAberto(c)}
          />
        ))}
      </div>

      {aberto && (
        <DetalheDrawer inv={aberto} onClose={() => setAberto(null)} />
      )}
    </div>
  );
}

function Marcadagua() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
    >
      {Array.from({ length: 6 }).map((_, row) => (
        <div
          key={row}
          className="flex -rotate-[18deg] gap-32 text-[110px] font-black uppercase tracking-[0.3em] text-zinc-400/[0.04]"
          style={{ marginTop: row === 0 ? 80 : 220 }}
        >
          {Array.from({ length: 4 }).map((__, col) => (
            <span key={col}>PREVIEW</span>
          ))}
        </div>
      ))}
    </div>
  );
}

function FiltrosBar({
  filtros,
  onChange,
}: {
  filtros: Filtros;
  onChange: (f: Filtros) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-app-border bg-white px-4 py-3">
      <Filter className="h-4 w-4 text-zinc-500" aria-hidden />
      <Select
        value={filtros.obra}
        onChange={(v) => onChange({ ...filtros, obra: v })}
        opcoes={[...OBRAS]}
        placeholder="Obra"
      />
      <Select
        value={filtros.tipo}
        onChange={(v) => onChange({ ...filtros, tipo: v as TipoInconsistencia | null })}
        opcoes={TIPOS}
        placeholder="Tipo"
      />
      <Select
        value={filtros.responsavel}
        onChange={(v) => onChange({ ...filtros, responsavel: v })}
        opcoes={[...RESPONSAVEIS]}
        placeholder="Responsável"
      />
      <Select
        value={filtros.prioridade}
        onChange={(v) =>
          onChange({ ...filtros, prioridade: v as PrioridadeInvestigacao | null })
        }
        opcoes={["Alta", "Média", "Baixa"]}
        placeholder="Prioridade"
      />
      <button
        type="button"
        onClick={() =>
          onChange({ obra: null, tipo: null, responsavel: null, prioridade: null })
        }
        className="ml-auto text-xs text-zinc-500 hover:text-zinc-800"
      >
        Limpar filtros
      </button>
    </div>
  );
}

function Select({
  value,
  onChange,
  opcoes,
  placeholder,
}: {
  value: string | null;
  onChange: (v: string | null) => void;
  opcoes: string[];
  placeholder: string;
}) {
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      className="rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-700 outline-none focus:border-brand-primary"
    >
      <option value="">{placeholder}</option>
      {opcoes.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

function Coluna({
  id,
  titulo,
  cards,
  onMover,
  onAbrir,
}: {
  id: ColunaKanban;
  titulo: string;
  cards: Investigacao[];
  onMover: (id: string, destino: ColunaKanban) => void;
  onAbrir: (c: Investigacao) => void;
}) {
  const [dragOver, setDragOver] = React.useState(false);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!dragOver) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const draggedId = e.dataTransfer.getData("text/plain");
        if (draggedId) onMover(draggedId, id);
      }}
      className={[
        "rounded-2xl border bg-zinc-50/70 p-3 transition-colors",
        dragOver ? "border-brand-primary bg-brand-primary-light/40" : "border-app-border",
      ].join(" ")}
    >
      <div className="mb-3 flex items-baseline justify-between gap-2 px-1">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-700">
          {titulo}
        </h3>
        <span className="text-xs text-zinc-400 tabular-nums">{cards.length}</span>
      </div>
      <div className="space-y-2">
        {cards.length === 0 ? (
          <div className="flex flex-col items-center gap-1.5 rounded-lg border border-dashed border-zinc-200 px-3 py-8 text-center">
            <Inbox className="h-5 w-5 text-zinc-300" aria-hidden />
            <p className="text-xs font-medium text-zinc-400">
              Nenhuma investigação nesta etapa
            </p>
            <p className="text-[11px] text-zinc-300">
              Arraste um card aqui para movê-lo
            </p>
          </div>
        ) : (
          cards.map((c) => (
            <CardInvestigacao
              key={c.id}
              inv={c}
              onAbrir={() => onAbrir(c)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function dataAbertaFormatada(diasAtras: number): string {
  const d = new Date();
  d.setDate(d.getDate() - diasAtras);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function CardInvestigacao({
  inv,
  onAbrir,
}: {
  inv: Investigacao;
  onAbrir: () => void;
}) {
  return (
    <article
      draggable
      onDragStart={(e) => e.dataTransfer.setData("text/plain", inv.id)}
      onClick={onAbrir}
      className="cursor-pointer rounded-xl border border-app-border bg-white px-3 py-3 shadow-sm transition hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-mono text-[12px] font-semibold text-zinc-500">
          {inv.id}
        </p>
        <Badge variant="muted" className="text-[10px]">
          NF {inv.nf}
        </Badge>
      </div>
      <p className="mt-1.5 line-clamp-2 text-sm leading-snug text-zinc-800">
        {inv.resumo}
      </p>
      {!inv.nf_auditada && (
        <p className="mt-2 rounded-md bg-amber-50 px-2 py-1 text-[11px] leading-snug text-amber-700">
          NF não auditada — métricas estimadas a partir de dados brutos do Infleet
        </p>
      )}
      <div className="mt-2.5 flex items-center justify-between text-xs">
        <span
          className={[
            "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px]",
            inv.prioridade === "Alta"
              ? "bg-red-50 text-red-700"
              : inv.prioridade === "Média"
                ? "bg-amber-50 text-amber-700"
                : "bg-zinc-100 text-zinc-700",
          ].join(" ")}
        >
          {inv.tipo}
        </span>
        <div className="flex items-center gap-2 text-zinc-500">
          <Avatar iniciais={inv.responsavel.iniciais} />
          <span
            className="tabular-nums cursor-default underline decoration-dashed decoration-zinc-400 underline-offset-2"
            title={`Aberta em ${dataAbertaFormatada(inv.aberta_ha_dias)}`}
          >
            {inv.aberta_ha_dias}d
          </span>
        </div>
      </div>
    </article>
  );
}

function Avatar({ iniciais }: { iniciais: string }) {
  return (
    <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-primary-light text-[10px] font-semibold text-brand-primary-dark">
      {iniciais}
    </span>
  );
}

function DetalheDrawer({
  inv,
  onClose,
}: {
  inv: Investigacao;
  onClose: () => void;
}) {
  return (
    <>
      <button
        type="button"
        aria-label="Fechar"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-zinc-900/20"
      />
      <aside
        role="complementary"
        aria-label="Detalhes da investigação"
        className="fixed right-0 top-0 z-50 flex h-screen w-full max-w-[520px] flex-col bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-app-border px-5 py-4">
          <div>
            <p className="font-mono text-[12px] font-semibold text-zinc-500">
              {inv.id}
            </p>
            <h3 className="mt-0.5 text-lg font-semibold text-zinc-950">
              NF {inv.nf} - {inv.tipo}
            </h3>
            <p className="text-xs text-zinc-500">
              {formatNomeObra(inv.obra)} - {inv.responsavel.nome} - aberta há {inv.aberta_ha_dias}d
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="rounded-md p-1 text-zinc-500 hover:bg-zinc-100"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          <p className="text-sm leading-relaxed text-zinc-700">{inv.resumo}</p>

          {!inv.nf_auditada && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <p className="font-semibold">NF {inv.nf} ainda não foi formalmente auditada</p>
              <p className="mt-0.5 text-amber-700">
                As métricas percentuais (ex.: −7,4%) foram estimadas diretamente sobre os dados brutos do Infleet, sem validação formal. Confirme os valores antes de usar como base para autuação.
              </p>
            </div>
          )}

          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Timeline da investigação
            </h4>
            <ol className="space-y-2">
              {inv.timeline.map((e, i) => (
                <li
                  key={i}
                  className="flex items-start gap-3 rounded-lg border border-app-border bg-zinc-50 px-3 py-2 text-sm"
                >
                  <span className="mt-0.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-400" />
                  <div className="min-w-0 flex-1">
                    <p className="font-mono text-[11px] text-zinc-500">
                      {e.data}
                    </p>
                    <p className="mt-0.5 text-zinc-800">{e.texto}</p>
                  </div>
                  {e.marca && (
                    <span className="rounded-full bg-white px-2 py-0.5 text-[10px] uppercase tracking-wide text-zinc-500">
                      {e.marca}
                    </span>
                  )}
                </li>
              ))}
            </ol>
          </section>

          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Evidências anexadas
            </h4>
            {inv.evidencias.length === 0 ? (
              <p className="rounded-lg border border-dashed border-zinc-200 px-3 py-4 text-center text-xs text-zinc-400">
                Nenhuma evidência anexada até o momento.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {inv.evidencias.map((ev) => (
                  <li
                    key={ev.nome}
                    className="flex items-center justify-between rounded-lg border border-app-border bg-white px-3 py-2 text-sm"
                  >
                    <span className="flex items-center gap-2 text-zinc-800">
                      <Paperclip className="h-3.5 w-3.5 text-zinc-500" aria-hidden />
                      <span className="font-medium">{ev.nome}</span>
                      <span className="text-[11px] uppercase text-zinc-400">
                        {ev.tipo}
                      </span>
                    </span>
                    <span className="text-xs text-zinc-500 tabular-nums">
                      {ev.tamanho_kb} KB
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <div className="mb-2 flex items-baseline gap-2">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
                Análise automática sobre as evidências
              </h4>
              <span className="text-[10px] font-medium uppercase tracking-wide text-zinc-400">
                Escopo: esta investigação
              </span>
            </div>
            <p className="rounded-xl border border-brand-primary/20 bg-brand-primary-light/40 px-4 py-3 text-sm leading-relaxed text-zinc-800">
              {inv.analise_automatica}
            </p>
          </section>
        </div>

        <footer className="flex flex-wrap items-center gap-2 border-t border-app-border bg-zinc-50 px-5 py-3">
          <Button variant="ghost" size="sm" title="Ação ilustrativa (preview)">
            Encerrar com correção
          </Button>
          <Button variant="secondary" size="sm" title="Ação ilustrativa (preview)">
            Solicitar mais informações
          </Button>
          <Button variant="primary" size="sm" title="Ação ilustrativa (preview)">
            Escalar <ChevronRight className="h-3.5 w-3.5" aria-hidden />
          </Button>
        </footer>
      </aside>
    </>
  );
}
