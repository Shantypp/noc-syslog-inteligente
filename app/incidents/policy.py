"""
incidents/policy.py — Paso 3 del flujo: POLÍTICA (severidad + regla).

La política NO crea incidentes sola. Detecta eventos que lo ameritan y los
PROPONE; un humano revisa y decide (flujo seguro obligatorio del curso:
evento -> validación -> PROPUESTA -> REVISIÓN HUMANA -> aprobación ...).
"""

import os
import sqlite3

# Eventos con severidad <= este valor generan propuesta de incidente (0-2 = emergency/alert/critical)
UMBRAL_INCIDENTE = int(os.getenv("INCIDENT_MAX_SEVERITY", "2"))

# Tiempo máximo de atención por severidad, en minutos (SLA)
SLA_MINUTOS = {0: 15, 1: 15, 2: 30, 3: 240, 4: 480, 5: 1440, 6: 1440, 7: 1440}

# Equipo sin eventos durante este tiempo -> "sin comunicación" (HU-01)
UMBRAL_SIN_COMUNICACION_MIN = int(os.getenv("NO_COMM_MINUTES", "10"))


def propuestas(conn: sqlite3.Connection, limite: int = 50) -> list[dict]:
    """Eventos graves que todavía no tienen incidente: esperan revisión humana."""
    rows = conn.execute(
        "SELECT e.id, e.recibido_en, e.severidad, e.mensaje, e.sospechoso, e.repeticiones, e.componente, e.estado_componente, "
        "d.nombre AS equipo, d.marca FROM events e "
        "LEFT JOIN devices d ON d.id = e.device_id "
        "WHERE e.severidad <= ? AND NOT EXISTS (SELECT 1 FROM incidents i WHERE i.event_id = e.id) "
        "ORDER BY e.severidad, e.id DESC LIMIT ?",
        (UMBRAL_INCIDENTE, limite),
    ).fetchall()
    return [dict(r) for r in rows]
