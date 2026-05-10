import { Badge } from "@/components/ui/badge";

import type { ValidacaoFinal } from "@/lib/types";

interface Props {
  status: ValidacaoFinal | null;
  /** Indica se a auditoria foi aprovada manualmente pelo auditor. */
  aprovadaManualmente?: boolean;
  className?: string;
}

export function StatusBadge({ status, aprovadaManualmente, className }: Props) {
  if (!status)
    return (
      <Badge variant="muted" className={className}>
        Não auditada
      </Badge>
    );
  if (status === "APROVADO")
    return (
      <Badge variant="success" className={className}>
        {aprovadaManualmente ? "Aprovada (manual)" : "Aprovada"}
      </Badge>
    );
  return (
    <Badge variant="danger" className={className}>
      Inconsistente
    </Badge>
  );
}
