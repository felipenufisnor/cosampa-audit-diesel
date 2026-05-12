"""Detector de pareceres-template/placeholder.

Existem cenarios em que o `parecer_ia` persistido nao e' analise real:
- cache populado com frases-template ("Resultado calculado a partir...")
- vazamentos de nome de campo de banco ("impacto_total_alertas_brl")
- texto degenerado (vocabulario pobre / repeticao)

Este modulo concentra a heuristica em UM lugar para que a API
(`GET /auditorias/{id}`, consolidado, PDF) e o gerador (antes de persistir)
compartilhem o mesmo criterio de "isso e' parecer valido?".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

ParecerStatus = Literal["ok", "placeholder", "ausente"]


# Frases-template ja observadas em producao. Comparacao feita sobre versao
# normalizada (sem acento, lower). Mantenha as entradas tambem normalizadas.
_PLACEHOLDER_PHRASES: tuple[str, ...] = (
    "resultado calculado a partir dos indicadores",
    "avaliacao baseada nos alertas disparados pelo engine",
    "revise os alertas listados e proceda conforme procedimento",
    "valor consolidado conforme campo",
)

# Nomes de coluna/variavel vazando pro texto: padrao snake_case terminando em
# sufixos tecnicos. Suficiente para flagrar `impacto_total_alertas_brl`,
# `diferenca_litros`, etc.
_FIELD_LEAK_PATTERN = re.compile(
    r"\b[a-z][a-z0-9_]{2,}_(brl|pct|litros|alertas|json|id)\b"
)


@dataclass(frozen=True)
class ParecerQuality:
    status: ParecerStatus
    reasons: tuple[str, ...]

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"


def _normalizar(texto: str) -> str:
    """Lower + remove acentos para tornar a busca de frases robusta."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


def avaliar_parecer(parecer: str | None) -> ParecerQuality:
    """Classifica um parecer como `ok`, `placeholder` ou `ausente`.

    - `ausente`: None, vazio ou so whitespace.
    - `placeholder`: contem frase-template OU nome de campo vazado OU e'
      curto demais para conter analise real.
    - `ok`: passou em todos os filtros.
    """
    if parecer is None or not parecer.strip():
        return ParecerQuality(status="ausente", reasons=("vazio",))

    texto = parecer.strip()
    normalizado = _normalizar(texto)
    reasons: list[str] = []

    for phrase in _PLACEHOLDER_PHRASES:
        if phrase in normalizado:
            reasons.append(f"frase_template:{phrase[:32]}")

    leak = _FIELD_LEAK_PATTERN.search(normalizado)
    if leak:
        reasons.append(f"nome_campo_vazado:{leak.group(0)}")

    # Texto curto demais (< 25 palavras) raramente e' analise real.
    palavras = [p for p in re.split(r"\s+", texto) if p]
    if len(palavras) < 25:
        reasons.append(f"curto_demais:{len(palavras)}_palavras")

    if reasons:
        return ParecerQuality(status="placeholder", reasons=tuple(reasons))
    return ParecerQuality(status="ok", reasons=())


def is_parecer_placeholder(parecer: str | None) -> bool:
    """Conveniencia: True quando o parecer existe mas e' template/lixo."""
    return avaliar_parecer(parecer).status == "placeholder"
