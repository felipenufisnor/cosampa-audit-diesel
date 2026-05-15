"use client";

/**
 * Drawer do Assistente de Investigacao (Feature B da v2).
 *
 * Drawer lateral direito (NAO modal, NAO sticky-bar). Abre/fecha por estado
 * controlado pelo pai. Carrega historico persistido ao abrir (GET
 * /auditorias/{id}/mensagens). Submete perguntas via POST
 * /auditorias/{id}/perguntar (SSE) e renderiza chunks em streaming.
 *
 * Chamadas de tool aparecem entre mensagens, em texto cinza pequeno:
 *   "Consultando historico do veiculo 13.T881..."
 *   "Historico recebido (28 dias, 14 abastecimentos)."
 */

import * as React from "react";
import { AlertTriangle, Send, Sparkle, X } from "lucide-react";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAssistenteStatus,
  usePerguntasSugeridas,
} from "@/hooks/use-assistente";
import {
  BACKEND_CONTRACT_ERROR,
  hasAssistantHealthContract,
} from "@/lib/assistant-contract";
import { api } from "@/lib/api";
import type {
  AssistantStreamEvent,
  AuditoriaIndicadores,
  MensagemAssistente,
  PerguntaSugerida,
} from "@/lib/types";

interface ToolNote {
  kind: "tool";
  id: string;
  texto: string;
}

interface ChatMessage {
  kind: "user" | "assistant";
  id: string;
  texto: string;
  streaming?: boolean;
}

type LogItem = ChatMessage | ToolNote;

interface Props {
  open: boolean;
  onClose: () => void;
  auditoria: AuditoriaIndicadores;
  perguntaInicial?: string | null;
}

