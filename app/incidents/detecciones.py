"""
incidents/detecciones.py — Detección automática de patrones (correlación de eventos).

Un evento suelto dice "qué pasó". Varios eventos juntos dicen "qué está ocurriendo".
Estas reglas miran el conjunto y generan una DETECCIÓN que el operador revisa
(igual que las propuestas: el sistema detecta, una persona decide).

Reglas:
  fuerza_bruta      N inicios de sesión fallidos en un equipo en pocos minutos
  fuera_de_horario  cambio de configuración fuera del horario laboral
  puerto_inestable  un puerto/componente que cambia de estado muchas veces (flapping)
  tormenta          un equipo supera el límite de mensajes por minuto
  manipulacion      un log intenta dar órdenes (posible inyección contra una IA)

Si ya hay una detección abierta de la misma regla para el mismo equipo y objeto,
se ACTUALIZA (cantidad, último evento) en lugar de crear otra: así no se inunda la bandeja.
"""

import re
import sqlite3
from datetime import timedelta

from app import config
from app.utils import de_texto, hace

REGLAS = {
    "fuerza_bruta": {"titulo": "Posible ataque de fuerza bruta", "severidad": 2},
    "fuera_de_horario": {"titulo": "Cambio de configuración fuera de horario", "severidad": 3},
    "puerto_inestable": {"titulo": "Puerto o componente inestable", "severidad": 3},
    "tormenta": {"titulo": "Tormenta de eventos", "severidad": 3},
    "manipulacion": {"titulo": "Intento de manipulación dentro de un log", "severidad": 2},
}

_LOGIN_FALLIDO = re.compile(r"login[_ ]?fail|login failure|authentication fail|failed password|admin login failed", re.I)
_LOGIN_FALLIDO_SQL = ("(mensaje LIKE '%login%fail%' OR mensaje LIKE '%authentication fail%' "
                      "OR mensaje LIKE '%failed password%')")
_IP_ORIGEN = re.compile(r"(?:source|from|src|rhost)\s*[:=]?\s*\[?\s*(\d{1,3}(?:\.\d{1,3}){3})", re.I)
_CAMBIO_CONFIG = re.compile(r"CONFIG_I|configured from|configuration (?:was )?changed|cfg[_ ]?change", re.I)


