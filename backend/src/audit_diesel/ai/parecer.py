"""GeradorParecer: produz markdown estruturado a partir de uma auditoria."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from . import cache
from .client import ChatClient, ChatMessage
from .parecer_deterministico import gerar_parecer_deterministico
from .parecer_guardrails import validar_parecer
from .prompts import parecer as prompts
from .provider import ProviderInfo

log = structlog.get_logger("audit_diesel.ai.parecer")


@dataclass
class ParecerResult:
    """Saida do gerador: texto markdown + metadados de auditabilidade."""

    markdown: str
    modelo: str | None
    provider: str
    offline: bool
    latency_s: float
    prompt_tokens: int
    completion_tokens: int


class GeradorParecer:
    """Encapsula a chamada do LLM para produzir o parecer."""

    def __init__(self, client: ChatClient | None = None) -> None:
        self.client = client or ChatClient()

    def gerar(self, auditoria_payload: dict[str, Any]) -> ParecerResult:
        nf_anterior = str(auditoria_payload.get("auditoria", {}).get("nf_anterior") or "")
        nf_atual = str(auditoria_payload.get("auditoria", {}).get("nf_atual") or "")

        # Cache hit em DEMO_MODE=true: resposta instantanea, identica a cada
        # execucao da demo, imune a oscilacao do provider.
        cached = cache.get_cached_parecer(nf_anterior, nf_atual)
        if cached:
            return ParecerResult(
                markdown=str(cached.get("markdown") or "").strip(),
                modelo=cached.get("modelo"),
                provider=str(cached.get("provider") or "demo_cache"),
                offline=True,
                latency_s=0.0,
                prompt_tokens=int(cached.get("prompt_tokens") or 0),
                completion_tokens=int(cached.get("completion_tokens") or 0),
            )

        user_msg = prompts.montar_user_message(auditoria_payload)
        response = self.client.chat(
            messages=[
                ChatMessage(role="system", content=prompts.SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_msg),
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        response = self._ensure_valid_response(response, auditoria_payload)
        provider = response.provider
        result = ParecerResult(
            markdown=response.content.strip(),
            modelo=response.model,
            provider=provider.name if provider else "unknown",
            offline=bool(provider and provider.offline),
            latency_s=response.latency_s,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )
        log.info(
            "parecer.generated",
            provider=result.provider,
            offline=result.offline,
            words=len(result.markdown.split()),
            latency_s=round(result.latency_s, 3),
        )
        if nf_anterior and nf_atual:
            cache.save_cached_parecer(nf_anterior, nf_atual, result)
        return result

    def _ensure_valid_response(self, response: Any, payload: dict[str, Any]) -> Any:
        """Valida, tenta reparar e degrada para fallback determinístico se necessário."""
        validation = validar_parecer(response.content, payload)
        if validation.ok:
            return response

        log.warning(
            "llm.guardrail.parecer_invalid",
            stage="primary",
            errors=validation.errors,
            model=response.model,
        )
        repaired = self._repair(response.content, payload, validation.errors)
        repaired_validation = validar_parecer(repaired.content, payload)
        if repaired_validation.ok:
            return repaired

        fallback_model = self.client.settings.llm_fallback_model
        if fallback_model:
            log.warning(
                "llm.guardrail.parecer_invalid",
                stage="repair",
                errors=repaired_validation.errors,
                model=repaired.model,
            )
            fallback = self.client.chat(
                messages=[
                    ChatMessage(role="system", content=prompts.SYSTEM_PROMPT),
                    ChatMessage(role="user", content=prompts.montar_user_message(payload)),
                ],
                temperature=0.2,
                max_tokens=1500,
                model_override=fallback_model,
            )
            fallback_validation = validar_parecer(fallback.content, payload)
            if fallback_validation.ok:
                return fallback
            log.warning(
                "llm.guardrail.parecer_invalid",
                stage="fallback",
                errors=fallback_validation.errors,
                model=fallback.model,
            )

        log.error("llm.guardrail.parecer_degraded")
        return _deterministic_response(response, payload)

    def _repair(self, markdown: str, payload: dict[str, Any], errors: list[str]) -> Any:
        return self.client.chat(
            messages=[
                ChatMessage(role="system", content=prompts.REPAIR_SYSTEM_PROMPT),
                ChatMessage(
                    role="user",
                    content=prompts.montar_repair_user_message(
                        auditoria_payload=payload,
                        parecer_invalido=markdown,
                        erros=errors,
                    ),
                ),
            ],
            temperature=0.1,
            max_tokens=1500,
            model_override=self.client.settings.llm_model,
        )


def _deterministic_response(response: Any, payload: dict[str, Any]) -> Any:
    response.content = gerar_parecer_deterministico(payload)
    response.tool_calls = []
    response.model = "deterministic-parecer-fallback"
    response.provider = ProviderInfo(
        name="deterministic_fallback",
        base_url="local://deterministic",
        model="deterministic-parecer-fallback",
        offline=True,
    )
    return response
