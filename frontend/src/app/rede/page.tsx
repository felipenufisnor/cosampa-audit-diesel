"use client";

/**
 * Preview "Análise de Rede" (Tarefa 4 da v2).
 *
 * Grafo de relacionamentos 100% client-side, renderizado em SVG com
 * posições curadas à mão (sem algoritmo de layout). Três clusters suspeitos
 * pré-rotulados são destacados com retângulos de fundo sutis para
 * narrativa de demo. Painel lateral mostra o nó selecionado.
 *
 * Rota acessível: /rede
 */

import * as React from "react";
import { X } from "lucide-react";

import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

import {
  ARESTAS,
  CLUSTERS,
  type ClusterSuspeito,
  NOS,
  type NoGrafo,
  type TipoNo,
  TIPOS_NO,
} from "./mock-data";

const VB_W = 1200;
const VB_H = 720;

const COR_POR_TIPO: Record<TipoNo, string> = {
  obra: "#1e3a8a",
  veiculo: "#0f766e",
  fornecedor: "#7c2d12",
  operador: "#475569",
};

const FILL_POR_TIPO: Record<TipoNo, string> = {
  obra: "#dbeafe",
  veiculo: "#ccfbf1",
  fornecedor: "#fed7aa",
  operador: "#e2e8f0",
};

const LABEL_POR_TIPO: Record<TipoNo, string> = {
  obra: "obra",
  veiculo: "veículo",
  fornecedor: "fornecedor",
  operador: "operador",
};

