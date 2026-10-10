"""
api/puertos.py — Puertos y componentes de cada equipo.

    GET /api/puertos   estado actual de cada puerto/componente que ha reportado eventos

El estado actual de un componente es el de su ÚLTIMO evento. Así, si
GigabitEthernet0/1 cae y luego vuelve, aparece "Arriba" (recuperado), y su
historial conserva la caída.
"""

import sqlite3

from fastapi import APIRouter, Depends

from app.collector.componentes import es_problema
from app.collector.parser import SEVERIDADES
from app.database import get_db
from app.security.auth import requiere

router = APIRouter(prefix="/api/puertos", tags=["puertos y componentes"], dependencies=[Depends(requiere("lector"))])


def estado_componentes(conn: sqlite3.Connection) -> list[dict]:
    """Un registro por (equipo, componente) con su último estado, contadores e incidente abierto."""
    filas = conn.execute(
        "SELECT e.id, e.device_id, d.nombre AS equipo, d.marca, e.componente, e.estado_componente, "
        "e.severidad, e.recibido_en, e.mensaje, i.id AS incident_id, i.estado AS incident_estado "
        "FROM events e JOIN devices d ON d.id = e.device_id "
        "LEFT JOIN incidents i ON i.event_id = e.id "
        "WHERE e.componente IS NOT NULL ORDER BY e.id").fetchall()
    componentes: dict[tuple, dict] = {}
    for f in filas:
        clave = (f["device_id"], f["componente"])
        c = componentes.setdefault(clave, {
            "device_id": f["device_id"], "equipo": f["equipo"], "marca": f["marca"],
            "componente": f["componente"], "eventos": 0, "problemas": 0, "incidente_abierto": None})
        c["eventos"] += 1
        c["problemas"] += int(es_problema(f["estado_componente"]))
        if f["incident_id"] and f["incident_estado"] != "cerrado":
            c["incidente_abierto"] = f["incident_id"]
        # El último evento define el estado actual
        c.update(estado=f["estado_componente"], con_problema=es_problema(f["estado_componente"]),
                 severidad=f["severidad"], severidad_nombre=SEVERIDADES[f["severidad"]],
                 ultimo_evento=f["recibido_en"], ultimo_mensaje=f["mensaje"], event_id=f["id"])
    return sorted(componentes.values(), key=lambda c: (c["equipo"], not c["con_problema"], c["componente"]))


@router.get("")
def listar(conn: sqlite3.Connection = Depends(get_db)):
    componentes = estado_componentes(conn)
    return {
        "total": len(componentes),
        "con_problema": sum(c["con_problema"] for c in componentes),
        "componentes": componentes,
    }
