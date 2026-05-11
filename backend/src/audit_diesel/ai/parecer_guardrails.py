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


_NUMBER_TOKEN_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)*(?![A-Za-z])")
_EMBEDDED_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
# Datas (ISO ou BR) e horas: fragmentos de "2026-03-23T08:09:00" não devem
# disparar o guardrail quando o LLM cita a data no parecer.
_DATE_TIME_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)?"
    r"|\d{2}/\d{2}/\d{4}"
    r"|\d{2}:\d{2}(?::\d{2})?"
)
# Tokens "código" (mistura letras e dígitos): placas como "KZV5173",
# "13.T881", "GE-04" etc. Mascaramos o token inteiro para não validar
# os dígitos isoladamente — eles vêm do payload via strings.
_TOKEN_RE = re.compile(r"[\w\.\-]+")


def _invalid_numbers(text: str, payload: dict[str, Any]) -> list[str]:
    allowed = _allowed_numbers(payload)
    masked_spans = [m.span() for m in _DATE_TIME_RE.finditer(text)]
    masked_spans.extend(_code_spans(text))
    out: list[str] = []
    for m in _NUMBER_TOKEN_RE.finditer(text):
        if _inside_any(m.start(), masked_spans):
            continue
        raw = m.group(0)
        normalized = _to_float(raw)
        if normalized is None:
            continue
        if _is_small_ordinal(normalized):
            continue
        if not any(abs(normalized - a) <= max(0.02, abs(a) * 0.0001) for a in allowed):
            out.append(raw)
    return out


def _inside_any(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def _code_spans(text: str) -> list[tuple[int, int]]:
    """Identifica spans de tokens alfanuméricos (placas, IDs)."""
    out: list[tuple[int, int]] = []
    for m in _TOKEN_RE.finditer(text):
        tok = m.group(0)
        has_alpha = any(c.isalpha() for c in tok)
        has_digit = any(c.isdigit() for c in tok)
        if has_alpha and has_digit:
            out.append(m.span())
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
            # Strings frequentemente carregam placas e IDs ("13.T881",
            # "OCP0615", "GE-04 JP") que aparecem literalmente no parecer.
            # Extraímos cada subsequência numérica para evitar falso positivo
            # do guardrail sobre números que vieram do payload.
            for m in _EMBEDDED_NUMBER_RE.finditer(v):
                num = _to_float(m.group(0))
                if num is not None:
                    vals.add(num)
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

    # Somas de impacto agregadas por (tipo, severidade) e totais. O parecer
    # cita legitimamente subtotais como "R$ X em alertas NAO_CADASTRADO" ou
    # "R$ Y em alta severidade"; precisamos permitir todos os recortes
    # comumente usados na narrativa.
    alertas = [a for a in payload.get("alertas", []) if isinstance(a, dict)]
    by_tipo: dict[str, float] = {}
    by_sev: dict[str, float] = {}
    for a in alertas:
        imp = float(a.get("impacto_financeiro") or 0.0)
        by_tipo[str(a.get("tipo") or "")] = by_tipo.get(str(a.get("tipo") or ""), 0.0) + imp
        by_sev[str(a.get("severidade") or "")] = by_sev.get(str(a.get("severidade") or ""), 0.0) + imp
    for v in by_tipo.values():
        vals.add(v)
    for v in by_sev.values():
        vals.add(v)
    vals.add(sum(by_tipo.values()))  # total geral
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
