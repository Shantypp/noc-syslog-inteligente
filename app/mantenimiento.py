"""
mantenimiento.py — Tareas de cuidado de la base de datos.

  purgar_antiguos : retención. Borra eventos más viejos que N días, EXCEPTO los
                    vinculados a un incidente (son evidencia). También limpia sesiones
                    vencidas y contadores de más de un año.
  respaldar       : copia consistente de la base de datos (API de backup de SQLite),
                    segura aunque el servidor esté recibiendo eventos.
"""

import sqlite3
from pathlib import Path

from app import config
from app.utils import a_texto, ahora_utc, hace


def purgar_antiguos(conn: sqlite3.Connection, dias: int | None = None) -> dict:
    dias = dias or config.obtener(conn, "dias_retencion")
    limite = hace(horas=24 * dias)
    eventos = conn.execute(
        "DELETE FROM events WHERE recibido_en < ? "
        "AND id NOT IN (SELECT event_id FROM incidents WHERE event_id IS NOT NULL)", (limite,)).rowcount
    sesiones = conn.execute("DELETE FROM sessions WHERE expira_en < ?", (a_texto(ahora_utc()),)).rowcount
    conn.execute("DELETE FROM ingest_stats WHERE dia < date('now', '-365 days')")
    conn.commit()
    return {"eventos_eliminados": eventos, "sesiones_vencidas": sesiones, "dias_retencion": dias}


def respaldar(conn: sqlite3.Connection, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    copia = sqlite3.connect(destino)
    try:
        conn.backup(copia)
    finally:
        copia.close()
    return destino
