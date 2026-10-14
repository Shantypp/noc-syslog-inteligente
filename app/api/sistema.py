"""
api/sistema.py — Estado y administración del sistema.

    GET  /api/sistema/estado           receptor UDP, IP para configurar los equipos, ritmo de eventos (lector)
    GET  /api/sistema/configuracion    parámetros editables y su valor actual (administrador)
    PUT  /api/sistema/configuracion    cambiar parámetros (administrador)
    GET  /api/sistema/respaldo         descargar una copia de la base de datos (administrador)
    POST /api/sistema/demo             cargar equipos y eventos SIMULADOS de demostración (administrador)
    POST /api/sistema/retencion        borrar eventos antiguos según los días de retención (administrador)
"""

import os
import socket
import sqlite3
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app import VERSION, config, mantenimiento
from app.collector import ingest, udp_server
from app.database import get_db
from app.security.auth import requiere
from app.seed import insertar_equipos_simulados
from app.utils import ahora_utc, hace

router = APIRouter(prefix="/api/sistema", tags=["sistema"])
ADMIN = requiere("administrador")

MUESTRAS = Path(__file__).resolve().parents[2] / "data" / "muestras_simuladas.log"


class CambioConfiguracion(BaseModel):
    valores: dict[str, int]


def ips_del_equipo() -> list[str]:
    """IPs de este computador (las que se ponen en 'logging host' de los routers)."""
    try:
        ips = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        ips = []
    return sorted({ip for ip in ips if not ip.startswith("127.")})


@router.get("/estado")
def estado(u: dict = Depends(requiere("lector")), conn: sqlite3.Connection = Depends(get_db)):
    uno = lambda sql, *p: conn.execute(sql, p).fetchone()[0]  # noqa: E731
    host = udp_server.ESTADO["host"] or os.getenv("SYSLOG_UDP_HOST", "127.0.0.1")
    solo_local = host.startswith("127.") or host == "localhost"
    archivo = conn.execute("PRAGMA database_list").fetchone()["file"]
    ruta = Path(archivo) if archivo else None
    return {
        "version": VERSION,
        "udp": {**udp_server.ESTADO, "host": host,
                "puerto": udp_server.ESTADO["puerto"] or int(os.getenv("SYSLOG_UDP_PORT", "5514")),
                "solo_local": solo_local},
        "ips_del_equipo": ips_del_equipo(),
        "eventos_ultimo_minuto": uno("SELECT COALESCE(SUM(repeticiones), 0) FROM events WHERE recibido_en >= ?", hace(minutos=1)),
        "eventos_ultima_hora": uno("SELECT COALESCE(SUM(repeticiones), 0) FROM events WHERE recibido_en >= ?", hace(horas=1)),
        "ultimo_evento": uno("SELECT MAX(recibido_en) FROM events"),
        "equipos": uno("SELECT COUNT(*) FROM devices"),
        "eventos_guardados": uno("SELECT COUNT(*) FROM events"),
        "ingreso_hoy": ingest.totales(conn, dias=1),
        "base_de_datos_mb": round(ruta.stat().st_size / 1_048_576, 2) if ruta and ruta.exists() else None,
        "dias_retencion": config.obtener(conn, "dias_retencion"),
        "hora_servidor_utc": ahora_utc().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/configuracion")
def ver_configuracion(u: dict = Depends(ADMIN), conn: sqlite3.Connection = Depends(get_db)):
    return config.todos(conn)


@router.put("/configuracion")
def cambiar_configuracion(datos: CambioConfiguracion, u: dict = Depends(ADMIN),
                          conn: sqlite3.Connection = Depends(get_db)):
    # Se validan TODOS antes de guardar: o se aplican todos los cambios o ninguno
    for clave, valor in datos.valores.items():
        p = config.PARAMETROS.get(clave)
        if p is None:
            raise HTTPException(422, f"Parámetro desconocido: {clave}")
        if not p.minimo <= valor <= p.maximo:
            raise HTTPException(422, f"{p.nombre}: debe estar entre {p.minimo} y {p.maximo}")
    inicio = datos.valores.get("horario_inicio", config.obtener(conn, "horario_inicio"))
    fin = datos.valores.get("horario_fin", config.obtener(conn, "horario_fin"))
    if inicio >= fin:
        raise HTTPException(422, "El inicio del horario laboral debe ser anterior al fin")
    for clave, valor in datos.valores.items():
        config.guardar(conn, clave, valor, u["usuario"])
    return config.todos(conn)


@router.get("/respaldo")
def respaldo(u: dict = Depends(ADMIN), conn: sqlite3.Connection = Depends(get_db)):
    """Copia completa y consistente de la base de datos (se puede abrir con DB Browser for SQLite)."""
    with tempfile.TemporaryDirectory() as carpeta:
        archivo = mantenimiento.respaldar(conn, Path(carpeta) / "respaldo.db")
        contenido = archivo.read_bytes()
    nombre = f"noc_respaldo_{ahora_utc().strftime('%Y%m%d_%H%M')}.db"
    return Response(contenido, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.post("/demo")
def cargar_demo(u: dict = Depends(ADMIN), conn: sqlite3.Connection = Depends(get_db)):
    """Equipos SIMULADOS (IPs de documentación RFC 5737) + eventos de muestra. Se puede ejecutar varias veces."""
    equipos = insertar_equipos_simulados(conn)
    resumen = ingest.importar_texto(conn, MUESTRAS.read_text(encoding="utf-8")) if MUESTRAS.exists() else {}
    return {"equipos_creados": equipos, "eventos": dict(resumen)}


@router.post("/retencion")
def retencion(u: dict = Depends(ADMIN), conn: sqlite3.Connection = Depends(get_db)):
    return mantenimiento.purgar_antiguos(conn)