export function AssistenteDrawer({
  open,
  onClose,
  auditoria,
  perguntaInicial,
}: Props) {
  const [log, setLog] = React.useState<LogItem[]>([]);
  const [input, setInput] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [historicoCarregado, setHistoricoCarregado] = React.useState(false);
  const [erro, setErro] = React.useState<string | null>(null);
  const abortRef = React.useRef<AbortController | null>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const submitedInitialRef = React.useRef(false);

  const statusQuery = useAssistenteStatus(open);
  const health = statusQuery.data;
  const statusPendente = statusQuery.isLoading && !health;
  const contratoOk = hasAssistantHealthContract(health);
  const contratoInvalido = Boolean(health && !contratoOk);
  const podePerguntaLivre =
    contratoOk &&
    health.assistant_can_answer_free_text === true &&
    !statusQuery.isError;
  const statusAssistente = contratoOk ? health.assistant_status : undefined;
  const sugeridasQuery = usePerguntasSugeridas(auditoria.id, open);
  const perguntasCacheadas = React.useMemo(
    () => sugeridasQuery.data?.perguntas ?? [],
    [sugeridasQuery.data?.perguntas],
  );
  const temRespostaCacheada = React.useCallback(
    (pergunta: string) =>
      perguntasCacheadas.some((p) => p.pergunta.trim() === pergunta.trim()),
    [perguntasCacheadas],
  );

  // Carrega historico persistido quando o drawer abre.
  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api
      .listarMensagensAssistente(auditoria.id)
      .then((h) => {
        if (cancelled) return;
        setLog(h.mensagens.map(_paraLogItem));
        setHistoricoCarregado(true);
      })
      .catch(() => {
        if (cancelled) return;
        setHistoricoCarregado(true);
      });
    return () => {
      cancelled = true;
    };
  }, [open, auditoria.id]);

  // Pergunta inicial (vinda de Feature C "Investigar")
  React.useEffect(() => {
    if (!open || !historicoCarregado) return;
    if (statusPendente) return;
    if (!perguntaInicial || submitedInitialRef.current) return;
    submitedInitialRef.current = true;
    submeter(perguntaInicial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, historicoCarregado, perguntaInicial, statusPendente]);

  // Scroll para baixo sempre que o log cresce
  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [log]);

  // Cleanup do fetch ao fechar
  React.useEffect(() => {
    if (!open && abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
      setBusy(false);
    }
  }, [open]);

  async function submeter(pergunta: string) {
    const trimmed = pergunta.trim();
    if (!trimmed || busy) return;
    setErro(null);
    if (!podePerguntaLivre && !temRespostaCacheada(trimmed)) {
      setErro(
        contratoInvalido
          ? BACKEND_CONTRACT_ERROR
          : "Assistente de IA indisponível e sem resposta pré-carregada para esta pergunta. Configure a IA ou consulte os alertas desta auditoria.",
      );
      return;
    }
    setBusy(true);
    setInput("");
    const userId = `u-${Date.now()}`;
    const aid = `a-${Date.now()}`;
    setLog((prev) => [
      ...prev,
      { kind: "user", id: userId, texto: trimmed },
      { kind: "assistant", id: aid, texto: "", streaming: true },
    ]);

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      await api.streamPergunta(
        auditoria.id,
        trimmed,
        (ev: AssistantStreamEvent) => {
          setLog((prev) => atualizar(prev, aid, ev));
        },
        ctrl.signal,
      );
    } catch (e) {
      if (!ctrl.signal.aborted) {
        setErro(e instanceof Error ? e.message : "Falha ao consultar o assistente");
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
      setLog((prev) =>
        prev.map((it) =>
          it.kind === "assistant" && it.id === aid ? { ...it, streaming: false } : it,
        ),
      );
    }
  }

  if (!open) return null;

  return (
    <>
      <button
        type="button"
        aria-label="Fechar assistente"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-zinc-900/15"
      />
      <aside
        role="complementary"
        aria-label="Assistente de investigação"
        className="fixed right-0 top-0 z-50 flex h-screen w-full max-w-[440px] flex-col bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-app-border px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-brand-primary-dark">
              Assistente
            </p>
            <h3 className="mt-1 text-base font-semibold text-zinc-950">
              Auditoria NF {auditoria.nf_atual}
            </h3>
            <p className="text-xs text-zinc-500">
              Conversa restrita ao contexto desta NF.
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

        {!podePerguntaLivre && !statusPendente && (
          <div
            role="status"
            className="border-b border-amber-200 bg-amber-50 px-5 py-3"
          >
            <div className="flex gap-2">
              <AlertTriangle
                className="h-4 w-4 flex-shrink-0 text-amber-600 mt-0.5"
                aria-hidden
              />
              <div className="text-[13px] leading-relaxed text-amber-900">
                <p className="font-semibold">
                  {contratoInvalido
                    ? "Backend desatualizado"
                    : perguntasCacheadas.length > 0
                    ? "Assistente de IA em modo degradado"
                    : "Assistente de IA indisponível"}
                </p>
                <p className="mt-0.5 text-amber-800">
                  {contratoInvalido
                    ? BACKEND_CONTRACT_ERROR
                    : perguntasCacheadas.length > 0
                    ? "Perguntas livres estão pausadas. Use uma das respostas pré-carregadas abaixo enquanto o serviço é restabelecido."
                    : "Sem respostas pré-carregadas para esta auditoria. Configure a IA ou consulte os alertas listados nesta NF."}
                </p>
              </div>
            </div>
          </div>
        )}

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {!historicoCarregado && (
            <Skeleton className="h-14 w-full" />
          )}
          {historicoCarregado && log.length === 0 && (
            <div className="rounded-xl border border-app-border bg-zinc-50 px-4 py-3 text-sm text-zinc-600">
              Faça uma pergunta sobre esta auditoria. O assistente pode consultar
              o cadastro do GP, o histórico do veículo e comparar com auditorias
              anteriores.
            </div>
          )}
          {log.map((it) =>
            it.kind === "tool" ? (
              <p
                key={it.id}
                className="px-1 text-[12px] leading-relaxed text-zinc-500"
              >
                {it.texto}
              </p>
            ) : (
              <MessageBubble key={it.id} msg={it} />
            ),
          )}
          {erro && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {erro}
            </p>
          )}
        </div>

        <footer className="border-t border-app-border bg-zinc-50/60 px-4 py-3">
          <Chips
            auditoria={auditoria}
            disabled={busy}
            offline={!podePerguntaLivre || statusAssistente === "degraded_cache"}
            cacheadas={perguntasCacheadas}
            onPick={(q) => submeter(q)}
          />
          <form
            className="mt-2 flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              submeter(input);
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                !podePerguntaLivre
                  ? perguntasCacheadas.length > 0
                    ? "Use as perguntas pré-carregadas"
                    : "IA indisponível e sem cache para esta auditoria"
                  : "Pergunte sobre essa auditoria..."
              }
              disabled={busy || !podePerguntaLivre || statusPendente}
              className="flex-1 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:border-brand-primary"
            />
            <Button
              type="submit"
              disabled={busy || !podePerguntaLivre || statusPendente || !input.trim()}
              size="sm"
            >
              {busy ? (
                <Sparkle className="h-4 w-4 animate-pulse" aria-hidden />
              ) : (
                <Send className="h-4 w-4" aria-hidden />
              )}
            </Button>
          </form>
        </footer>
      </aside>
    </>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.kind === "user";
  return (
    <div
      className={
        isUser
          ? "rounded-xl border border-app-border bg-white px-3.5 py-2.5"
          : "rounded-xl border border-brand-primary-medium/20 bg-brand-primary-light/55 px-3.5 py-2.5"
      }
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
        {isUser ? "Você" : "Assistente"}
      </p>
      {isUser ? (
        <p className="mt-1 whitespace-pre-wrap text-[14.5px] leading-relaxed text-zinc-800">
          {msg.texto}
        </p>
      ) : msg.texto ? (
        <div className="mt-1 text-[14.5px] leading-relaxed text-zinc-800">
          <ReactMarkdown
            components={{
              p: ({ children }) => <p className="my-1">{children}</p>,
              strong: ({ children }) => <strong className="font-semibold text-zinc-900">{children}</strong>,
              em: ({ children }) => <em className="italic">{children}</em>,
              ul: ({ children }) => <ul className="my-1 list-disc pl-5">{children}</ul>,
              ol: ({ children }) => <ol className="my-1 list-decimal pl-5">{children}</ol>,
              li: ({ children }) => <li className="my-0.5">{children}</li>,
              h1: ({ children }) => <h1 className="mb-1 mt-2 text-base font-bold">{children}</h1>,
              h2: ({ children }) => <h2 className="mb-1 mt-2 text-[15px] font-bold">{children}</h2>,
              h3: ({ children }) => <h3 className="mb-0.5 mt-1.5 text-[14.5px] font-semibold">{children}</h3>,
              code: ({ children }) => <code className="rounded bg-white/75 px-1 py-0.5 font-mono text-[13px] text-brand-primary-dark ring-1 ring-brand-primary-medium/15">{children}</code>,
            }}
          >
            {msg.texto}
          </ReactMarkdown>
        </div>
      ) : msg.streaming ? (
        <span className="mt-1 text-[14.5px] text-zinc-400">Pensando...</span>
      ) : null}
    </div>
  );
}

