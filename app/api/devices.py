"""
api/devices.py — Endpoints del inventario de dispositivos (RF-01).

    GET    /api/devices        listar (filtros opcionales ?marca=&estado=)
    GET    /api/devices/{id}   ver uno
    POST   /api/devices        crear
    PUT    /api/devices/{id}   editar (actualiza la fecha de actualización)
    DELETE /api/devices/{id}   eliminar
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.database import get_db
from app.models import Device, DeviceIn, EstadoDevice, Marca

router = APIRouter(prefix="/api/devices", tags=["inventario"])

# Hora actual en UTC con el mismo formato que usa la tabla.
AHORA_UTC = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


def _buscar(conn: sqlite3.Connection, device_id: int) -> Device:
    """Devuelve el equipo o responde 404 si no existe."""
    row = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No existe el equipo con id {device_id}")
    return Device(**dict(row))


def _ip_duplicada(ip: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un equipo con la IP {ip}")


@router.get("", response_model=list[Device])
def listar(marca: Marca | None = None, estado: EstadoDevice | None = None,
           conn: sqlite3.Connection = Depends(get_db)):
    # Se arma la consulta con parámetros "?" (nunca concatenando texto del usuario)
    # para evitar inyección SQL.
    sql, params = "SELECT * FROM devices WHERE 1=1", []
    if marca:
        sql += " AND marca = ?"
        params.append(marca.value)
    if estado:
        sql += " AND estado = ?"
        params.append(estado.value)
    rows = conn.execute(sql + " ORDER BY nombre", params).fetchall()
    return [Device(**dict(r)) for r in rows]


@router.get("/{device_id}", response_model=Device)
def ver(device_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return _buscar(conn, device_id)


@router.post("", response_model=Device, status_code=status.HTTP_201_CREATED)
def crear(datos: DeviceIn, conn: sqlite3.Connection = Depends(get_db)):
    try:
        cur = conn.execute(
            "INSERT INTO devices (nombre, ip, marca, modelo, version_so, ubicacion, estado, origen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (datos.nombre, datos.ip, datos.marca.value, datos.modelo, datos.version_so,
             datos.ubicacion, datos.estado.value, datos.origen.value),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise _ip_duplicada(datos.ip)
    return _buscar(conn, cur.lastrowid)


@router.put("/{device_id}", response_model=Device)
def editar(device_id: int, datos: DeviceIn, conn: sqlite3.Connection = Depends(get_db)):
    _buscar(conn, device_id)  # 404 si no existe
    try:
        conn.execute(
            "UPDATE devices SET nombre = ?, ip = ?, marca = ?, modelo = ?, version_so = ?, "
            f"ubicacion = ?, estado = ?, origen = ?, actualizado_en = {AHORA_UTC} WHERE id = ?",
            (datos.nombre, datos.ip, datos.marca.value, datos.modelo, datos.version_so,
             datos.ubicacion, datos.estado.value, datos.origen.value, device_id),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise _ip_duplicada(datos.ip)
    return _buscar(conn, device_id)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(device_id: int, conn: sqlite3.Connection = Depends(get_db)):
    _buscar(conn, device_id)  # 404 si no existe
    conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    conn.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
