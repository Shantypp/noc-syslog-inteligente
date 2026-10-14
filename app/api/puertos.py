"""
api/puertos.py — Puertos y componentes de cada equipo.

    GET /api/puertos   estado actual de cada puerto/componente que ha reportado eventos

El estado actual de un componente es el de su ÚLTIMO evento. Así, si
GigabitEthernet0/1 cae y luego vuelve, aparece "Arriba" (recuperado), y su
historial conserva la caída.
"""

import sqlite3

from fastapi import APIRouter, Depends

from app.collector.componentes import ESTADOS_PROBLEMA, es_problema
from app.collector.parser import SEVERIDADES
from app.database import get_db
from app.security.auth import requiere

router = APIRouter(prefix="/api/puertos", tags=["puertos y componentes"], dependencies=[Depends(requiere("lector"))])


def estado_componentes(conn: sqlite3.Connection, device_id: int | None = None) -> list[dict]:
    """
    Un registro por (equipo, componente) con su último estado, contadores e incidente abierto.
    Se resuelve en UNA consulta agrupada (no recorre todos los eventos en Python).
    """
    marcas = ", ".join("?" * len(ESTADOS_PROBLEMA))
    filtro, params = "", list(ESTADOS_PROBLEMA)
    if device_id is not None:
        filtro = " AND device_id = ?"
        params.append(device_id)
    filas = conn.execute(
        "WITH ult AS (SELECT device_id, componente, MAX(id) AS id, COUNT(*) AS eventos, "
        f"  COALESCE(SUM(estado_componente IN ({marcas})), 0) AS problemas "
        f"  FROM events WHERE componente IS NOT NULL AND device_id IS NOT NULL{filtro} GROUP BY device_id, componente) "
        "SELECT ult.*, d.nombre AS equipo, d.marca, e.estado_componente, e.severidad, e.recibido_en, e.mensaje, "
        "  (SELECT i.id FROM incidents i JOIN events ie ON ie.id = i.event_id WHERE i.estado != 'cerrado' "
        "   AND ie.device_id = ult.device_id AND ie.componente = ult.componente ORDER BY i.id DESC LIMIT 1) AS incidente_abierto "
        "FROM ult JOIN events e ON e.id = ult.id JOIN devices d ON d.id = ult.device_id", params).fetchall()
    componentes = [{
        "device_id": f["device_id"], "equipo": f["equipo"], "marca": f["marca"], "componente": f["componente"],
        "eventos": f["eventos"], "problemas": f["problemas"], "incidente_abierto": f["incidente_abierto"],
        # El último evento define el estado actual
        "estado": f["estado_componente"], "con_problema": es_problema(f["estado_componente"]),
        "severidad": f["severidad"], "severidad_nombre": SEVERIDADES[f["severidad"]],
        "ultimo_evento": f["recibido_en"], "ultimo_mensaje": f["mensaje"], "event_id": f["id"],
    } for f in filas]
    return sorted(componentes, key=lambda c: (c["equipo"], not c["con_problema"], c["componente"]))


@router.get("")
def listar(conn: sqlite3.Connection = Depends(get_db)):
    componentes = estado_componentes(conn)
    return {
        "total": len(componentes),
        "con_problema": sum(c["con_problema"] for c in componentes),
        "componentes": componentes,
    }
