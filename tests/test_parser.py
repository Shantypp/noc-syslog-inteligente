"""Pruebas del parser Syslog (RF-03)."""

import pytest

from app.collector.parser import MensajeInvalido, parse_syslog


def test_pri_se_descompone_en_facility_y_severidad():
    r = parse_syslog("<187>Oct  3 10:15:02 R1-NOC %LINK-3-UPDOWN: Interface Gi0/1 down")
    assert r["facility"] == 23   # 187 // 8 -> local7
    assert r["severidad"] == 3   # 187 %  8 -> error


def test_formato_rfc3164():
    r = parse_syslog("<189>Oct  3 10:16:10 R1-NOC %SYS-5-CONFIG_I: Configured from console")
    assert r["formato"] == "RFC3164"
    assert r["hostname"] == "R1-NOC"
    assert r["timestamp_equipo"] == "Oct  3 10:16:10"
    assert r["mensaje"] == "%SYS-5-CONFIG_I: Configured from console"


def test_formato_rfc5424():
    r = parse_syslog('<165>1 2026-10-03T10:17:00Z FW-EDGE fortigate - - - msg="VPN up"')
    assert r["formato"] == "RFC5424"
    assert r["hostname"] == "FW-EDGE"
    assert r["severidad"] == 5
    assert r["mensaje"] == 'msg="VPN up"'


def test_formato_huawei():
    r = parse_syslog("<184>Oct  3 10:24:00 SW-CORE %%01DEVM/1/hwPowerFail(t)[2]:Power supply 2 failed.")
    assert r["hostname"] == "SW-CORE"
    assert r["severidad"] == 0


@pytest.mark.parametrize("texto", ["sin pri", "<999>Oct  3 10:00:00 X msg", ""])
def test_mensajes_invalidos(texto):
    with pytest.raises(MensajeInvalido):
        parse_syslog(texto)


def test_formato_desconocido_conserva_el_texto():
    r = parse_syslog("<14>algo raro")
    assert r["formato"] == "desconocido"
    assert r["mensaje"] == "algo raro"