function Chips({
  auditoria,
  disabled,
  offline,
  cacheadas,
  onPick,
}: {
  auditoria: AuditoriaIndicadores;
  disabled: boolean;
  offline: boolean;
  cacheadas: PerguntaSugerida[];
  onPick: (q: string) => void;
}) {
  // Em offline, mostramos exclusivamente as perguntas cacheadas — sao as
  // unicas que vao retornar resposta util. Online, mantemos sugestoes
  // contextuais derivadas da auditoria.
  const sugestoes = React.useMemo(() => {
    if (offline) {
      return cacheadas.map((p) => ({ pergunta: p.pergunta, cacheada: true }));
    }
    const out: { pergunta: string; cacheada: boolean }[] = [];
    if (auditoria.qtd_equipamentos_nao_cadastrados > 0) {
      out.push({
        pergunta: "Quais veículos não estão cadastrados nesta NF?",
        cacheada: false,
      });
    }
    out.push({
      pergunta: "Compare o consumo desta NF com a NF anterior",
      cacheada: false,
    });
    out.push({
      pergunta: "Qual o impacto financeiro dos alertas desta auditoria?",
      cacheada: false,
    });
    out.push({
      pergunta: "Existe algum padrão suspeito nesta auditoria?",
      cacheada: false,
    });
    return out.slice(0, 4);
  }, [auditoria, offline, cacheadas]);

  if (offline && sugestoes.length === 0) {
    return (
      <p className="text-[12px] text-zinc-500">
        Nenhuma pergunta sugerida com resposta disponível para esta auditoria.
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {sugestoes.map((s) => (
        <button
          key={s.pergunta}
          type="button"
          disabled={disabled}
          onClick={() => onPick(s.pergunta)}
          title={s.cacheada ? "Resposta disponível agora" : undefined}
          className={
            s.cacheada
              ? "rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[12px] text-amber-900 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
              : "rounded-full border border-zinc-200 bg-white px-2.5 py-1 text-[12px] text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50"
          }
        >
          {s.pergunta}
        </button>
      ))}
    </div>
  );
}

function _paraLogItem(m: MensagemAssistente): LogItem {
  return {
    kind: m.papel,
    id: `db-${m.id}`,
    texto: m.conteudo,
  };
}

function atualizar(
  prev: LogItem[],
  assistantId: string,
  ev: AssistantStreamEvent,
): LogItem[] {
  switch (ev.event) {
    case "assistant_status": {
      const note: ToolNote = {
        kind: "tool",
        id: `status-${Date.now()}-${Math.random()}`,
        texto: String(ev.payload["mensagem"] ?? "Preparando resposta..."),
      };
      const idx = prev.findIndex((it) => it.kind === "assistant" && it.id === assistantId);
      if (idx < 0) return [...prev, note];
      const novo = [...prev];
      novo.splice(idx, 0, note);
      return novo;
    }
    case "tool_call_started": {
      const nome = String(ev.payload["nome"] ?? "");
      const args = ev.payload["argumentos"] as Record<string, unknown> | undefined;
      const arg_str = args
        ? Object.entries(args)
            .map(([k, v]) => `${k}=${String(v)}`)
            .join(", ")
        : "";
      const note: ToolNote = {
        kind: "tool",
        id: `tc-${Date.now()}-${Math.random()}`,
        texto: `Consultando ${nome}${arg_str ? ` (${arg_str})` : ""}...`,
      };
      const idx = prev.findIndex((it) => it.kind === "assistant" && it.id === assistantId);
      if (idx < 0) return [...prev, note];
      // Insere antes do bubble streaming.
      const novo = [...prev];
      novo.splice(idx, 0, note);
      return novo;
    }
    case "tool_call_completed": {
      const note: ToolNote = {
        kind: "tool",
        id: `tcc-${Date.now()}-${Math.random()}`,
        texto: `${ev.payload["nome"]}: ${ev.payload["resultado_resumo"] ?? "ok"}`,
      };
      const idx = prev.findIndex((it) => it.kind === "assistant" && it.id === assistantId);
      if (idx < 0) return [...prev, note];
      const novo = [...prev];
      novo.splice(idx, 0, note);
      return novo;
    }
    case "assistant_chunk": {
      return prev.map((it) =>
        it.kind === "assistant" && it.id === assistantId
          ? { ...it, texto: it.texto + String(ev.payload["texto"] ?? "") }
          : it,
      );
    }
    case "assistant_done": {
      return prev.map((it) =>
        it.kind === "assistant" && it.id === assistantId
          ? {
              ...it,
              streaming: false,
              texto: it.texto || String(ev.payload["mensagem_completa"] ?? ""),
            }
          : it,
      );
    }
    case "error": {
      const note: ToolNote = {
        kind: "tool",
        id: `err-${Date.now()}`,
        texto: `Erro: ${ev.payload["mensagem"] ?? "indefinido"}`,
      };
      return [...prev, note];
    }
    default:
      return prev;
  }
}
