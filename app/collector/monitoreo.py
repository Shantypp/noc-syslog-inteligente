"""
collector/monitoreo.py — ¿Está vivo cada equipo? (ping periódico)

Syslog solo avisa cuando pasa algo: un equipo sano puede pasar horas en silencio y,
mirando solo los mensajes, parecería "sin comunicación". Por eso el NOC le hace ping
a cada equipo REAL del inventario cada N segundos (Configuración › intervalo_ping_s, 10 por defecto):

  - si responde, está activo y se guarda la latencia;
  - si falla 3 veces seguidas (unos 30 s), se registra el evento "Conectividad (ping) · Caído"
    (severidad 2), que entra al flujo normal: propuesta de incidente y detecciones;
  - cuando vuelve a responder, se registra "Conectividad (ping) · Arriba" y, si había
    un incidente abierto por esa caída, queda marcado como Recuperado.

Solo se hace ping a los equipos del inventario marcados como reales y activos
(nunca a las IPs simuladas ni a direcciones que no estén en el inventario).
"""

import asyncio
import ipaddress
import logging
import os
import re
import sqlite3
import subprocess

from app import config
from app.database import get_connection
from app.incidents import correlacion, detecciones
from app.utils import a_texto, ahora_utc

log = logging.getLogger("noc.monitoreo")

FALLOS_PARA_CAIDO = 3            # fallos seguidos antes de declarar el equipo caído
COMPONENTE = "Conectividad (ping)"
_TIEMPO = re.compile(r"(?:time|tiempo)\s*[=<]\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)


def interpretar_ping(salida: str, codigo: int) -> tuple[bool, int | None]:
    """
    (responde, latencia_ms). En Windows, "Host de destino inaccesible" devuelve código 0
    pero no trae TTL: por eso se exige que la respuesta tenga TTL.
    """
    if codigo != 0 or "ttl=" not in salida.lower():
        return False, None
    m = _TIEMPO.search(salida)
    return True, (max(1, round(float(m.group(1).replace(",", ".")))) if m else None)


def hacer_ping(ip: str, espera_s: int = 1) -> tuple[bool, int | None]:
    """Un ping al equipo. Se usa el comando del sistema (no requiere permisos de administrador)."""
    ipaddress.ip_address(ip)  # solo direcciones IP válidas: nada de texto extra en el comando
    if os.name == "nt":
        args, flags = ["ping", "-n", "1", "-w", str(espera_s * 1000), ip], 0x08000000  # sin abrir ventana
    else:
        args, flags = ["ping", "-c", "1", "-W", str(espera_s), ip], 0
    try:
        r = subprocess.run(args, capture_output=True, timeout=espera_s + 3, creationflags=flags)
    except (OSError, subprocess.TimeoutExpired):
        return False, None
    return interpretar_ping(r.stdout.decode(errors="replace"), r.returncode)


def _registrar_evento(conn: sqlite3.Connection, equipo: dict, severidad: int, estado: str, mensaje: str) -> int:
    cur = conn.execute(
        "INSERT INTO events (device_id, ip_origen, hostname, severidad, mensaje, mensaje_crudo, origen, "
        "componente, estado_componente) VALUES (?, 'noc', ?, ?, ?, ?, ?, ?, ?)",
        (equipo["id"], equipo["nombre"], severidad, mensaje, mensaje, equipo["origen"], COMPONENTE, estado))
    conn.commit()
    evento = dict(conn.execute("SELECT * FROM events WHERE id = ?", (cur.lastrowid,)).fetchone())
    detecciones.evaluar(conn, evento)   # ej.: un equipo que cae y vuelve muchas veces = inestable
    correlacion.relacionar(conn, evento)  # si había incidente por la caída, queda "Recuperado"
    return cur.lastrowid


def registrar_resultado(conn: sqlite3.Connection, equipo: dict, responde: bool, latencia: int | None) -> int | None:
    """Guarda el resultado del ping. Si el equipo cambió de estado, registra el evento y devuelve su id."""
    antes = equipo.get("alcanzable")          # 1 = respondía, 0 = caído, None = aún no se sabía
    fallos = 0 if responde else (equipo.get("fallos_ping") or 0) + 1
    if responde:
        ahora = 1
    elif fallos >= FALLOS_PARA_CAIDO:
        ahora = 0
    else:
        ahora = antes                          # un ping perdido no basta para declararlo caído
    conn.execute("UPDATE devices SET alcanzable = ?, ultimo_ping = ?, latencia_ms = ?, fallos_ping = ? WHERE id = ?",
                 (ahora, a_texto(ahora_utc()), latencia if responde else None, fallos, equipo["id"]))
    conn.commit()
    if ahora == 0 and antes != 0:
        return _registrar_evento(conn, equipo, 2, "Caído",
                                 f"[NOC] {equipo['nombre']} no responde al ping ({FALLOS_PARA_CAIDO} intentos seguidos)")
    if ahora == 1 and antes == 0:
        return _registrar_evento(conn, equipo, 5, "Arriba",
                                 f"[NOC] {equipo['nombre']} responde nuevamente al ping"
                                 + (f" ({latencia} ms)" if latencia is not None else ""))
    return None


def _equipos_a_revisar() -> tuple[int, list[dict]]:
    conn = get_connection()
    try:
        intervalo = config.obtener(conn, "intervalo_ping_s")
        equipos = [dict(r) for r in conn.execute(
            "SELECT * FROM devices WHERE origen = 'real' AND estado = 'activo'")] if intervalo else []
        return intervalo, equipos
    finally:
        conn.close()


async def ciclo() -> None:
    """Tarea de fondo: se inicia con el servidor y revisa los equipos cada N segundos."""
    log.info("Monitoreo por ping iniciado")
    while True:
        intervalo = 10
        try:
            intervalo, equipos = _equipos_a_revisar()
            if equipos:
                resultados = await asyncio.gather(*(asyncio.to_thread(hacer_ping, e["ip"]) for e in equipos))
                conn = get_connection()
                try:
                    for equipo, (responde, latencia) in zip(equipos, resultados):
                        registrar_resultado(conn, equipo, responde, latencia)
                finally:
                    conn.close()
        except Exception:  # un error de una ronda no debe detener el monitoreo
            log.exception("Error en el monitoreo por ping")
        await asyncio.sleep(intervalo or 10)
