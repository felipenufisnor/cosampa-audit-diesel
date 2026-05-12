import type { Healthz } from "./types";

export function hasAssistantHealthContract(value: unknown): value is Healthz {
  if (typeof value !== "object" || value === null) return false;
  const maybe = value as Record<string, unknown>;
  return (
    typeof maybe["assistant_status"] === "string" &&
    typeof maybe["assistant_reason"] === "string" &&
    typeof maybe["assistant_can_answer_free_text"] === "boolean" &&
    typeof maybe["assistant_has_cached_answers"] === "boolean"
  );
}

export const BACKEND_CONTRACT_ERROR =
  "Backend desatualizado ou não reiniciado. Reinicie a API e confirme /healthz com os campos assistant_status.";
