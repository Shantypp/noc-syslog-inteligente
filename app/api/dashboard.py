"""
api/dashboard.py — Datos del tablero principal (RF-04, HU-01).

    GET /api/dashboard   bandeja "Requiere su atención", tarjetas de resumen, estado de equipos,
                         eventos recientes, distribución por severidad e incidentes activos
    GET /api/novedades   consulta liviana para avisos en vivo y contadores del menú
"""

import sqlite3

from fastapi import APIRouter, Depends

from app.api.events import enriquecer
from app.api.puertos import estado_componentes
from app.collector import ingest
from app.console.audit import PENDIENTE
from app.database import get_db
from app.incidents.policy import SLA_MINUTOS, contar_propuestas, minutos_sin_comunicacion, umbral_incidente
from app.security.auth import requiere, tiene_rol
from app.utils import ahora_utc, de_texto, hace

router = APIRouter(tags=["dashboard"])


def estado_equipos(conn: sqlite3.Connection) -> list[dict]:
    """
    Estado operativo de cada equipo (HU-01):
      - 'inactivo' si el administrador lo marcó así (mantenimiento, apagado...)
      - 'sin_comunicacion' si no envía eventos hace más de los minutos configurados
      - 'activo' en otro caso
    """
    limite = hace(minutos=minutos_sin_comunicacion(conn))
    rows = conn.execute(
        "SELECT d.*, MAX(e.recibido_en) AS ultimo_evento, COUNT(e.id) AS total_eventos "
        "FROM devices d LEFT JOIN events e ON e.device_id = d.id "
        "GROUP BY d.id ORDER BY d.nombre").fetchall()
    problemas: dict[int, list[str]] = {}
    for c in estado_componentes(conn):
        if c["con_problema"]:
            problemas.setdefault(c["device_id"], []).append(f'{c["componente"]} ({c["estado"]})')
    equipos = []
    for r in rows:
        eq = dict(r)
        eq["componentes_con_problema"] = problemas.get(eq["id"], [])
        if eq["estado"] != "activo":
            eq["estado_operativo"] = eq["estado"]
        elif not eq["ultimo_evento"] or eq["ultimo_evento"] < limite:
            eq["estado_operativo"] = "sin_comunicacion"
        else:
            eq["estado_operativo"] = "activo"
        equipos.append(eq)
    return equipos


def bandeja(conn: sqlite3.Connection, usuario: dict, equipos: list[dict]) -> list[dict]:
    """
    'Requiere su atención': lo que una persona debe revisar AHORA, en orden de prioridad.
    Cada elemento dice qué pasa, dónde y a qué pantalla ir para resolverlo.
    """
    items = []

    def agregar(prioridad, tipo, titulo, detalle, enlace, severidad=None):
        items.append({"prioridad": prioridad, "tipo": tipo, "titulo": titulo, "detalle": detalle,
                      "enlace": enlace, "severidad": severidad})

    ahora = ahora_utc()
    for i in conn.execute("SELECT i.id, i.titulo, i.severidad, i.abierto_en, i.recuperado_en, i.responsable, "
                          "d.nombre AS equipo FROM incidents i LEFT JOIN devices d ON d.id = i.device_id "
                          "WHERE i.estado != 'cerrado' ORDER BY i.severidad, i.id"):
        minutos = (ahora - de_texto(i["abierto_en"])).total_seconds() / 60
        if i["recuperado_en"]:
            agregar(6, "recuperado", f"Incidente #{i['id']} se recuperó: puede cerrarse",
                    f"{i['equipo'] or ''} · {i['titulo']}", f"incidentes/{i['id']}", i["severidad"])
        elif minutos > SLA_MINUTOS[i["severidad"]]:
            agregar(1, "sla", f"Incidente #{i['id']} con tiempo de atención vencido",
                    f"{i['equipo'] or ''} · {i['titulo']} · abierto hace {round(minutos)} min "
                    f"(máximo {SLA_MINUTOS[i['severidad']]}) · {i['responsable'] or 'sin responsable'}",
                    f"incidentes/{i['id']}", i["severidad"])

    for x in conn.execute("SELECT x.id, x.titulo, x.detalle, x.severidad, d.nombre AS equipo FROM detecciones x "
                          "LEFT JOIN devices d ON d.id = x.device_id WHERE x.estado = 'nueva' "
                          "ORDER BY x.severidad, x.actualizada_en DESC LIMIT 20"):
        agregar(2, "deteccion", f"{x['titulo']} · {x['equipo'] or ''}", x["detalle"], "detecciones", x["severidad"])

    if (n := contar_propuestas(conn)):
        agregar(3, "propuestas", f"{n} evento(s) grave(s) esperan su decisión",
                "Revise si abre un incidente o descarta la propuesta.", "incidentes")

    if tiene_rol(usuario, "administrador"):
        if (n := conn.execute("SELECT COUNT(*) FROM command_audit WHERE resultado = ?", (PENDIENTE,)).fetchone()[0]):
            agregar(4, "aprobaciones", f"{n} cambio(s) de configuración esperan aprobación",
                    "Solo otro administrador puede aprobar lo que alguien propuso.", "auditoria")

    sin_com = [e["nombre"] for e in equipos if e["estado_operativo"] == "sin_comunicacion"]
    if sin_com:
        agregar(5, "sin_comunicacion", f"{len(sin_com)} equipo(s) sin comunicación",
                ", ".join(sin_com[:6]) + ("…" if len(sin_com) > 6 else "") +
                f" · no envían eventos hace más de {minutos_sin_comunicacion(conn)} min.", "inventario")

    items.sort(key=lambda it: (it["prioridad"], it["severidad"] if it["severidad"] is not None else 9))
    return items


