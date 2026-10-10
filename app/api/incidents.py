"""
api/incidents.py — Gestión de incidentes (RF-05, HU-03).

    GET   /api/incidents                 listar (filtro ?estado=)
    GET   /api/incidents/propuestas      eventos graves esperando revisión humana
    GET   /api/incidents/{id}            detalle + evento original + seguimiento
    POST  /api/incidents                 crear (desde un evento o manual)
    PATCH /api/incidents/{id}            asignar responsable, cambiar estado o agregar nota
    POST  /api/incidents/{id}/cerrar     cerrar (exige causa y solución)

Ciclo de vida: abierto -> asignado -> en_progreso -> cerrado
"""

import sqlite3
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.database import get_db
from app.incidents.policy import SLA_MINUTOS, propuestas
from app.security.auth import requiere
from app.utils import ahora_utc, de_texto

router = APIRouter(prefix="/api/incidents", tags=["incidentes"], dependencies=[Depends(requiere("lector"))])
ATIENDE = requiere("operador")  # abrir, gestionar y cerrar: operador o administrador

AHORA_UTC = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


class EstadoIncidente(str, Enum):
    abierto = "abierto"
    asignado = "asignado"
    en_progreso = "en_progreso"


class IncidenteNuevo(BaseModel):
    event_id: int | None = Field(None, description="Evento que lo origina (recomendado)")
    titulo: str | None = Field(None, max_length=150)
    severidad: int | None = Field(None, ge=0, le=7)
    device_id: int | None = None
    responsable: str | None = Field(None, max_length=40)

    @model_validator(mode="after")
    def manual_requiere_datos(self):
        if self.event_id is None and (not self.titulo or self.severidad is None):
            raise ValueError("sin event_id debes indicar titulo y severidad")
        return self


class IncidenteCambio(BaseModel):
    responsable: str | None = Field(None, max_length=40)
    estado: EstadoIncidente | None = None
    nota: str | None = Field(None, max_length=500)


class IncidenteCierre(BaseModel):
    causa: str = Field(min_length=3, max_length=500)
    solucion: str = Field(min_length=3, max_length=500)


def _registrar(conn, incident_id: int, usuario: str, accion: str, detalle: str | None = None):
    """Cada cambio queda en incident_log: trazabilidad (RNF-03)."""
    conn.execute("INSERT INTO incident_log (incident_id, usuario, accion, detalle) VALUES (?, ?, ?, ?)",
                 (incident_id, usuario, accion, detalle))


def _con_sla(inc: dict) -> dict:
    """Agrega el SLA y si está vencido (abierto más tiempo del permitido)."""
    inc["sla_minutos"] = SLA_MINUTOS[inc["severidad"]]
    fin = de_texto(inc["cerrado_en"]) if inc["cerrado_en"] else ahora_utc()
    minutos = (fin - de_texto(inc["abierto_en"])).total_seconds() / 60
    inc["minutos_abierto"] = round(minutos)
    inc["sla_vencido"] = minutos > inc["sla_minutos"]
    return inc


