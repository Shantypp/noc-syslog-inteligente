"""
incidents/correlacion.py — Relaciona los eventos nuevos con los incidentes abiertos.

Si ya hay un incidente abierto por "GigabitEthernet0/1 en R1-NOC" y llega otro
evento de esa misma parte del equipo:
  - el evento se agrega al historial del incidente (no se crea otra propuesta);
  - si el componente volvió a "Arriba", el incidente se marca como RECUPERADO
    y se sugiere cerrarlo (la decisión sigue siendo de una persona);
  - si vuelve a fallar, se quita la marca de recuperado.
"""

import sqlite3

from app.collector.componentes import es_problema


def relacionar(conn: sqlite3.Connection, evento: dict) -> int | None:
    """Devuelve el id del incidente relacionado o None."""
    if not evento.get("componente"):
        return None
    inc = conn.execute(
        "SELECT i.id, i.recuperado_en FROM incidents i JOIN events e ON e.id = i.event_id "
        "WHERE i.estado != 'cerrado' AND i.device_id = ? AND e.componente = ? AND i.event_id != ? "
        "ORDER BY i.id DESC LIMIT 1",
        (evento["device_id"], evento["componente"], evento["id"])).fetchone()
    if inc is None:
        return None
    estado = evento.get("estado_componente")
    recuperado = estado == "Arriba"
    conn.execute(
        "INSERT INTO incident_log (incident_id, usuario, accion, detalle) VALUES (?, 'sistema', ?, ?)",
        (inc["id"], "recuperado" if recuperado else "evento",
         f"{evento['componente']} · {estado}: {evento['mensaje'][:160]}"))
    if recuperado:
        conn.execute("UPDATE incidents SET recuperado_en = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') "
                     "WHERE id = ? AND recuperado_en IS NULL", (inc["id"],))
    elif es_problema(estado):
        conn.execute("UPDATE incidents SET recuperado_en = NULL WHERE id = ?", (inc["id"],))
    conn.commit()
    return inc["id"]
