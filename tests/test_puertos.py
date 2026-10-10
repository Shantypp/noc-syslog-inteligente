"""Pruebas de identificación del componente afectado (puertos, fuentes, sensores...)."""

from pathlib import Path

import pytest

from app.collector.componentes import identificar

MUESTRAS = Path(__file__).resolve().parent.parent / "data" / "muestras_simuladas.log"


@pytest.mark.parametrize("mensaje,esperado", [
    ("%LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to down", ("GigabitEthernet0/1", "Caído")),
    ("%LINK-3-UPDOWN: Interface Gi0/2, changed state to down", ("GigabitEthernet0/2", "Caído")),   # se unifica
    ("%LINK-5-CHANGED: Interface Gi0/2, changed state to administratively down", ("GigabitEthernet0/2", "Caído")),
    ("%LINK-5-CHANGED: Interface GigabitEthernet0/1, changed state to up", ("GigabitEthernet0/1", "Arriba")),
    ("The line protocol on interface GE0/0/1 has entered the DOWN state.", ("GE0/0/1", "Caído")),
    ('type=event subtype=system msg="Interface status changed" interface="wan2" status="down"', ("wan2", "Caído")),
    ("%%01DEVM/1/hwPowerFail(t)[2]:Power supply 2 failed.", ("Fuente de poder 2", "Falla")),
    ("%PLATFORM-2-TEMP_CRITICAL: Temperature sensor 1 reached critical threshold", ("Sensor de temperatura 1", "Crítico")),
    ('msg="HA failover: primary unit down"', ("Clúster HA", "Conmutación")),
    ('msg="IPsec tunnel SEDE-NORTE up"', ("Túnel VPN SEDE-NORTE", "Arriba")),
    ("%SEC_LOGIN-4-LOGIN_FAILED: Login failed [user: admin]", (None, None)),   # no es una parte del equipo
])
def test_identifica_el_componente(mensaje, esperado):
    assert identificar(mensaje) == esperado


@pytest.fixture
def con_datos(client):
    for e in [{"nombre": "R1-NOC", "ip": "192.0.2.1", "marca": "Cisco"},
              {"nombre": "FW-EDGE", "ip": "192.0.2.2", "marca": "Fortinet"},
              {"nombre": "SW-CORE", "ip": "192.0.2.3", "marca": "Huawei"}]:
        client.post("/api/devices", json=e)
    with open(MUESTRAS, "rb") as f:
        client.post("/api/events/importar", files={"archivo": ("m.log", f, "text/plain")})
    return client


def test_estado_actual_de_puertos_y_componentes(con_datos):
    d = con_datos.get("/api/puertos").json()
    estado = {(c["equipo"], c["componente"]): c["estado"] for c in d["componentes"]}
    assert estado[("R1-NOC", "GigabitEthernet0/1")] == "Arriba"   # cayó y luego se recuperó
    assert estado[("SW-CORE", "GE0/0/1")] == "Caído"
    assert estado[("SW-CORE", "Fuente de poder 2")] == "Falla"
    assert d["total"] == 6 and d["con_problema"] == 4


def test_el_panel_dice_que_parte_del_equipo_falla(con_datos):
    sw = next(e for e in con_datos.get("/api/dashboard").json()["equipos"] if e["nombre"] == "SW-CORE")
    assert sorted(sw["componentes_con_problema"]) == ["Fuente de poder 2 (Falla)", "GE0/0/1 (Caído)"]


def test_el_incidente_muestra_el_componente_afectado(con_datos):
    evento = next(e for e in con_datos.get("/api/events").json()["eventos"] if e["componente"] == "Fuente de poder 2")
    inc = con_datos.post("/api/incidents", json={"event_id": evento["id"]}).json()
    assert inc["componente"] == "Fuente de poder 2" and inc["estado_componente"] == "Falla"
