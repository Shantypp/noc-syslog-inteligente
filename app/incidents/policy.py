"""
incidents/policy.py — Paso 3 del flujo: POLÍTICA (severidad + regla).

La política NO crea incidentes sola. Detecta eventos que lo ameritan y los
PROPONE; un humano revisa y decide (flujo seguro obligatorio del curso:
evento -> validación -> PROPUESTA -> REVISIÓN HUMANA -> aprobación ...).

Una propuesta deja de aparecer cuando:
  - ya tiene incidente, o
  - una persona la descartó (falso positivo, mantenimiento programado...), o
  - ya hay un incidente abierto por esa MISMA parte del equipo (es el mismo problema:
    el evento queda en el historial de ese incidente).
"""

import sqlite3

from app import config

# Tiempo máximo de atención por severidad, en minutos (SLA)
SLA_MINUTOS = {0: 15, 1: 15, 2: 30, 3: 240, 4: 480, 5: 1440, 6: 1440, 7: 1440}


def umbral_incidente(conn: sqlite3.Connection) -> int:
    """Eventos con severidad <= este valor generan propuesta (0-2 = emergency/alert/critical)."""
    return config.obtener(conn, "umbral_incidente")


def minutos_sin_comunicacion(conn: sqlite3.Connection) -> int:
    """Equipo sin eventos durante este tiempo -> 'sin comunicación' (HU-01)."""
    return config.obtener(conn, "minutos_sin_comunicacion")


_FILTRO_PROPUESTAS = (
    "e.severidad <= ? AND e.revisado_en IS NULL "
    "AND NOT EXISTS (SELECT 1 FROM incidents i WHERE i.event_id = e.id) "
    "AND NOT (e.componente IS NOT NULL AND EXISTS ("
    "    SELECT 1 FROM incidents i JOIN events ie ON ie.id = i.event_id "
    "    WHERE i.estado != 'cerrado' AND i.device_id = e.device_id AND ie.componente = e.componente))"
)


def propuestas(conn: sqlite3.Connection, limite: int = 50) -> list[dict]:
    """Eventos graves que todavía no tienen incidente: esperan revisión humana."""
    rows = conn.execute(
        "SELECT e.id, e.recibido_en, e.severidad, e.mensaje, e.sospechoso, e.repeticiones, e.componente, "
        "e.estado_componente, e.device_id, d.nombre AS equipo, d.marca, "
        # ¿Esa parte del equipo ya volvió a funcionar después del evento? -> probablemente se puede descartar
        "EXISTS (SELECT 1 FROM events r WHERE e.componente IS NOT NULL AND r.device_id = e.device_id "
        "        AND r.componente = e.componente AND r.id > e.id AND r.estado_componente = 'Arriba') AS ya_recuperado "
        "FROM events e LEFT JOIN devices d ON d.id = e.device_id "
        f"WHERE {_FILTRO_PROPUESTAS} ORDER BY e.severidad, e.id DESC LIMIT ?",
        (umbral_incidente(conn), limite),
    ).fetchall()
    return [dict(r) for r in rows]


def contar_propuestas(conn: sqlite3.Connection) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM events e WHERE {_FILTRO_PROPUESTAS}",
                        (umbral_incidente(conn),)).fetchone()[0]
