"""
collector/ingest.py — Flujo de ingreso de un mensaje (RF-02, RF-03).

Implementa los pasos 1 y 2 del flujo obligatorio del curso:
    1. Ingreso     -> llega por UDP o por archivo
    2. Validación  -> rate limit, fuente autorizada, formato, limpieza,
                      detección de sospechosos y deduplicación
y lo guarda en la tabla events.

¿Cómo se sabe de qué equipo viene?
  - Mensaje desde una IP real   -> se busca la IP en el inventario (allowlist).
  - Mensaje desde 127.0.0.1 o importado de archivo (LABORATORIO) -> se busca el
    HOSTNAME del mensaje entre los nombres del inventario.
  Si no se encuentra, el mensaje se RECHAZA: solo se aceptan fuentes inventariadas.
"""

import ipaddress
import os
import sqlite3
from collections import Counter

from app.collector.componentes import identificar
from app.collector.parser import MensajeInvalido, parse_syslog
from app.security.controls import (LimitadorTasa, es_sospechoso, huella_dedup,
                                   limpiar_mensaje)

VENTANA_DEDUP = int(os.getenv("DEDUP_WINDOW_SECONDS", "60"))
limitador_global = LimitadorTasa(int(os.getenv("RATE_LIMIT_PER_MINUTE", "300")))

# Contadores en memoria de lo que pasó con cada mensaje (se ven en /api/events/estadisticas)
estadisticas: Counter = Counter()

IMPORTADO = "archivo"  # valor de ip_origen para mensajes importados


def _es_laboratorio(ip_origen: str) -> bool:
    if ip_origen == IMPORTADO:
        return True
    try:
        return ipaddress.ip_address(ip_origen).is_loopback
    except ValueError:
        return False


def _buscar_equipo(conn, ip_origen: str, hostname: str | None):
    if _es_laboratorio(ip_origen):
        if not hostname:
            return None
        return conn.execute("SELECT * FROM devices WHERE nombre = ? COLLATE NOCASE",
                            (hostname,)).fetchone()
    return conn.execute("SELECT * FROM devices WHERE ip = ?", (ip_origen,)).fetchone()


def procesar_mensaje(conn: sqlite3.Connection, crudo: str, ip_origen: str,
                     limitador: LimitadorTasa | None = None) -> dict:
    """
    Procesa UN mensaje. Devuelve {"resultado": ..., "event_id": ...}.
    resultados posibles: guardado | duplicado | limitado | invalido | fuente_no_autorizada
    """
    limitador = limitador or limitador_global

    # Control de tormentas: si se supera el límite por minuto, se descarta.
    if not limitador.permitir():
        return _contar("limitado")

    try:
        datos = parse_syslog(crudo)
    except MensajeInvalido:
        return _contar("invalido")

    equipo = _buscar_equipo(conn, ip_origen, datos["hostname"])
    if equipo is None:
        return _contar("fuente_no_autorizada")

    mensaje = limpiar_mensaje(datos["mensaje"])
    huella = huella_dedup(equipo["id"], datos["severidad"], mensaje)

    # Deduplicación: ¿llegó el mismo mensaje hace menos de VENTANA_DEDUP segundos?
    previo = conn.execute(
        "SELECT id FROM events WHERE hash_dedup = ? "
        "AND recibido_en >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?) "
        "ORDER BY id DESC LIMIT 1",
        (huella, f"-{VENTANA_DEDUP} seconds"),
    ).fetchone()
    if previo:
        conn.execute("UPDATE events SET repeticiones = repeticiones + 1 WHERE id = ?", (previo["id"],))
        conn.commit()
        return _contar("duplicado", previo["id"])

    # ¿Qué parte del equipo genera el evento? (puerto, fuente, sensor, túnel...)
    componente, estado_componente = identificar(mensaje)

    cur = conn.execute(
        "INSERT INTO events (device_id, timestamp_equipo, ip_origen, hostname, facility, "
        "severidad, mensaje, mensaje_crudo, hash_dedup, sospechoso, origen, componente, estado_componente) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (equipo["id"], datos["timestamp_equipo"], ip_origen, datos["hostname"],
         datos["facility"], datos["severidad"], mensaje, limpiar_mensaje(crudo),
         huella, int(es_sospechoso(mensaje)), equipo["origen"], componente, estado_componente),
    )
    conn.commit()
    return _contar("guardado", cur.lastrowid)


def importar_texto(conn: sqlite3.Connection, contenido: str,
                   limitador: LimitadorTasa | None = None) -> Counter:
    """Importa un archivo .log (un mensaje por línea). Devuelve el resumen."""
    resumen: Counter = Counter()
    for linea in contenido.splitlines():
        if linea.strip() and not linea.lstrip().startswith("#"):  # ignora vacías y comentarios
            resumen[procesar_mensaje(conn, linea, IMPORTADO, limitador)["resultado"]] += 1
    return resumen


def _contar(resultado: str, event_id: int | None = None) -> dict:
    estadisticas[resultado] += 1
    return {"resultado": resultado, "event_id": event_id}
