"""GeradorParecer: produz markdown estruturado a partir de uma auditoria."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from . import cache
from .client import ChatClient, ChatMessage
from .prompts import parecer as prompts

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
            max_tokens=900,
        )
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
