"""Funcoes puras de normalizacao para os dados heterogeneos do cliente.

Os arquivos xlsx originais misturam tipos para o mesmo campo (ex: data como
string '21/03/2026' OU datetime; numero como '15.000,00' OU 15000). Este modulo
isola toda essa logica em funcoes determinismas e testaveis.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any

# Excel armazena datas como serial number a partir de 1899-12-30 (workaround do bug
# herdado do Lotus 1-2-3 que considera 1900 ano bissexto).
_EXCEL_EPOCH = datetime(1899, 12, 30)

_PLACA_LIMPEZA_RE = re.compile(r"[\s\.\-/]")


def normalizar_placa(valor: Any) -> str:
    """Normaliza placa/codigo de equipamento para uso como chave de busca.

    Remove espacos, pontos, hifens e barras; converte para uppercase. Mantem
    o valor original (apos strip) inalterado se for None/NaN.

    Examples
    --------
    >>> normalizar_placa("07.T586")
    '07T586'
    >>> normalizar_placa("07-T586")
    '07T586'
    >>> normalizar_placa(" nuy4231 ")
    'NUY4231'
    """
    if valor is None:
        return ""
    s = str(valor).strip()
    if not s or s.lower() == "nan":
        return ""
    return _PLACA_LIMPEZA_RE.sub("", s).upper()


def normalizar_numero_br(valor: Any) -> float:
    """Converte numero em formato brasileiro (15.000,00) ou puro (15000.0) para float.

    Aceita int, float, str. Strings podem usar '.' como separador de milhar e
    ',' como decimal ('15.000,00') ou apenas decimal ('15000,5'), ou ainda no
    padrao ingles ('15000.00'). Retorna 0.0 para None/NaN/vazio.

    Examples
    --------
    >>> normalizar_numero_br("15.000,00")
    15000.0
    >>> normalizar_numero_br(15000)
    15000.0
    >>> normalizar_numero_br("1.092,00")
    1092.0
    """
    if valor is None:
        return 0.0
    if isinstance(valor, bool):
        return float(valor)
    if isinstance(valor, int | float):
        try:
            f = float(valor)
        except (TypeError, ValueError):
            return 0.0
        if f != f:  # NaN
            return 0.0
        return f
    s = str(valor).strip()
    if not s or s.lower() in {"nan", "-", "--", "none"}:
        return 0.0
    s = s.replace("R$", "").replace(" ", "")
    # Heurística BR: vírgula = decimal; ponto = separador de milhar quando
    # todos os grupos são de 3 dígitos (ex: "15.000", "1.092.345"); caso
    # contrário, ponto é decimal padrão inglês ("15.5", "6.59").
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") >= 1:
        partes = s.split(".")
        # Todas as partes após a primeira têm exatamente 3 dígitos -> milhar BR.
        if all(len(p) == 3 and p.isdigit() for p in partes[1:]) and partes[0].lstrip("-").isdigit():
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def normalizar_data(valor: Any) -> datetime | None:
    """Aceita datetime, date, string dd/mm/aaaa, dd/mm/aa ou serial Excel (float/int).

    Retorna None para '-', '', None e demais valores invalidos.

    Examples
    --------
    >>> normalizar_data("21/03/2026").date().isoformat()
    '2026-03-21'
    >>> normalizar_data(46125).date().isoformat()
    '2026-04-13'
    >>> normalizar_data("-") is None
    True
    """
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day)
    if isinstance(valor, int | float):
        v = float(valor)
        if v != v:  # NaN
            return None
        if v <= 0:
            return None
        return _EXCEL_EPOCH + timedelta(days=v)
    s = str(valor).strip()
    if not s or s in {"-", "--", "nan", "NaT", "None"}:
        return None
    # Tenta varios formatos.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y", "%d/%m/%y %H:%M", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def normalizar_hora(valor: Any) -> time | None:
    """Aceita time, datetime, string HH:MM ou HH:MM:SS.

    Examples
    --------
    >>> normalizar_hora("08:50:00")
    datetime.time(8, 50)
    >>> normalizar_hora("15:34")
    datetime.time(15, 34)
    """
    if valor is None:
        return None
    if isinstance(valor, time):
        return valor
    if isinstance(valor, datetime):
        return valor.time()
    s = str(valor).strip()
    if not s or s.lower() in {"nan", "-", "none"}:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def combinar_data_hora(data: datetime | None, hora: time | None) -> datetime | None:
    """Combina data + hora em datetime unico. Se hora for None, mantem 00:00."""
    if data is None:
        return None
    if hora is None:
        return data
    return datetime.combine(data.date(), hora)


_CAPACIDADE_RE = re.compile(r"(\d+)")


def normalizar_capacidade(valor: Any) -> int | None:
    """Extrai inteiro de litros de strings tipo '630LTS', '280LTS', '219lts'.

    Retorna None se nao conseguir parsear.

    Examples
    --------
    >>> normalizar_capacidade("630LTS")
    630
    >>> normalizar_capacidade("219lts")
    219
    >>> normalizar_capacidade("-") is None
    True
    """
    if valor is None:
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        if valor != valor:
            return None
        return int(valor)
    s = str(valor).strip()
    if not s or s in {"-", "nan", "None"}:
        return None
    m = _CAPACIDADE_RE.search(s)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def normalizar_texto(valor: Any) -> str | None:
    """Strip e converte '-', 'nan', '' em None."""
    if valor is None:
        return None
    if isinstance(valor, float) and valor != valor:
        return None
    s = str(valor).strip()
    if not s or s in {"-", "--", "nan", "None", "NaT"}:
        return None
    return s
