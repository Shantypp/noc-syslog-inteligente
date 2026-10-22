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


# --- Mensajes tal como los envían los equipos reales ---

def test_cisco_real_con_secuencia_y_hora_sin_sincronizar():
    r = parse_syslog("<187>63: *Oct 21 17:19:23.985 COT: %LINK-3-UPDOWN: Interface GigabitEthernet1/0/3, changed state to down")
    assert r["formato"] == "Cisco IOS"
    assert r["severidad"] == 3
    assert r["timestamp_equipo"] == "Oct 21 17:19:23.985 COT"
    assert r["mensaje"] == "%LINK-3-UPDOWN: Interface GigabitEthernet1/0/3, changed state to down"
    assert r["hostname"] is None  # sin "logging origin-id": el equipo se identifica por su IP


def test_cisco_real_con_nombre_del_equipo():
    r = parse_syslog("<189>121: R2-LAB: Oct 21 18:10:02.123 COT: %SYS-5-CONFIG_I: Configured from console by console")
    assert r["hostname"] == "R2-LAB"
    assert r["mensaje"].startswith("%SYS-5-CONFIG_I")


def test_cisco_con_hora_de_encendido():
    r = parse_syslog("<189>45: 00:12:34: %SYS-5-CONFIG_I: Configured from console by console")
    assert r["timestamp_equipo"] == "00:12:34"
    assert r["mensaje"].startswith("%SYS-5-CONFIG_I")


def test_dos_mensajes_cisco_iguales_quedan_iguales_sin_la_secuencia():
    a = parse_syslog("<187>62: *Oct 21 17:19:22.986 COT: %LINK-3-UPDOWN: Interface Gi1/0/3, changed state to down")
    b = parse_syslog("<187>70: *Oct 21 17:20:01.002 COT: %LINK-3-UPDOWN: Interface Gi1/0/3, changed state to down")
    assert a["mensaje"] == b["mensaje"]  # así la deduplicación los puede agrupar


def test_huawei_con_anio():
    r = parse_syslog("<188>Oct 16 2026 10:15:02 SW-CORE %%01IFNET/4/LINK_STATE(l)[0]:The line protocol on interface GE0/0/1 has entered the DOWN state.")
    assert r["hostname"] == "SW-CORE"
    assert r["timestamp_equipo"] == "Oct 16 2026 10:15:02"
    assert r["mensaje"].startswith("%%01IFNET")


def test_fortigate_formato_propio():
    r = parse_syslog('<189>date=2026-10-16 time=10:15:02 devname="FGT60F" devid="FGT60F0000" type="event" msg="Administrator admin logged in"')
    assert r["formato"] == "FortiGate"
    assert r["hostname"] == "FGT60F"
    assert r["timestamp_equipo"] == "2026-10-16 10:15:02"
    assert 'msg="Administrator admin logged in"' in r["mensaje"]


def test_rfc3164_con_nombre_corto_no_se_confunde_con_cisco():
    r = parse_syslog("<187>Oct  3 10:15:02 CORE %LINK-3-UPDOWN: Interface Gi0/1 down")
    assert r["formato"] == "RFC3164" and r["hostname"] == "CORE"
