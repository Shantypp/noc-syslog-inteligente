"""
collector/ingest.py — Flujo de ingreso de un mensaje (RF-02, RF-03).

Implementa los pasos 1 y 2 del flujo obligatorio del curso:
    1. Ingreso     -> llega por UDP o por archivo
    2. Validación  -> formato, límite por equipo, fuente autorizada, limpieza,
                      detección de sospechosos y deduplicación
y lo guarda en la tabla events. Después:
    - aplica las DETECCIONES automáticas (fuerza bruta, fuera de horario, puerto inestable...)
    - lo RELACIONA con el incidente abierto de esa misma parte del equipo (si existe)

¿Cómo se sabe de qué equipo viene?
  - Mensaje desde una IP real   -> se busca la IP en el inventario (allowlist).
  - Mensaje desde 127.0.0.1 o importado de archivo (LABORATORIO) -> se busca el
    HOSTNAME del mensaje entre los nombres del inventario.
  Si no se encuentra, el mensaje se RECHAZA: solo se aceptan fuentes inventariadas.
"""

import ipaddress
import sqlite3
from collections import Counter

from app import config
from app.collector.componentes import identificar
from app.collector.parser import MensajeInvalido, parse_syslog
from app.incidents import correlacion, detecciones
from app.security.controls import (LimitadorTasa, es_sospechoso, huella_dedup,
                                   limpiar_mensaje)

# Límite de mensajes por minuto POR EQUIPO. El valor se toma de la configuración en cada mensaje.
limitador_global = LimitadorTasa(config.PARAMETROS["limite_por_minuto"].valor_por_defecto())

# Contadores desde que arrancó el servidor (los históricos por día están en la tabla ingest_stats)
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
    Procesa UN mensaje. Devuelve {"resultado": ..., "event_id": ..., "detecciones": [...], "incidente": ...}.
    resultados posibles: guardado | duplicado | limitado | invalido | fuente_no_autorizada
    """
    if limitador is None:
        limitador = limitador_global
        limitador.limite = config.obtener(conn, "limite_por_minuto")

    try:
        datos = parse_syslog(crudo)
    except MensajeInvalido:
        datos = None

    # Control de tormentas POR EQUIPO: cada fuente tiene su cupo por minuto.
    # En laboratorio todos llegan desde 127.0.0.1, así que la fuente es el hostname.
    fuente = ip_origen
    if _es_laboratorio(ip_origen) and datos and datos["hostname"]:
        fuente = datos["hostname"].lower()
    if not limitador.permitir(fuente):
        # Solo el PRIMER descarte del minuto genera la detección (no se escribe en la BD por cada mensaje)
        if limitador.rechazados(fuente) == 1:
            _avisar_tormenta(conn, ip_origen, datos, limitador.limite)
        return _contar(conn, "limitado")

    if datos is None:
        return _contar(conn, "invalido")

    equipo = _buscar_equipo(conn, ip_origen, datos["hostname"])
    if equipo is None:
        return _contar(conn, "fuente_no_autorizada")

    mensaje = limpiar_mensaje(datos["mensaje"])
    huella = huella_dedup(equipo["id"], datos["severidad"], mensaje)
    # ¿Qué parte del equipo genera el evento? (puerto, fuente, sensor, túnel...)
    componente, estado_componente = identificar(mensaje)

    # Deduplicación: ¿llegó el mismo mensaje hace poco? -> se suma como repetición
    ventana = config.obtener(conn, "ventana_dedup_s")
    previo = conn.execute(
        "SELECT * FROM events WHERE hash_dedup = ? "
        "AND recibido_en >= strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?) "
        "ORDER BY id DESC LIMIT 1",
        (huella, f"-{ventana} seconds"),
    ).fetchone()
    if previo and componente:
        # Un puerto que cae, sube y vuelve a caer NO es una repetición: es un cambio de estado.
        # Solo se agrupa si ese componente no reportó nada distinto desde el mensaje anterior.
        ultimo = conn.execute("SELECT MAX(id) FROM events WHERE device_id = ? AND componente = ?",
                              (equipo["id"], componente)).fetchone()[0]
        if ultimo != previo["id"]:
            previo = None
    if previo:
        conn.execute("UPDATE events SET repeticiones = repeticiones + 1 WHERE id = ?", (previo["id"],))
        conn.commit()
        # Las repeticiones también cuentan para las reglas (ej. 20 "login failed" idénticos = fuerza bruta)
        tocadas = detecciones.evaluar(conn, dict(previo) | {"repeticiones": previo["repeticiones"] + 1})
        return _contar(conn, "duplicado", previo["id"], tocadas)

    sospechoso = int(es_sospechoso(mensaje))

    cur = conn.execute(
        "INSERT INTO events (device_id, timestamp_equipo, ip_origen, hostname, facility, "
        "severidad, mensaje, mensaje_crudo, hash_dedup, sospechoso, origen, componente, estado_componente) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (equipo["id"], datos["timestamp_equipo"], ip_origen, datos["hostname"],
         datos["facility"], datos["severidad"], mensaje, limpiar_mensaje(crudo),
         huella, sospechoso, equipo["origen"], componente, estado_componente),
    )
    conn.commit()
    evento = dict(conn.execute("SELECT * FROM events WHERE id = ?", (cur.lastrowid,)).fetchone())
    tocadas = detecciones.evaluar(conn, evento)
    incidente = correlacion.relacionar(conn, evento)
    return _contar(conn, "guardado", cur.lastrowid, tocadas, incidente)


def _avisar_tormenta(conn, ip_origen: str, datos: dict | None, limite: int) -> None:
    """Registra una detección de tormenta para el equipo que superó su límite."""
    equipo = _buscar_equipo(conn, ip_origen, datos["hostname"] if datos else None)
    if equipo is not None:  # solo de equipos inventariados (una IP desconocida no genera alertas)
        detecciones.tormenta(conn, equipo["id"], limite)


def importar_texto(conn: sqlite3.Connection, contenido: str,
                   limitador: LimitadorTasa | None = None) -> Counter:
    """Importa un archivo .log (un mensaje por línea). Devuelve el resumen."""
    resumen: Counter = Counter()
    for linea in contenido.splitlines():
        if linea.strip() and not linea.lstrip().startswith("#"):  # ignora vacías y comentarios
            resumen[procesar_mensaje(conn, linea, IMPORTADO, limitador)["resultado"]] += 1
    return resumen


def _contar(conn: sqlite3.Connection, resultado: str, event_id: int | None = None,
            tocadas: list[int] | None = None, incidente: int | None = None) -> dict:
    estadisticas[resultado] += 1
    conn.execute(
        "INSERT INTO ingest_stats (dia, resultado, cantidad) VALUES (strftime('%Y-%m-%d', 'now'), ?, 1) "
        "ON CONFLICT(dia, resultado) DO UPDATE SET cantidad = cantidad + 1", (resultado,))
    conn.commit()
    return {"resultado": resultado, "event_id": event_id, "detecciones": tocadas or [], "incidente": incidente}


def totales(conn: sqlite3.Connection, dias: int | None = None) -> dict:
    """Totales históricos por resultado (todos los días o los últimos N)."""
    sql, params = "SELECT resultado, SUM(cantidad) FROM ingest_stats", []
    if dias:
        sql += " WHERE dia >= date('now', ?)"
        params.append(f"-{dias - 1} days")
    return {r[0]: r[1] for r in conn.execute(sql + " GROUP BY resultado", params)}