export default function RedePage() {
  const [tiposVisiveis, setTiposVisiveis] = React.useState<Set<TipoNo>>(
    new Set(TIPOS_NO.map((t) => t.id)),
  );
  const [noSelecionado, setNoSelecionado] = React.useState<string | null>(null);
  const [clusterDestacado, setClusterDestacado] = React.useState<string | null>(null);

  const nosVisiveis = React.useMemo(
    () => NOS.filter((n) => tiposVisiveis.has(n.tipo)),
    [tiposVisiveis],
  );
  const idsVisiveis = React.useMemo(
    () => new Set(nosVisiveis.map((n) => n.id)),
    [nosVisiveis],
  );
  const arestasVisiveis = React.useMemo(
    () => ARESTAS.filter((a) => idsVisiveis.has(a.de) && idsVisiveis.has(a.para)),
    [idsVisiveis],
  );

  function toggleTipo(t: TipoNo) {
    setTiposVisiveis((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  }

  const noFocado: NoGrafo | null = noSelecionado
    ? (NOS.find((n) => n.id === noSelecionado) ?? null)
    : null;
  const vizinhos = React.useMemo(() => {
    if (!noFocado) return [] as NoGrafo[];
    const ids = new Set<string>();
    ARESTAS.forEach((a) => {
      if (a.de === noFocado.id) ids.add(a.para);
      if (a.para === noFocado.id) ids.add(a.de);
    });
    return NOS.filter((n) => ids.has(n.id));
  }, [noFocado]);

  return (
    <div className="relative mx-auto max-w-[1500px] space-y-5">
      <Marcadagua />

      <Breadcrumbs
        items={[{ label: "Dashboard", href: "/" }, { label: "Análise de rede" }]}
      />

      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
            Preview
          </p>
          <h2 className="mt-1 text-[24px] font-bold tracking-tight text-zinc-950">
            Análise de rede
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Grafo de relacionamentos entre obras, veículos, fornecedores e
            operadores. Clusters destacados foram pré-identificados pelo
            sistema como potencialmente suspeitos.
          </p>
        </div>
        <Badge variant="muted" className="text-[12px]">
          Preview - Disponível em versão futura
        </Badge>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        <div className="rounded-2xl border border-app-border bg-white p-4">
          <Toolbar
            tiposVisiveis={tiposVisiveis}
            onToggle={toggleTipo}
            clusterDestacado={clusterDestacado}
            onClusterHover={setClusterDestacado}
          />

          <svg
            viewBox={`0 0 ${VB_W} ${VB_H}`}
            className="mt-3 h-[560px] w-full"
            role="img"
            aria-label="Grafo de relacionamentos"
          >
            {/* Clusters de fundo */}
            {CLUSTERS.map((c) => (
              <ClusterBackground
                key={c.id}
                cluster={c}
                destacado={clusterDestacado === c.id}
              />
            ))}

            {/* Arestas */}
            <g>
              {arestasVisiveis.map((a, i) => {
                const A = NOS.find((n) => n.id === a.de);
                const B = NOS.find((n) => n.id === a.para);
                if (!A || !B) return null;
                const ehVizinho =
                  noFocado &&
                  (a.de === noFocado.id || a.para === noFocado.id);
                return (
                  <line
                    key={i}
                    x1={A.x}
                    y1={A.y}
                    x2={B.x}
                    y2={B.y}
                    stroke={a.destacada ? "#b91c1c" : "#94a3b8"}
                    strokeWidth={a.destacada ? 1.6 : 1}
                    strokeOpacity={
                      noFocado ? (ehVizinho ? 0.95 : 0.18) : a.destacada ? 0.55 : 0.4
                    }
                  />
                );
              })}
            </g>

            {/* Nos */}
            <g>
              {nosVisiveis.map((n) => (
                <NoSvg
                  key={n.id}
                  n={n}
                  ativo={noSelecionado === n.id}
                  esmaecido={
                    noFocado != null &&
                    n.id !== noFocado.id &&
                    !vizinhos.includes(n)
                  }
                  onClick={() => setNoSelecionado(n.id === noSelecionado ? null : n.id)}
                />
              ))}
            </g>

            {/* Rotulos dos clusters */}
            {CLUSTERS.map((c) => (
              <text
                key={`lbl-${c.id}`}
                x={c.bbox.x + 12}
                y={c.bbox.y + 22}
                className="fill-zinc-500"
                fontSize="11"
                fontWeight="600"
                opacity={clusterDestacado === c.id ? 0.85 : 0.5}
              >
                {c.titulo.toUpperCase()}
              </text>
            ))}
          </svg>

          <Legenda />
        </div>

        <PainelLateral
          no={noFocado}
          vizinhos={vizinhos}
          clusters={CLUSTERS}
          onClusterHover={setClusterDestacado}
          onClusterClick={(c) => {
            // Foca o primeiro id do cluster.
            if (c.ids[0]) setNoSelecionado(c.ids[0]);
          }}
          onLimpar={() => setNoSelecionado(null)}
        />
      </div>

    </div>
  );
}

function Toolbar({
  tiposVisiveis,
  onToggle,
  clusterDestacado,
  onClusterHover,
}: {
  tiposVisiveis: Set<TipoNo>;
  onToggle: (t: TipoNo) => void;
  clusterDestacado: string | null;
  onClusterHover: (id: string | null) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {TIPOS_NO.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => onToggle(t.id)}
            className={[
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px]",
              tiposVisiveis.has(t.id)
                ? "border-zinc-300 bg-white text-zinc-800"
                : "border-zinc-200 bg-zinc-100 text-zinc-400 line-through",
            ].join(" ")}
          >
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: COR_POR_TIPO[t.id] }}
              aria-hidden
            />
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5 text-[11px] text-zinc-500">
        <span>Clusters detectados:</span>
        {CLUSTERS.map((c) => (
          <button
            key={c.id}
            type="button"
            onMouseEnter={() => onClusterHover(c.id)}
            onMouseLeave={() => onClusterHover(null)}
            className={[
              "rounded-full border px-2 py-0.5",
              c.severidade === "alta"
                ? "border-red-200 text-red-700"
                : "border-amber-200 text-amber-700",
              clusterDestacado === c.id ? "bg-zinc-50" : "bg-white",
            ].join(" ")}
          >
            {c.titulo}
          </button>
        ))}
      </div>
    </div>
  );
}

function ClusterBackground({
  cluster,
  destacado,
}: {
  cluster: ClusterSuspeito;
  destacado: boolean;
}) {
  const fill = cluster.severidade === "alta" ? "#fee2e2" : "#fef3c7";
  return (
    <rect
      x={cluster.bbox.x}
      y={cluster.bbox.y}
      width={cluster.bbox.w}
      height={cluster.bbox.h}
      rx={18}
      fill={fill}
      opacity={destacado ? 0.7 : 0.35}
      stroke={cluster.severidade === "alta" ? "#fca5a5" : "#fcd34d"}
      strokeWidth={destacado ? 1.5 : 0.8}
      strokeDasharray="4 4"
    />
  );
}

