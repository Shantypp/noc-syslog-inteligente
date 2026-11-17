"""
notificaciones/alertas.py — Qué situaciones del NOC se avisan por Telegram y con qué texto.

Las funciones nunca lanzan errores: una alerta que falla no puede detener la recepción de Syslog.
"""

import functools
import logging
import sqlite3

from app import config
from app.notificaciones import telegram

log = logging.getLogger("noc.alertas")
NOMBRE_SEVERIDAD = ["Emergencia", "Alerta", "Crítico", "Error", "Advertencia", "Aviso", "Informativo", "Depuración"]


def _seguro(funcion):
    @functools.wraps(funcion)
    def envoltura(*args, **kwargs):
        if not telegram.configurado():
            return False
        try:
            return funcion(*args, **kwargs)
        except Exception:
            log.exception("No se pudo preparar la alerta")
            return False
    return envoltura


def _espera(conn) -> int:
    return config.obtener(conn, "telegram_espera_min")


@_seguro
def conectividad(conn: sqlite3.Connection, equipo: dict, caido: bool, latencia: int | None = None) -> bool:
    if caido:
        texto = f"[CAIDO] {equipo['nombre']} ({equipo['ip']}) no responde al ping (3 intentos seguidos)."
    else:
        texto = f"[RECUPERADO] {equipo['nombre']} ({equipo['ip']}) responde nuevamente" + (
            f" ({latencia} ms)." if latencia else ".")
    # Caída y recuperación tienen claves distintas: la recuperación siempre se avisa
    return telegram.notificar(f"ping:{equipo['id']}:{'caido' if caido else 'arriba'}", texto, _espera(conn))


@_seguro
def red_de_gestion(conn: sqlite3.Connection, conectado: bool, redes: list[str]) -> bool:
    texto = ("[RED OK] El NOC recuperó la conexión con la red de gestión." if conectado else
             f"[SIN RED] El NOC no está conectado a la red de gestión ({', '.join(redes)}). "
             "No se marcan los equipos como caídos: revise el cable o la red del servidor NOC.")
    return telegram.notificar(f"red:{'ok' if conectado else 'sin'}", texto, _espera(conn))


@_seguro
def nueva_deteccion(conn: sqlite3.Connection, deteccion_id: int) -> bool:
    d = conn.execute("SELECT x.*, d.nombre AS equipo FROM detecciones x LEFT JOIN devices d ON d.id = x.device_id "
                     "WHERE x.id = ?", (deteccion_id,)).fetchone()
    if d is None:
        return False
    texto = f"[DETECCION] {d['titulo']} en {d['equipo'] or 'equipo desconocido'}. {d['detalle']}"
    return telegram.notificar(f"det:{d['regla']}:{d['device_id']}:{d['clave'] or ''}", texto, _espera(conn))


@_seguro
def evento_grave(conn: sqlite3.Connection, evento: dict, equipo: dict) -> bool:
    sev = evento.get("severidad")
    if sev is None or sev > config.obtener(conn, "telegram_severidad"):
        return False
    texto = (f"[{NOMBRE_SEVERIDAD[sev].upper()}] sev {sev} en {equipo['nombre']} ({equipo['ip']}): "
             f"{evento['mensaje'][:400]}")
    clave = f"ev:{equipo['id']}:{evento.get('hash_dedup') or evento['mensaje'][:80]}"
    return telegram.notificar(clave, texto, _espera(conn))