def _registrar(conn: sqlite3.Connection, regla: str, device_id: int, clave: str | None, detalle: str,
               evento_id: int | None, ventana_min: int, cantidad: int | None = None) -> int:
    """Crea la detección o actualiza la que sigue abierta. Devuelve su id."""
    abierta = conn.execute(
        "SELECT id, cantidad FROM detecciones WHERE regla = ? AND device_id = ? AND IFNULL(clave, '') = ? "
        "AND estado = 'nueva' AND actualizada_en >= ? ORDER BY id DESC LIMIT 1",
        (regla, device_id, clave or "", hace(minutos=ventana_min))).fetchone()
    if abierta:
        conn.execute(
            "UPDATE detecciones SET cantidad = ?, detalle = ?, ultimo_evento_id = COALESCE(?, ultimo_evento_id), "
            "actualizada_en = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
            (cantidad if cantidad is not None else abierta["cantidad"] + 1, detalle, evento_id, abierta["id"]))
        conn.commit()
        return abierta["id"]
    r = REGLAS[regla]
    cur = conn.execute(
        "INSERT INTO detecciones (regla, device_id, clave, titulo, detalle, severidad, cantidad, ultimo_evento_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (regla, device_id, clave, r["titulo"], detalle, r["severidad"], cantidad or 1, evento_id))
    conn.commit()
    return cur.lastrowid


def hora_local(recibido_en: str, desfase: int) -> tuple[int, str]:
    local = de_texto(recibido_en) + timedelta(hours=desfase)
    return local.hour, local.strftime("%H:%M")


def evaluar(conn: sqlite3.Connection, evento: dict) -> list[int]:
    """Aplica las reglas a un evento recién guardado (o repetido). Devuelve las detecciones tocadas."""
    tocadas = []
    mensaje, device_id = evento["mensaje"], evento["device_id"]

    # 1) Manipulación: el log intenta dar órdenes
    if evento.get("sospechoso"):
        tocadas.append(_registrar(conn, "manipulacion", device_id, None,
                                  f"Texto sospechoso en un log: \"{mensaje[:160]}\". Se guardó como dato; no se ejecutó nada.",
                                  evento["id"], 60))

    # 2) Fuerza bruta: inicios de sesión fallidos acumulados en la ventana
    if _LOGIN_FALLIDO.search(mensaje):
        ip = (_IP_ORIGEN.search(mensaje) or [None, None])[1]
        ventana = config.obtener(conn, "fuerza_bruta_ventana_min")
        sql = f"SELECT COALESCE(SUM(repeticiones), 0) FROM events WHERE device_id = ? AND recibido_en >= ? AND {_LOGIN_FALLIDO_SQL}"
        params: list = [device_id, hace(minutos=ventana)]
        if ip:
            sql += " AND mensaje LIKE ?"
            params.append(f"%{ip}%")
        intentos = conn.execute(sql, params).fetchone()[0]
        if intentos >= config.obtener(conn, "fuerza_bruta_intentos"):
            origen = f"desde {ip}" if ip else "de origen desconocido"
            tocadas.append(_registrar(conn, "fuerza_bruta", device_id, ip,
                                      f"{intentos} inicios de sesión fallidos {origen} en {ventana} minutos.",
                                      evento["id"], ventana, cantidad=intentos))

    # 3) Cambio de configuración fuera del horario laboral
    if _CAMBIO_CONFIG.search(mensaje):
        inicio, fin = config.obtener(conn, "horario_inicio"), config.obtener(conn, "horario_fin")
        hora, texto_hora = hora_local(evento["recibido_en"], config.obtener(conn, "desfase_utc"))
        if not inicio <= hora < fin:
            tocadas.append(_registrar(conn, "fuera_de_horario", device_id, None,
                                      f"Cambio de configuración a las {texto_hora} (hora local), fuera del horario "
                                      f"laboral {inicio:02d}:00–{fin:02d}:00: \"{mensaje[:140]}\"",
                                      evento["id"], 60))

    # 4) Puerto o componente inestable (cambia de estado muchas veces)
    if evento.get("componente"):
        ventana = config.obtener(conn, "inestable_ventana_min")
        estados = [r[0] for r in conn.execute(
            "SELECT estado_componente FROM events WHERE device_id = ? AND componente = ? AND recibido_en >= ? ORDER BY id",
            (device_id, evento["componente"], hace(minutos=ventana)))]
        cambios = sum(1 for a, b in zip(estados, estados[1:]) if a != b)
        if cambios >= config.obtener(conn, "inestable_cambios"):
            tocadas.append(_registrar(conn, "puerto_inestable", device_id, evento["componente"],
                                      f"{evento['componente']} cambió de estado {cambios} veces en {ventana} minutos "
                                      f"(último: {evento.get('estado_componente')}). Revise cableado, transceptor o energía.",
                                      evento["id"], ventana, cantidad=cambios))
    return tocadas


def tormenta(conn: sqlite3.Connection, device_id: int, limite: int) -> int:
    """Se llama cuando un equipo supera su límite de mensajes por minuto."""
    return _registrar(conn, "tormenta", device_id, None,
                      f"El equipo superó {limite} mensajes por minuto. Los excedentes se descartan para proteger "
                      "el sistema; revise si hay una falla en cascada o un ataque.", None, 10)


def listar(conn: sqlite3.Connection, estado: str | None = "nueva", device_id: int | None = None, limite: int = 100) -> list[dict]:
    sql = ("SELECT x.*, d.nombre AS equipo, d.marca FROM detecciones x LEFT JOIN devices d ON d.id = x.device_id WHERE 1=1")
    params: list = []
    if estado:
        sql += " AND x.estado = ?"
        params.append(estado)
    if device_id is not None:
        sql += " AND x.device_id = ?"
        params.append(device_id)
    sql += " ORDER BY x.estado = 'nueva' DESC, x.severidad, x.actualizada_en DESC LIMIT ?"
    params.append(limite)
    return [dict(r) for r in conn.execute(sql, params)]