def _buscar(conn, incident_id: int) -> dict:
    row = conn.execute(
        "SELECT i.*, d.nombre AS equipo, d.marca, e.componente, e.estado_componente FROM incidents i "
        "LEFT JOIN devices d ON d.id = i.device_id LEFT JOIN events e ON e.id = i.event_id "
        "WHERE i.id = ?", (incident_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe el incidente {incident_id}")
    return _con_sla(dict(row))


@router.get("")
def listar(estado: str | None = None, conn: sqlite3.Connection = Depends(get_db)):
    sql = ("SELECT i.*, d.nombre AS equipo, d.marca, e.componente, e.estado_componente FROM incidents i "
           "LEFT JOIN devices d ON d.id = i.device_id LEFT JOIN events e ON e.id = i.event_id")
    params = []
    if estado == "activos":
        sql += " WHERE i.estado != 'cerrado'"
    elif estado:
        sql += " WHERE i.estado = ?"
        params.append(estado)
    rows = conn.execute(sql + " ORDER BY i.estado = 'cerrado', i.severidad, i.id DESC", params).fetchall()
    return [_con_sla(dict(r)) for r in rows]


@router.get("/propuestas")
def listar_propuestas(conn: sqlite3.Connection = Depends(get_db)):
    return propuestas(conn)


@router.get("/{incident_id}")
def ver(incident_id: int, conn: sqlite3.Connection = Depends(get_db)):
    inc = _buscar(conn, incident_id)
    evento = conn.execute("SELECT * FROM events WHERE id = ?", (inc["event_id"],)).fetchone() \
        if inc["event_id"] else None
    inc["evento"] = dict(evento) if evento else None
    inc["seguimiento"] = [dict(r) for r in conn.execute(
        "SELECT usuario, accion, detalle, fecha FROM incident_log WHERE incident_id = ? ORDER BY id",
        (incident_id,)).fetchall()]
    return inc


@router.post("", status_code=status.HTTP_201_CREATED)
def crear(datos: IncidenteNuevo, u: dict = Depends(ATIENDE), conn: sqlite3.Connection = Depends(get_db)):
    titulo, severidad, device_id = datos.titulo, datos.severidad, datos.device_id
    if datos.event_id is not None:
        ev = conn.execute("SELECT * FROM events WHERE id = ?", (datos.event_id,)).fetchone()
        if ev is None:
            raise HTTPException(404, f"No existe el evento {datos.event_id}")
        ya = conn.execute("SELECT id FROM incidents WHERE event_id = ?", (datos.event_id,)).fetchone()
        if ya:
            raise HTTPException(409, f"El evento ya tiene el incidente {ya['id']}")
        titulo = titulo or ev["mensaje"][:150]
        severidad = ev["severidad"] if severidad is None else severidad
        device_id = device_id or ev["device_id"]

    estado = "asignado" if datos.responsable else "abierto"
    cur = conn.execute(
        "INSERT INTO incidents (event_id, device_id, titulo, severidad, estado, responsable) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (datos.event_id, device_id, titulo, severidad, estado, datos.responsable))
    _registrar(conn, cur.lastrowid, u["usuario"], "creado",
               f"desde evento {datos.event_id}" if datos.event_id else "manual")
    if datos.responsable:
        _registrar(conn, cur.lastrowid, u["usuario"], "asignado", datos.responsable)
    conn.commit()
    return _buscar(conn, cur.lastrowid)


@router.patch("/{incident_id}")
def actualizar(incident_id: int, datos: IncidenteCambio, u: dict = Depends(ATIENDE), conn: sqlite3.Connection = Depends(get_db)):
    inc = _buscar(conn, incident_id)
    if inc["estado"] == "cerrado":
        raise HTTPException(409, "El incidente está cerrado; no se puede modificar")
    if datos.responsable is None and datos.estado is None and not datos.nota:
        raise HTTPException(422, "Indica responsable, estado o nota")

    responsable = datos.responsable if datos.responsable is not None else inc["responsable"]
    estado = datos.estado.value if datos.estado else inc["estado"]
    if datos.responsable and estado == "abierto":
        estado = "asignado"  # asignar un responsable avanza el estado
    if estado in ("asignado", "en_progreso") and not responsable:
        raise HTTPException(422, f"Para pasar a '{estado}' se necesita un responsable")

    conn.execute(f"UPDATE incidents SET responsable = ?, estado = ?, actualizado_en = {AHORA_UTC} "
                 "WHERE id = ?", (responsable, estado, incident_id))
    if datos.responsable is not None and datos.responsable != inc["responsable"]:
        _registrar(conn, incident_id, u["usuario"], "asignado", datos.responsable)
    if estado != inc["estado"]:
        _registrar(conn, incident_id, u["usuario"], "estado", f"{inc['estado']} -> {estado}")
    if datos.nota:
        _registrar(conn, incident_id, u["usuario"], "nota", datos.nota)
    conn.commit()
    return ver(incident_id, conn)


@router.post("/{incident_id}/cerrar")
def cerrar(incident_id: int, datos: IncidenteCierre, u: dict = Depends(ATIENDE), conn: sqlite3.Connection = Depends(get_db)):
    inc = _buscar(conn, incident_id)
    if inc["estado"] == "cerrado":
        raise HTTPException(409, "El incidente ya está cerrado")
    conn.execute(f"UPDATE incidents SET estado = 'cerrado', causa = ?, solucion = ?, "
                 f"cerrado_en = {AHORA_UTC}, actualizado_en = {AHORA_UTC} WHERE id = ?",
                 (datos.causa, datos.solucion, incident_id))
    _registrar(conn, incident_id, u["usuario"], "cerrado", f"Causa: {datos.causa} | Solución: {datos.solucion}")
    conn.commit()
    return ver(incident_id, conn)
