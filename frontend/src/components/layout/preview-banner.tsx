import { FlaskConical } from "lucide-react";

export function PreviewBanner({ descricao }: { descricao?: string }) {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <FlaskConical
        className="mt-0.5 h-4 w-4 shrink-0 text-amber-600"
        aria-hidden
      />
      <div>
        <p className="font-semibold">Tela em Preview — dados ilustrativos</p>
        <p className="mt-0.5 text-amber-800">
          {descricao ??
            "Os dados exibidos são ilustrativos e não refletem informações reais. Esta funcionalidade estará disponível em uma versão futura da plataforma."}
        </p>
      </div>
    </div>
  );
}
