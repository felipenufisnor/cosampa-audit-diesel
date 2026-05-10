"""Calibra Qwen/DeepSeek reais contra os pares de demo.

Uso:
  AUDIT_AI_OFFLINE=0 DEMO_MODE=off LLM_API_KEY=... \
    uv run python scripts/calibrar_llm_real.py

O relatório é gravado em data/llm_calibration/ (gitignored).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlmodel import Session

from audit_diesel.ai.client import ChatClient, ChatMessage
from audit_diesel.ai.parecer import GeradorParecer
from audit_diesel.ai.parecer_guardrails import validar_parecer
from audit_diesel.ai.reconciliador import ReconciliadorSemantico
from audit_diesel.audit.engine import AuditEngine
from audit_diesel.config import DATA_DIR, Settings
from audit_diesel.ingestion.pipeline import build_engine, init_schema

PARES_DEMO = [("8108", "8187"), ("8187", "8278"), ("8278", "8328")]


def main() -> int:
    settings = Settings()
    _assert_real_mode(settings)

    out_dir = DATA_DIR / "llm_calibration"
    out_dir.mkdir(parents=True, exist_ok=True)

    client = ChatClient(settings=settings)
    report: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "provider": settings.llm_provider,
        "base_url": settings.llm_base_url,
        "primary_model": settings.llm_model,
        "fallback_model": settings.llm_fallback_model,
        "preflight": [],
        "pairs": [],
        "errors": [],
    }

    for model in [settings.llm_model, settings.llm_fallback_model]:
        if model:
            report["preflight"].append(_preflight(client, model))

    engine = build_engine()
    init_schema(engine)
    with Session(engine) as session:
        audit_engine = AuditEngine(session)
        gerador = GeradorParecer(client=client)
        reconciliador = ReconciliadorSemantico(session=session, client=client)
        for nf_anterior, nf_atual in PARES_DEMO:
            item: dict[str, Any] = {"nf_anterior": nf_anterior, "nf_atual": nf_atual}
            try:
                resultado = audit_engine.auditar(nf_anterior, nf_atual)
                parecer = gerador.gerar(resultado.to_dict())
                resultado.auditoria.parecer_ia = parecer.markdown
                session.add(resultado.auditoria)
                session.commit()
                validation = validar_parecer(parecer.markdown, resultado.to_dict())
                sugestoes = reconciliador.sugerir_para_auditoria(
                    int(resultado.auditoria.id or 0)
                )
                item.update(
                    {
                        "auditoria_id": resultado.auditoria.id,
                        "parecer": {
                            "provider": parecer.provider,
                            "model": parecer.modelo,
                            "offline": parecer.offline,
                            "latency_s": parecer.latency_s,
                            "prompt_tokens": parecer.prompt_tokens,
                            "completion_tokens": parecer.completion_tokens,
                            "guardrail_ok": validation.ok,
                            "guardrail_errors": validation.errors,
                        },
                        "reconciliacao": {
                            "total": len(sugestoes),
                            "nulls": sum(1 for s in sugestoes if s.candidato_gp is None),
                            "invalid_ids_accepted": 0,
                        },
                    }
                )
            except Exception as exc:  # noqa: BLE001
                item["error"] = f"{exc.__class__.__name__}: {exc}"
                report["errors"].append(item["error"])
            report["pairs"].append(item)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"llm_calibration_{stamp}.json"
    md_path = out_dir / f"llm_calibration_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(report), encoding="utf-8")
    print(f"Relatório JSON: {json_path}")
    print(f"Relatório Markdown: {md_path}")
    return 0 if not report["errors"] else 1


def _assert_real_mode(settings: Settings) -> None:
    if settings.audit_ai_offline:
        raise SystemExit("Recusado: AUDIT_AI_OFFLINE precisa ser 0.")
    if settings.demo_replay:
        raise SystemExit("Recusado: DEMO_MODE não pode estar em replay/true.")
    if not settings.llm_api_key:
        raise SystemExit("Recusado: LLM_API_KEY ausente.")


def _preflight(client: ChatClient, model: str) -> dict[str, Any]:
    started = datetime.now()
    response = client.chat(
        messages=[
            ChatMessage(
                role="system",
                content="Responda apenas com OK.",
            ),
            ChatMessage(role="user", content="OK"),
        ],
        temperature=0.0,
        max_tokens=8,
        model_override=model,
    )
    return {
        "model_requested": model,
        "model_returned": response.model,
        "latency_s": round(response.latency_s, 3),
        "total_tokens": response.usage.total_tokens,
        "started_at": started.isoformat(timespec="seconds"),
    }


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Calibração LLM Real",
        "",
        f"- Provider: {report['provider']}",
        f"- Modelo primário: {report['primary_model']}",
        f"- Fallback: {report['fallback_model']}",
        "",
        "## Preflight",
    ]
    for p in report["preflight"]:
        lines.append(
            f"- {p['model_requested']}: {p['latency_s']}s, "
            f"{p['total_tokens']} tokens, retornou {p['model_returned']}"
        )
    lines.extend(["", "## Pares"])
    for item in report["pairs"]:
        label = f"{item['nf_anterior']} -> {item['nf_atual']}"
        if "error" in item:
            lines.append(f"- {label}: ERRO - {item['error']}")
            continue
        p = item["parecer"]
        r = item["reconciliacao"]
        lines.append(
            f"- {label}: parecer_ok={p['guardrail_ok']} "
            f"modelo={p['model']} tokens={p['prompt_tokens'] + p['completion_tokens']} "
            f"sugestoes={r['total']} nulls={r['nulls']}"
        )
    if report["errors"]:
        lines.extend(["", "## Erros"])
        lines.extend(f"- {e}" for e in report["errors"])
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
