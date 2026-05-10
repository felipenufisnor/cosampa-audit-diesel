import { Badge } from "@/components/ui/badge";

import type { ValidacaoFinal } from "@/lib/types";

interface Props {
  status: ValidacaoFinal | null;
  /** Indica se a auditoria foi aprovada manualmente pelo auditor. */
  aprovadaManualmente?: boolean;
}

export function StatusBadge({ status, aprovadaManualmente }: Props) {
  if (!status) return <Badge variant="muted">Não auditada</Badge>;
  if (status === "APROVADO")
    return (
      <Badge variant="success">
        {aprovadaManualmente ? "Aprovada (manual)" : "Aprovada"}
      </Badge>
    );
  return <Badge variant="danger">Inconsistente</Badge>;
}
