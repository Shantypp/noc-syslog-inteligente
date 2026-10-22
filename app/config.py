"""
config.py — Configuración del sistema editable desde la aplicación.

Cada parámetro tiene un valor por defecto (que puede venir del archivo .env) y
el administrador puede cambiarlo en la pantalla "Configuración" sin tocar archivos
ni reiniciar el servidor. Los cambios quedan registrados (quién y cuándo).
"""

import os
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Parametro:
    clave: str
    nombre: str
    descripcion: str
    defecto: int
    minimo: int
    maximo: int
    unidad: str = ""
    variable_env: str | None = None

    def valor_por_defecto(self) -> int:
        if self.variable_env and os.getenv(self.variable_env):
            try:
                return int(os.environ[self.variable_env])
            except ValueError:
                pass
        return self.defecto


PARAMETROS = {p.clave: p for p in [
    # --- Incidentes y estado de equipos
    Parametro("umbral_incidente", "Severidad que genera propuesta de incidente",
              "Los eventos con esta severidad o más graves (número menor) se proponen como incidente.", 2, 0, 7, "", "INCIDENT_MAX_SEVERITY"),
    Parametro("minutos_sin_comunicacion", "Minutos para \"sin comunicación\"",
              "Si un equipo no envía eventos en este tiempo (y no se le puede hacer ping), aparece sin comunicación.", 10, 1, 1440, "min", "NO_COMM_MINUTES"),
    Parametro("intervalo_ping_s", "Revisar los equipos reales con ping cada",
              "El NOC le hace ping a cada equipo REAL del inventario para saber si está vivo, aunque no envíe mensajes. "
              "Si falla 3 veces seguidas se registra \"Conectividad · Caído\". 0 = desactivado.", 30, 0, 3600, "s", "PING_INTERVAL_SECONDS"),
    # --- Control de tormentas
    Parametro("ventana_dedup_s", "Ventana para agrupar mensajes repetidos",
              "Un mensaje idéntico del mismo equipo dentro de esta ventana se cuenta como repetición.", 60, 0, 3600, "s", "DEDUP_WINDOW_SECONDS"),
    Parametro("limite_por_minuto", "Máximo de mensajes por equipo por minuto",
              "Lo que exceda se descarta y se registra una detección de tormenta. Es por equipo: uno ruidoso no silencia a los demás.", 300, 10, 100000, "msg/min", "RATE_LIMIT_PER_MINUTE"),
    # --- Detecciones automáticas
    Parametro("fuerza_bruta_intentos", "Intentos fallidos para detectar fuerza bruta",
              "Inicios de sesión fallidos en un equipo, dentro de la ventana, que generan una detección.", 5, 2, 1000, "intentos", "BRUTE_FORCE_ATTEMPTS"),
    Parametro("fuerza_bruta_ventana_min", "Ventana para fuerza bruta",
              "Minutos en los que se cuentan los inicios de sesión fallidos.", 5, 1, 1440, "min"),
    Parametro("inestable_cambios", "Cambios de estado para \"puerto inestable\"",
              "Si un puerto o componente cambia de estado esta cantidad de veces en la ventana, se detecta inestabilidad.", 3, 2, 100, "cambios"),
    Parametro("inestable_ventana_min", "Ventana para puerto inestable", "Minutos en los que se cuentan los cambios.", 10, 1, 1440, "min"),
    Parametro("horario_inicio", "Inicio del horario laboral",
              "Los cambios de configuración fuera del horario laboral generan una detección.", 7, 0, 23, "h", "BUSINESS_START"),
    Parametro("horario_fin", "Fin del horario laboral", "Hora en que termina el horario laboral.", 19, 1, 24, "h", "BUSINESS_END"),
    Parametro("desfase_utc", "Zona horaria (desfase respecto a UTC)",
              "Colombia es -5. Se usa para saber la hora local de cada evento.", -5, -12, 14, "h", "UTC_OFFSET_HOURS"),
    # --- Datos
    Parametro("dias_retencion", "Días de retención de eventos",
              "Los eventos más antiguos se eliminan automáticamente, salvo los vinculados a incidentes.", 90, 1, 3650, "días", "RETENTION_DAYS"),
]}


class ValorInvalido(ValueError):
    pass


def obtener(conn: sqlite3.Connection, clave: str) -> int:
    """Valor actual de un parámetro (el guardado o, si no hay, el por defecto)."""
    p = PARAMETROS[clave]
    fila = conn.execute("SELECT valor FROM settings WHERE clave = ?", (clave,)).fetchone()
    if fila is not None:
        try:
            return int(fila["valor"])
        except ValueError:
            pass
    return p.valor_por_defecto()


def todos(conn: sqlite3.Connection) -> list[dict]:
    guardados = {r["clave"]: dict(r) for r in conn.execute("SELECT * FROM settings")}
    salida = []
    for p in PARAMETROS.values():
        g = guardados.get(p.clave)
        salida.append({
            "clave": p.clave, "nombre": p.nombre, "descripcion": p.descripcion, "unidad": p.unidad,
            "minimo": p.minimo, "maximo": p.maximo, "defecto": p.valor_por_defecto(),
            "valor": obtener(conn, p.clave),
            "modificado_por": g["actualizado_por"] if g else None, "modificado_en": g["actualizado_en"] if g else None,
        })
    return salida


def guardar(conn: sqlite3.Connection, clave: str, valor: int, usuario: str) -> None:
    if clave not in PARAMETROS:
        raise ValorInvalido(f"Parámetro desconocido: {clave}")
    p = PARAMETROS[clave]
    if not isinstance(valor, int) or not p.minimo <= valor <= p.maximo:
        raise ValorInvalido(f"{p.nombre}: debe ser un número entre {p.minimo} y {p.maximo}")
    conn.execute(
        "INSERT INTO settings (clave, valor, actualizado_por) VALUES (?, ?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor, actualizado_por = excluded.actualizado_por, "
        "actualizado_en = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')", (clave, str(valor), usuario))
    conn.commit()
