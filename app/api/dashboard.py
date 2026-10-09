"""
api/dashboard.py — Datos del tablero principal (RF-04, HU-01).

    GET /api/dashboard   tarjetas de resumen, estado de equipos, eventos recientes,
                         distribución por severidad, propuestas e incidentes activos
"""

import sqlite3

from fastapi import APIRouter, Depends

from app.api.events import enriquecer
from app.collector import ingest
from app.database import get_db
from app.incidents.policy import UMBRAL_INCIDENTE, UMBRAL_SIN_COMUNICACION_MIN, propuestas
from app.utils import hace

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def estado_equipos(conn: sqlite3.Connection) -> list[dict]:
    """
    Estado operativo de cada equipo (HU-01):
      - 'inactivo' si el administrador lo marcó así (mantenimiento, apagado...)
      - 'sin_comunicacion' si no envía eventos hace más de UMBRAL_SIN_COMUNICACION_MIN
      - 'activo' en otro caso
    """
    limite = hace(minutos=UMBRAL_SIN_COMUNICACION_MIN)
    rows = conn.execute(
        "SELECT d.*, MAX(e.recibido_en) AS ultimo_evento, COUNT(e.id) AS total_eventos "
        "FROM devices d LEFT JOIN events e ON e.device_id = d.id "
        "GROUP BY d.id ORDER BY d.nombre").fetchall()
    equipos = []
    for r in rows:
        eq = dict(r)
        if eq["estado"] != "activo":
            eq["estado_operativo"] = eq["estado"]
        elif not eq["ultimo_evento"] or eq["ultimo_evento"] < limite:
            eq["estado_operativo"] = "sin_comunicacion"
        else:
            eq["estado_operativo"] = "activo"
        equipos.append(eq)
    return equipos


@router.get("")
def resumen(conn: sqlite3.Connection = Depends(get_db)):
    desde_24h = hace(horas=24)
    uno = lambda sql, *p: conn.execute(sql, p).fetchone()[0]  # noqa: E731 (consulta de un solo valor)

    equipos = estado_equipos(conn)
    por_severidad = {r[0]: r[1] for r in conn.execute(
        "SELECT severidad, COUNT(*) FROM events WHERE recibido_en >= ? GROUP BY severidad", (desde_24h,))}
    recientes = conn.execute(
        "SELECT e.*, d.nombre AS equipo, d.marca FROM events e "
        "LEFT JOIN devices d ON d.id = e.device_id ORDER BY e.id DESC LIMIT 10").fetchall()
    criticos = conn.execute(
        "SELECT e.*, d.nombre AS equipo, d.marca FROM events e "
        "LEFT JOIN devices d ON d.id = e.device_id WHERE e.severidad <= ? "
        "ORDER BY e.id DESC LIMIT 10", (UMBRAL_INCIDENTE,)).fetchall()
    incidentes_activos = conn.execute(
        "SELECT i.id, i.titulo, i.severidad, i.estado, i.responsable, i.abierto_en, d.nombre AS equipo "
        "FROM incidents i LEFT JOIN devices d ON d.id = i.device_id "
        "WHERE i.estado != 'cerrado' ORDER BY i.severidad, i.id DESC LIMIT 10").fetchall()

    return {
        "tarjetas": {
            "equipos_total": len(equipos),
            "equipos_activos": sum(e["estado_operativo"] == "activo" for e in equipos),
            "equipos_sin_comunicacion": sum(e["estado_operativo"] == "sin_comunicacion" for e in equipos),
            "eventos_24h": uno("SELECT COUNT(*) FROM events WHERE recibido_en >= ?", desde_24h),
            "criticos_24h": uno("SELECT COUNT(*) FROM events WHERE recibido_en >= ? AND severidad <= ?",
                                desde_24h, UMBRAL_INCIDENTE),
            "sospechosos_24h": uno("SELECT COUNT(*) FROM events WHERE recibido_en >= ? AND sospechoso = 1",
                                   desde_24h),
            "incidentes_abiertos": uno("SELECT COUNT(*) FROM incidents WHERE estado != 'cerrado'"),
            "propuestas_pendientes": len(propuestas(conn, limite=500)),
        },
        "umbral_sin_comunicacion_min": UMBRAL_SIN_COMUNICACION_MIN,
        "equipos": equipos,
        "por_severidad": [por_severidad.get(s, 0) for s in range(8)],
        "eventos_recientes": [enriquecer(r) for r in recientes],
        "eventos_criticos": [enriquecer(r) for r in criticos],
        "incidentes_activos": [dict(r) for r in incidentes_activos],
        "ingreso": dict(ingest.estadisticas),
    }
