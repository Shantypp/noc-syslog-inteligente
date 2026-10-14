"""
api/detecciones.py — Detecciones automáticas (patrones entre varios eventos).

    GET  /api/detecciones                     listar (?estado=nueva|incidente|descartada|todas, ?device_id=)
    POST /api/detecciones/{id}/incidente      convertir en incidente (operador)
    POST /api/detecciones/{id}/descartar      descartar con motivo (operador)

El sistema detecta; una persona decide qué hacer (igual que con las propuestas).
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import get_db
from app.incidents import detecciones
from app.security.auth import requiere

router = APIRouter(prefix="/api/detecciones", tags=["detecciones"], dependencies=[Depends(requiere("lector"))])
ATIENDE = requiere("operador")


class Descarte(BaseModel):
    motivo: str = Field(min_length=3, max_length=300)


def _pendiente(conn, deteccion_id: int) -> dict:
    fila = conn.execute("SELECT x.*, d.nombre AS equipo FROM detecciones x "
                        "LEFT JOIN devices d ON d.id = x.device_id WHERE x.id = ?", (deteccion_id,)).fetchone()
    if fila is None:
        raise HTTPException(404, f"No existe la detección {deteccion_id}")
    if fila["estado"] != "nueva":
        raise HTTPException(409, f"La detección ya fue revisada ({fila['estado']})")
    return dict(fila)


@router.get("")
def listar(estado: str = "nueva", device_id: int | None = None, conn: sqlite3.Connection = Depends(get_db)):
    if estado not in ("nueva", "incidente", "descartada", "todas"):
        raise HTTPException(422, "estado debe ser nueva, incidente, descartada o todas")
    return detecciones.listar(conn, None if estado == "todas" else estado, device_id)


@router.post("/{deteccion_id}/incidente", status_code=201)
def a_incidente(deteccion_id: int, u: dict = Depends(ATIENDE), conn: sqlite3.Connection = Depends(get_db)):
    x = _pendiente(conn, deteccion_id)
    titulo = f"{x['titulo']} en {x['equipo'] or 'equipo desconocido'}" + (f" ({x['clave']})" if x["clave"] else "")
    cur = conn.execute("INSERT INTO incidents (device_id, titulo, severidad) VALUES (?, ?, ?)",
                       (x["device_id"], titulo[:150], x["severidad"]))
    conn.execute("INSERT INTO incident_log (incident_id, usuario, accion, detalle) VALUES (?, ?, 'creado', ?)",
                 (cur.lastrowid, u["usuario"], f"desde detección automática #{deteccion_id}: {x['detalle']}"))
    conn.execute("UPDATE detecciones SET estado = 'incidente', incident_id = ?, revisado_por = ? WHERE id = ?",
                 (cur.lastrowid, u["usuario"], deteccion_id))
    conn.commit()
    return {"incident_id": cur.lastrowid}


@router.post("/{deteccion_id}/descartar")
def descartar(deteccion_id: int, datos: Descarte, u: dict = Depends(ATIENDE), conn: sqlite3.Connection = Depends(get_db)):
    _pendiente(conn, deteccion_id)
    conn.execute("UPDATE detecciones SET estado = 'descartada', revisado_por = ?, motivo = ? WHERE id = ?",
                 (u["usuario"], datos.motivo, deteccion_id))
    conn.commit()
    return {"ok": True}