@router.get("/api/dashboard")
def resumen(u: dict = Depends(requiere("lector")), conn: sqlite3.Connection = Depends(get_db)):
    desde_24h = hace(horas=24)
    umbral = umbral_incidente(conn)
    uno = lambda sql, *p: conn.execute(sql, p).fetchone()[0]  # noqa: E731 (consulta de un solo valor)

    equipos = estado_equipos(conn)
    por_severidad = {r[0]: r[1] for r in conn.execute(
        "SELECT severidad, COUNT(*) FROM events WHERE recibido_en >= ? GROUP BY severidad", (desde_24h,))}
    recientes = conn.execute(
        "SELECT e.*, d.nombre AS equipo, d.marca FROM events e "
        "LEFT JOIN devices d ON d.id = e.device_id ORDER BY e.id DESC LIMIT 10").fetchall()
    criticos = conn.execute(
        "SELECT e.*, d.nombre AS equipo, d.marca FROM events e "
        "LEFT JOIN devices d ON d.id = e.device_id WHERE e.severidad <= ? "
        "ORDER BY e.id DESC LIMIT 10", (umbral,)).fetchall()
    incidentes_activos = conn.execute(
        "SELECT i.id, i.titulo, i.severidad, i.estado, i.responsable, i.abierto_en, i.recuperado_en, "
        "i.device_id, d.nombre AS equipo FROM incidents i LEFT JOIN devices d ON d.id = i.device_id "
        "WHERE i.estado != 'cerrado' ORDER BY i.severidad, i.id DESC LIMIT 10").fetchall()

    return {
        "atencion": bandeja(conn, u, equipos),
        "tarjetas": {
            "equipos_total": len(equipos),
            "equipos_activos": sum(e["estado_operativo"] == "activo" for e in equipos),
            "equipos_sin_comunicacion": sum(e["estado_operativo"] == "sin_comunicacion" for e in equipos),
            "eventos_24h": uno("SELECT COUNT(*) FROM events WHERE recibido_en >= ?", desde_24h),
            "criticos_24h": uno("SELECT COUNT(*) FROM events WHERE recibido_en >= ? AND severidad <= ?",
                                desde_24h, umbral),
            "sospechosos_24h": uno("SELECT COUNT(*) FROM events WHERE recibido_en >= ? AND sospechoso = 1",
                                   desde_24h),
            "incidentes_abiertos": uno("SELECT COUNT(*) FROM incidents WHERE estado != 'cerrado'"),
            "propuestas_pendientes": contar_propuestas(conn),
            "detecciones_nuevas": uno("SELECT COUNT(*) FROM detecciones WHERE estado = 'nueva'"),
            "componentes_con_problema": sum(len(e["componentes_con_problema"]) for e in equipos),
            "aprobaciones_pendientes": uno("SELECT COUNT(*) FROM command_audit WHERE resultado = ?", PENDIENTE),
        },
        "umbral_sin_comunicacion_min": minutos_sin_comunicacion(conn),
        "umbral_incidente": umbral,
        "equipos": equipos,
        "por_severidad": [por_severidad.get(s, 0) for s in range(8)],
        "eventos_recientes": [enriquecer(r) for r in recientes],
        "eventos_criticos": [enriquecer(r) for r in criticos],
        "incidentes_activos": [dict(r) for r in incidentes_activos],
        "ingreso": ingest.totales(conn, dias=1),
    }


@router.get("/api/novedades")
def novedades(evento: int = 0, deteccion: int = 0, u: dict = Depends(requiere("lector")),
              conn: sqlite3.Connection = Depends(get_db)):
    """
    Consulta liviana (la interfaz la llama cada 15 s). Devuelve:
      - los últimos ids (para saber qué es nuevo la próxima vez)
      - eventos graves y detecciones NUEVOS desde los ids indicados (para mostrar un aviso)
      - los contadores del menú lateral
    """
    umbral = umbral_incidente(conn)
    ultimo_evento = conn.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()[0]
    ultima_deteccion = conn.execute("SELECT COALESCE(MAX(id), 0) FROM detecciones").fetchone()[0]
    graves, nuevas = [], []
    if evento:  # la primera consulta (evento=0) solo toma la referencia, no avisa de lo viejo
        graves = [dict(r) for r in conn.execute(
            "SELECT e.id, e.severidad, e.mensaje, e.componente, d.nombre AS equipo FROM events e "
            "LEFT JOIN devices d ON d.id = e.device_id WHERE e.id > ? AND e.severidad <= ? ORDER BY e.id DESC LIMIT 5",
            (evento, umbral))]
    if deteccion:
        nuevas = [dict(r) for r in conn.execute(
            "SELECT x.id, x.titulo, x.severidad, d.nombre AS equipo FROM detecciones x "
            "LEFT JOIN devices d ON d.id = x.device_id WHERE x.id > ? ORDER BY x.id DESC LIMIT 5", (deteccion,))]
    uno = lambda sql, *p: conn.execute(sql, p).fetchone()[0]  # noqa: E731
    return {
        "ultimo_evento": ultimo_evento,
        "ultima_deteccion": ultima_deteccion,
        "eventos_graves": graves,
        "detecciones": nuevas,
        "contadores": {
            "incidentes": contar_propuestas(conn),
            "detecciones": uno("SELECT COUNT(*) FROM detecciones WHERE estado = 'nueva'"),
            "puertos": sum(c["con_problema"] for c in estado_componentes(conn)),
            "auditoria": uno("SELECT COUNT(*) FROM command_audit WHERE resultado = ?", PENDIENTE)
            if tiene_rol(u, "administrador") else 0,
        },
    }
