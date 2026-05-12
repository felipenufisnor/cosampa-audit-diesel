/** Formatadores pt-BR utilizados em tabelas, cards e detalhes. */

const BRL = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const NUM = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const NUM0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const PCT = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  signDisplay: "exceptZero",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const DATE = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const DATETIME = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatBRL(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return BRL.format(v);
}

export function formatLitros(v: number | null | undefined, decimais = 2): string {
  if (v === null || v === undefined) return "-";
  const fmt = decimais === 0 ? NUM0 : NUM;
  return `${fmt.format(v)} L`;
}

export function formatNumero(v: number | null | undefined, decimais = 0): string {
  if (v === null || v === undefined) return "-";
  return decimais === 0 ? NUM0.format(v) : NUM.format(v);
}

export function formatPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return PCT.format(v);
}

export function formatDateBR(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  return DATE.format(d);
}

export function formatDateTimeBR(iso: string | null | undefined): string {
  if (!iso) return "-";
  return DATETIME.format(new Date(iso));
}

export function formatHora(s: string | null | undefined): string {
  if (!s) return "-";
  // Backend manda "HH:MM" para hora_inicio/final.
  return s.slice(0, 5);
}

// Planilhas do cliente frequentemente omitem acentos. Corrige casos conhecidos
// apenas para exibição — não altera o dado armazenado.
const _CORRECOES_OBRA: [RegExp, string][] = [
  [/\bCONSORCIO\b/g, "CONSÓRCIO"],
];

export function formatNomeObra(nome: string | null | undefined): string {
  if (!nome) return "-";
  return _CORRECOES_OBRA.reduce((s, [re, sub]) => s.replace(re, sub), nome);
}
