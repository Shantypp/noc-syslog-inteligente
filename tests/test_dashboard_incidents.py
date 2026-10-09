"""Pruebas de la Fase 4: filtros (HU-02), dashboard (HU-01) e incidentes (HU-03)."""

from pathlib import Path

import pytest

MUESTRAS = Path(__file__).resolve().parent.parent / "data" / "muestras_simuladas.log"
EQUIPOS = [
    {"nombre": "R1-NOC", "ip": "192.0.2.1", "marca": "Cisco"},
    {"nombre": "FW-EDGE", "ip": "192.0.2.2", "marca": "Fortinet"},
    {"nombre": "SW-CORE", "ip": "192.0.2.3", "marca": "Huawei"},
]


@pytest.fixture
def con_datos(client):
    """Inventario + importación del archivo de muestras (dataset conocido)."""
    for e in EQUIPOS:
        client.post("/api/devices", json=e)
    with open(MUESTRAS, "rb") as f:
        r = client.post("/api/events/importar", files={"archivo": ("muestras.log", f, "text/plain")})
    assert r.status_code == 200
    return client


# ---------- Filtros (HU-02) ----------

def test_filtro_severidad_y_marca_devuelve_total_esperado(con_datos):
    # En el dataset, Cisco con severidad 0-3 son: LINK-3, PLATFORM-2 y SYS-3 (inyección) = 3
    r = con_datos.get("/api/events", params={"sev_max": 3, "marca": "Cisco"}).json()
    assert r["total"] == 3
    assert all(e["marca"] == "Cisco" and e["severidad"] <= 3 for e in r["eventos"])


def test_filtro_por_rango_de_fechas(con_datos):
    assert con_datos.get("/api/events", params={"desde": "2000-01-01"}).json()["total"] == 14
    assert con_datos.get("/api/events", params={"hasta": "2000-01-01"}).json()["total"] == 0


def test_fecha_invalida_es_rechazada(con_datos):
    assert con_datos.get("/api/events", params={"desde": "ayer"}).status_code == 422


def test_filtro_solo_sospechosos(con_datos):
    r = con_datos.get("/api/events", params={"solo_sospechosos": True}).json()
    assert r["total"] == 1
    assert "ignora las politicas" in r["eventos"][0]["mensaje"]


# ---------- Dashboard (HU-01) ----------

def test_dashboard_resume_el_estado(con_datos):
    d = con_datos.get("/api/dashboard").json()
    assert d["tarjetas"]["equipos_total"] == 3
    assert d["tarjetas"]["equipos_activos"] == 3          # los 3 enviaron eventos recién
    assert d["tarjetas"]["eventos_24h"] == 14
    assert d["tarjetas"]["sospechosos_24h"] == 1
    assert sum(d["por_severidad"]) == 14


def test_equipo_sin_eventos_aparece_sin_comunicacion(client):
    client.post("/api/devices", json=EQUIPOS[0])
    d = client.get("/api/dashboard").json()
    assert d["equipos"][0]["estado_operativo"] == "sin_comunicacion"


# ---------- Incidentes (HU-03) ----------

def _evento_critico(client) -> int:
    props = client.get("/api/incidents/propuestas").json()
    assert props, "la política debe proponer eventos de severidad 0-2"
    return props[0]["id"]


def test_ciclo_completo_de_incidente(con_datos):
    c = con_datos
    event_id = _evento_critico(c)

    # Crear desde el evento: recibe ID, estado, vínculo al evento y fechas
    inc = c.post("/api/incidents", json={"usuario": "ana", "event_id": event_id}).json()
    assert inc["id"] > 0 and inc["estado"] == "abierto" and inc["event_id"] == event_id
    assert inc["abierto_en"] and inc["sla_minutos"] > 0

    # Ya no aparece como propuesta
    assert event_id not in [p["id"] for p in c.get("/api/incidents/propuestas").json()]

    # Asignar -> pasa a "asignado"
    inc = c.patch(f"/api/incidents/{inc['id']}", json={"usuario": "ana", "responsable": "carlos"}).json()
    assert inc["estado"] == "asignado" and inc["responsable"] == "carlos"

    # Seguimiento
    inc = c.patch(f"/api/incidents/{inc['id']}", json={"usuario": "carlos", "estado": "en_progreso", "nota": "Revisando fuente"}).json()
    assert inc["estado"] == "en_progreso"

    # Cerrar sin causa -> error; con causa y solución -> cerrado
    assert c.post(f"/api/incidents/{inc['id']}/cerrar", json={"usuario": "carlos", "causa": "", "solucion": "x"}).status_code == 422
    inc = c.post(f"/api/incidents/{inc['id']}/cerrar",
                 json={"usuario": "carlos", "causa": "Falla de fuente", "solucion": "Se reemplazó la fuente"}).json()
    assert inc["estado"] == "cerrado" and inc["cerrado_en"]

    # Trazabilidad: cada paso quedó registrado con usuario
    acciones = [s["accion"] for s in inc["seguimiento"]]
    assert acciones == ["creado", "asignado", "estado", "estado", "nota", "cerrado"]

    # Un incidente cerrado no se modifica
    assert c.patch(f"/api/incidents/{inc['id']}", json={"usuario": "x", "nota": "y"}).status_code == 409


def test_no_se_duplican_incidentes_del_mismo_evento(con_datos):
    event_id = _evento_critico(con_datos)
    assert con_datos.post("/api/incidents", json={"usuario": "ana", "event_id": event_id}).status_code == 201
    assert con_datos.post("/api/incidents", json={"usuario": "ana", "event_id": event_id}).status_code == 409


def test_incidente_manual_requiere_titulo_y_severidad(client):
    assert client.post("/api/incidents", json={"usuario": "ana"}).status_code == 422
    r = client.post("/api/incidents", json={"usuario": "ana", "titulo": "Corte de fibra", "severidad": 1})
    assert r.status_code == 201


def test_la_interfaz_web_se_sirve(client):
    r = client.get("/")
    assert r.status_code == 200 and "NOC Syslog Inteligente" in r.text
