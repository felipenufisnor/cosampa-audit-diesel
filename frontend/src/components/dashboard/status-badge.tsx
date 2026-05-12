"use client";

import { UserCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";

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

  if (status === "APROVADO") {
    const badge = (
      <Badge variant="success" className={className}>
        {aprovadaManualmente && (
          <UserCheck className="h-3.5 w-3.5 shrink-0" aria-hidden />
        )}
        Aprovada
      </Badge>
    );
    if (aprovadaManualmente) {
      return (
        <Tooltip content="Aprovada manualmente pelo auditor">
          {badge}
        </Tooltip>
      );
    }
    return badge;
  }

  return (
    <Badge variant="danger" className={className}>
      Inconsistente
    </Badge>
  );
}
