"""
api/events.py — Endpoints de eventos Syslog (RF-02, RF-03, RF-04).

    GET  /api/events               listar con filtros (fecha, marca, equipo, severidad)
    POST /api/events/importar      importar un archivo .log
    GET  /api/events/estadisticas  qué pasó con los mensajes (guardados, rechazados, etc.)
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile

from app.collector import ingest
from app.collector.parser import FACILITIES, SEVERIDADES
from app.database import get_db
from app.models import Marca
from app.utils import normalizar_fecha

router = APIRouter(prefix="/api/events", tags=["eventos"])

TAMANO_MAXIMO_ARCHIVO = 1_000_000  # 1 MB: evita que un archivo enorme bloquee el servidor


def _fecha(valor: str | None, campo: str) -> str | None:
    if not valor:
        return None
    try:
        return normalizar_fecha(valor)
    except ValueError:
        raise HTTPException(422, f"Fecha inválida en '{campo}': {valor}")


def enriquecer(row) -> dict:
    """Agrega los nombres legibles de severidad y facility."""
    e = dict(row)
    e["severidad_nombre"] = SEVERIDADES[e["severidad"]]
    e["facility_nombre"] = FACILITIES.get(e["facility"])
    return e


@router.get("")
def listar(desde: str | None = Query(None, description="Fecha/hora inicial (ISO 8601)"),
           hasta: str | None = Query(None, description="Fecha/hora final (ISO 8601)"),
           marca: Marca | None = None,
           device_id: int | None = None,
           sev_min: int = Query(0, ge=0, le=7),
           sev_max: int = Query(7, ge=0, le=7, description="Ej. 3 = errores o más graves"),
           solo_sospechosos: bool = False,
           limit: int = Query(100, ge=1, le=500),
           offset: int = Query(0, ge=0),
           conn: sqlite3.Connection = Depends(get_db)):
    """Devuelve {total, eventos}. `total` cuenta TODOS los que cumplen el filtro (HU-02)."""
    # Cada filtro agrega una condición con parámetro "?" (nunca texto concatenado: evita inyección SQL)
    condiciones, params = ["e.severidad BETWEEN ? AND ?"], [sev_min, sev_max]
    if (d := _fecha(desde, "desde")):
        condiciones.append("e.recibido_en >= ?")
        params.append(d)
    if (h := _fecha(hasta, "hasta")):
        condiciones.append("e.recibido_en <= ?")
        params.append(h)
    if marca:
        condiciones.append("d.marca = ?")
        params.append(marca.value)
    if device_id is not None:
        condiciones.append("e.device_id = ?")
        params.append(device_id)
    if solo_sospechosos:
        condiciones.append("e.sospechoso = 1")

    base = (" FROM events e LEFT JOIN devices d ON d.id = e.device_id "
            "LEFT JOIN incidents i ON i.event_id = e.id "
            "WHERE " + " AND ".join(condiciones))
    total = conn.execute("SELECT COUNT(*)" + base, params).fetchone()[0]
    rows = conn.execute(
        "SELECT e.*, d.nombre AS equipo, d.marca, i.id AS incident_id" + base +
        " ORDER BY e.id DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
    return {"total": total, "eventos": [enriquecer(r) for r in rows]}


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