function NoSvg({
  n,
  ativo,
  esmaecido,
  onClick,
}: {
  n: NoGrafo;
  ativo: boolean;
  esmaecido: boolean;
  onClick: () => void;
}) {
  const r =
    n.tipo === "obra" ? 26 : n.tipo === "veiculo" ? 18 : n.tipo === "fornecedor" ? 22 : 16;
  const stroke =
    n.destaque === "alta" ? "#b91c1c" : n.destaque === "media" ? "#b45309" : COR_POR_TIPO[n.tipo];
  return (
    <g
      transform={`translate(${n.x},${n.y})`}
      style={{ cursor: "pointer", opacity: esmaecido ? 0.25 : 1 }}
      onClick={onClick}
      aria-label={n.rotulo}
    >
      <circle
        r={r}
        fill={FILL_POR_TIPO[n.tipo]}
        stroke={stroke}
        strokeWidth={ativo ? 3 : n.destaque ? 2 : 1.2}
      />
      <text
        y={r + 13}
        textAnchor="middle"
        className="fill-zinc-700"
        fontSize="11"
        fontWeight={n.destaque ? 600 : 500}
      >
        {n.rotulo}
      </text>
    </g>
  );
}

function Legenda() {
  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-app-border pt-3 text-[11px] text-zinc-500">
      <div className="flex flex-wrap gap-3">
        {TIPOS_NO.map((t) => (
          <span key={t.id} className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-3 rounded-full border"
              style={{
                background: FILL_POR_TIPO[t.id],
                borderColor: COR_POR_TIPO[t.id],
              }}
              aria-hidden
            />
            {t.label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-3 w-3 rounded-full border-2 border-red-700"
            aria-hidden
          />
          severidade alta
        </span>
      </div>
      <p className="text-zinc-400">
        Clique em um nó para isolar conexões. Toggle os tipos no topo.
      </p>
    </div>
  );
}

function PainelLateral({
  no,
  vizinhos,
  clusters,
  onClusterHover,
  onClusterClick,
  onLimpar,
}: {
  no: NoGrafo | null;
  vizinhos: NoGrafo[];
  clusters: ClusterSuspeito[];
  onClusterHover: (id: string | null) => void;
  onClusterClick: (c: ClusterSuspeito) => void;
  onLimpar: () => void;
}) {
  if (no) {
    return (
      <Card>
        <CardContent className="space-y-4 py-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                {LABEL_POR_TIPO[no.tipo]}
              </p>
              <h3 className="mt-0.5 text-lg font-semibold text-zinc-950">
                {no.rotulo}
              </h3>
              {no.detalhe && (
                <p className="text-xs text-zinc-500">{no.detalhe}</p>
              )}
            </div>
            <button
              type="button"
              onClick={onLimpar}
              aria-label="Limpar seleção"
              className="rounded-md p-1 text-zinc-500 hover:bg-zinc-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div>
            <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
              Vizinhos diretos ({vizinhos.length})
            </h4>
            <ul className="space-y-1.5">
              {vizinhos.map((v) => (
                <li
                  key={v.id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-app-border bg-white px-3 py-2 text-sm"
                >
                  <span className="flex items-center gap-2">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ background: COR_POR_TIPO[v.tipo] }}
                      aria-hidden
                    />
                    <span className="text-zinc-800">{v.rotulo}</span>
                  </span>
                  <span className="text-[11px] uppercase text-zinc-400">
                    {LABEL_POR_TIPO[v.tipo]}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="space-y-3 py-4">
        <h3 className="text-base font-semibold text-zinc-950">
          Clusters suspeitos
        </h3>
        <p className="text-xs text-zinc-500">
          Três agrupamentos pré-detectados pelo sistema. Passe o mouse para
          destacar no grafo.
        </p>
        <ul className="space-y-2">
          {clusters.map((c) => (
            <li
              key={c.id}
              onMouseEnter={() => onClusterHover(c.id)}
              onMouseLeave={() => onClusterHover(null)}
              onClick={() => onClusterClick(c)}
              className="cursor-pointer rounded-xl border border-app-border bg-white px-3 py-2.5"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-zinc-900">{c.titulo}</p>
                <Badge variant="muted" className="text-[10px]">
                  {c.severidade}
                </Badge>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-zinc-600">
                {c.descricao}
              </p>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
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
