"""Validação conservadora do parecer gerado por LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

BLOCKS = (
    "**Resultado**",
    "**Causa mais provável**",
    "**Recomendação ao auditor**",
    "**Risco financeiro associado**",
)


@dataclass
class ParecerValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)


def validar_parecer(markdown: str, payload: dict[str, Any]) -> ParecerValidation:
    """Valida o contrato mínimo do parecer antes de persistir/exibir."""
    errors: list[str] = []
    text = (markdown or "").strip()
    if not text:
        errors.append("parecer vazio")
        return ParecerValidation(False, errors)

    if "```" in text:
        errors.append("contém cerca de código")

    positions = [text.find(block) for block in BLOCKS]
    if any(p < 0 for p in positions):
        errors.append("blocos obrigatórios ausentes")
    elif positions != sorted(positions):
        errors.append("blocos fora de ordem")

    if len(re.findall(r"\S+", text)) > 220:
        errors.append("mais de 220 palavras")

    auditoria = payload.get("auditoria") or payload
    validacao = str(auditoria.get("validacao_final") or "").strip()
    resultado = _block_content(text, BLOCKS[0])
    if validacao and validacao not in resultado:
        errors.append("status incompatível com validacao_final")

    invalid_numbers = _invalid_numbers(text, payload)
    if invalid_numbers:
        errors.append(f"números não fornecidos: {', '.join(invalid_numbers[:5])}")

    return ParecerValidation(ok=not errors, errors=errors)


def _block_content(text: str, block: str) -> str:
    start = text.find(block)
    if start < 0:
        return ""
    start += len(block)
    next_positions = [text.find(b, start) for b in BLOCKS if text.find(b, start) >= 0]
    end = min(next_positions) if next_positions else len(text)
    return text[start:end]


def _invalid_numbers(text: str, payload: dict[str, Any]) -> list[str]:
    allowed = _allowed_numbers(payload)
    out: list[str] = []
    for raw in re.findall(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)*(?![A-Za-z])", text):
        normalized = _to_float(raw)
        if normalized is None:
            continue
        if _is_small_ordinal(normalized):
            continue
        if not any(abs(normalized - a) <= max(0.02, abs(a) * 0.0001) for a in allowed):
            out.append(raw)
    return out


def _allowed_numbers(payload: dict[str, Any]) -> set[float]:
    vals: set[float] = {0.0, 1.0, 2.0, 3.0}

    def walk(v: Any) -> None:
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, int | float):
            vals.add(float(v))
            return
        if isinstance(v, str):
            n = _to_float(v)
            if n is not None:
                vals.add(n)
            return
        if isinstance(v, dict):
            for item in v.values():
                walk(item)
            return
        if isinstance(v, list):
            for item in v:
                walk(item)

    walk(payload)
    auditoria = payload.get("auditoria") or payload
    if "diferenca_percentual" in auditoria:
        vals.add(float(auditoria.get("diferenca_percentual") or 0.0) * 100.0)
    impacto_alta = sum(
        float(a.get("impacto_financeiro") or 0.0)
        for a in payload.get("alertas", [])
        if isinstance(a, dict) and a.get("severidade") == "alta"
    )
    vals.add(impacto_alta)
    return vals


def _to_float(raw: str) -> float | None:
    s = raw.strip().replace("+", "")
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _is_small_ordinal(value: float) -> bool:
    return value in {1.0, 2.0, 3.0}
