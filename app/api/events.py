"""
api/events.py — Endpoints de eventos Syslog (RF-02, RF-03).

    GET  /api/events               listar eventos (filtros básicos; se amplían en la Fase 4)
    POST /api/events/importar      importar un archivo .log
    GET  /api/events/estadisticas  qué pasó con los mensajes (guardados, rechazados, etc.)
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile

from app.collector import ingest
from app.collector.parser import FACILITIES, SEVERIDADES
from app.database import get_db

router = APIRouter(prefix="/api/events", tags=["eventos"])

TAMANO_MAXIMO_ARCHIVO = 1_000_000  # 1 MB: evita que un archivo enorme bloquee el servidor


@router.get("")
def listar(device_id: int | None = None,
           sev_max: int | None = Query(None, ge=0, le=7, description="Ej. 3 = errores o más graves"),
           solo_sospechosos: bool = False,
           limit: int = Query(100, ge=1, le=500),
           conn: sqlite3.Connection = Depends(get_db)):
    sql = ("SELECT e.*, d.nombre AS equipo, d.marca FROM events e "
           "LEFT JOIN devices d ON d.id = e.device_id WHERE 1=1")
    params: list = []
    if device_id is not None:
        sql += " AND e.device_id = ?"
        params.append(device_id)
    if sev_max is not None:
        sql += " AND e.severidad <= ?"
        params.append(sev_max)
    if solo_sospechosos:
        sql += " AND e.sospechoso = 1"
    sql += " ORDER BY e.id DESC LIMIT ?"
    params.append(limit)

    eventos = []
    for row in conn.execute(sql, params).fetchall():
        e = dict(row)
        e["severidad_nombre"] = SEVERIDADES[e["severidad"]]
        e["facility_nombre"] = FACILITIES.get(e["facility"])
        eventos.append(e)
    return eventos


@router.post("/importar")
async def importar(archivo: UploadFile, conn: sqlite3.Connection = Depends(get_db)):
    """Importa un archivo de texto con un mensaje Syslog por línea."""
    contenido = await archivo.read(TAMANO_MAXIMO_ARCHIVO + 1)
    if len(contenido) > TAMANO_MAXIMO_ARCHIVO:
        raise HTTPException(413, "El archivo supera 1 MB")
    resumen = ingest.importar_texto(conn, contenido.decode("utf-8", errors="replace"))
    return {"archivo": archivo.filename, "resumen": dict(resumen)}


@router.get("/estadisticas")
def estadisticas():
    """Contadores desde que arrancó el servidor (evidencia de los controles de seguridad)."""
    return dict(ingest.estadisticas)
