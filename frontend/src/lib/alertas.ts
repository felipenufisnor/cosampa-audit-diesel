import type { TipoAlerta } from "@/lib/types";

export const ALERTA_TIPO_LABEL: Record<TipoAlerta, string> = {
  NAO_CADASTRADO: "Não cadastrado",
  POS_DESMOB: "Pós-desmobilização",
  OUTLIER: "Outlier",
  DUPLICIDADE: "Duplicidade",
};

export const ALERTA_TIPO_BADGE_VARIANT: Record<
  TipoAlerta,
  "danger" | "warn" | "duplicate"
> = {
  NAO_CADASTRADO: "danger",
  POS_DESMOB: "warn",
  OUTLIER: "danger",
  DUPLICIDADE: "duplicate",
};

export const ALERTA_TIPO_COUNT_CLASS: Record<TipoAlerta, string> = {
  NAO_CADASTRADO: "border-red-200 bg-red-50 text-red-700",
  POS_DESMOB: "border-amber-200 bg-amber-50 text-amber-800",
  OUTLIER: "border-red-200 bg-red-50 text-red-700",
  DUPLICIDADE: "border-violet-200 bg-violet-50 text-violet-800",
};
