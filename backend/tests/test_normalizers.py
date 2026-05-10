"""Testes das funcoes puras de normalizacao."""

from __future__ import annotations

from datetime import datetime, time

import pytest

from audit_diesel.ingestion.normalizers import (
    combinar_data_hora,
    normalizar_capacidade,
    normalizar_data,
    normalizar_hora,
    normalizar_numero_br,
    normalizar_placa,
    normalizar_texto,
)


class TestNormalizarPlaca:
    def test_placa_com_ponto(self):
        assert normalizar_placa("07.T586") == "07T586"

    def test_placa_com_hifen(self):
        assert normalizar_placa("07-T586") == "07T586"

    def test_placa_sem_separador(self):
        assert normalizar_placa("07T586") == "07T586"

    def test_consistencia_entre_formatos(self):
        assert normalizar_placa("07.T586") == normalizar_placa("07-T586") == normalizar_placa("07T586")

    def test_placa_mercosul(self):
        assert normalizar_placa("nuy4231") == "NUY4231"

    def test_espacos_e_barras(self):
        assert normalizar_placa(" 09/002 ") == "09002"

    def test_none_e_vazio(self):
        assert normalizar_placa(None) == ""
        assert normalizar_placa("") == ""
        assert normalizar_placa("nan") == ""


class TestNormalizarNumeroBr:
    def test_string_br_com_milhar(self):
        assert normalizar_numero_br("15.000,00") == 15000.0

    def test_string_br_milhar_sem_decimal(self):
        # "15.000" no padrao BR = 15000 (ponto eh separador de milhar).
        assert normalizar_numero_br("15.000") == 15000.0

    def test_decimal_ingles_pequeno(self):
        # "6.59" e "15.5" sao decimais (ponto), nao milhar.
        assert normalizar_numero_br("6.59") == 6.59
        assert normalizar_numero_br("15.5") == 15.5

    def test_inteiro_puro(self):
        assert normalizar_numero_br(15000) == 15000.0

    def test_string_e_inteiro_iguais(self):
        assert normalizar_numero_br("15.000,00") == normalizar_numero_br(15000)

    def test_decimal_simples(self):
        assert normalizar_numero_br("1.092,00") == 1092.0

    def test_float(self):
        assert normalizar_numero_br(6.59) == 6.59

    def test_string_com_rs(self):
        assert normalizar_numero_br("R$ 102.000,00") == 102000.0

    def test_vazio_e_traco(self):
        assert normalizar_numero_br("-") == 0.0
        assert normalizar_numero_br("") == 0.0
        assert normalizar_numero_br(None) == 0.0


class TestNormalizarData:
    def test_string_dd_mm_aaaa(self):
        d = normalizar_data("21/03/2026")
        assert d is not None and d.date().isoformat() == "2026-03-21"

    def test_serial_excel(self):
        # 46125 corresponde a 13/04/2026 com epoch 1899-12-30.
        d = normalizar_data(46125)
        assert d is not None and d.date().isoformat() == "2026-04-13"

    def test_serial_excel_float(self):
        d = normalizar_data(46125.0)
        assert d is not None and d.date().isoformat() == "2026-04-13"

    def test_datetime_passthrough(self):
        dt = datetime(2026, 3, 13, 8, 50)
        assert normalizar_data(dt) == dt

    def test_traco_vira_none(self):
        assert normalizar_data("-") is None

    def test_string_dd_mm_aa(self):
        d = normalizar_data("14/04/26")
        assert d is not None and d.date().isoformat() == "2026-04-14"


class TestNormalizarHora:
    def test_hh_mm_ss(self):
        assert normalizar_hora("08:50:00") == time(8, 50)

    def test_hh_mm(self):
        assert normalizar_hora("15:34") == time(15, 34)

    def test_time_passthrough(self):
        assert normalizar_hora(time(9, 25)) == time(9, 25)

    def test_invalido(self):
        assert normalizar_hora("xx") is None
        assert normalizar_hora(None) is None


class TestCombinarDataHora:
    def test_combina_correto(self):
        d = datetime(2026, 3, 13)
        h = time(8, 50)
        assert combinar_data_hora(d, h) == datetime(2026, 3, 13, 8, 50)

    def test_sem_hora_mantem_data(self):
        d = datetime(2026, 3, 13)
        assert combinar_data_hora(d, None) == d

    def test_sem_data(self):
        assert combinar_data_hora(None, time(8, 50)) is None


class TestNormalizarCapacidade:
    def test_lts_uppercase(self):
        assert normalizar_capacidade("630LTS") == 630

    def test_lts_lowercase(self):
        assert normalizar_capacidade("219lts") == 219

    def test_traco_vira_none(self):
        assert normalizar_capacidade("-") is None

    def test_so_numero(self):
        assert normalizar_capacidade(280) == 280

    def test_invalido_vira_none(self):
        assert normalizar_capacidade("ABC") is None


class TestNormalizarTexto:
    def test_strip(self):
        assert normalizar_texto("  abc  ") == "abc"

    def test_traco_vira_none(self):
        assert normalizar_texto("-") is None

    def test_nan_vira_none(self):
        assert normalizar_texto("nan") is None
        assert normalizar_texto(float("nan")) is None


@pytest.mark.parametrize(
    "v1,v2",
    [
        ("07.T586", "07T586"),
        ("07-T586", "07T586"),
        (" 07T586 ", "07T586"),
    ],
)
def test_placa_equivalencia(v1, v2):
    assert normalizar_placa(v1) == normalizar_placa(v2)
