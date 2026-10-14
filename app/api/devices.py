"""
api/devices.py — Endpoints del inventario de dispositivos (RF-01).

    GET    /api/devices        listar (filtros opcionales ?marca=&estado=)
    GET    /api/devices/{id}   ver uno
    GET    /api/devices/{id}/resumen   ficha completa del equipo
    POST   /api/devices        crear
    PUT    /api/devices/{id}   editar (actualiza la fecha de actualización)
    DELETE /api/devices/{id}   eliminar
"""

import sqlite3
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.database import get_db
from app.models import Device, DeviceIn, EstadoDevice, Marca
from app.security.auth import requiere
from app.utils import ahora_utc, hace

router = APIRouter(prefix="/api/devices", tags=["inventario"], dependencies=[Depends(requiere("lector"))])
SOLO_ADMIN = [Depends(requiere("administrador"))]  # modificar el inventario

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


@router.get("/{device_id}/resumen")
def resumen(device_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """
    Ficha del equipo: TODO lo de un equipo en una sola respuesta (estado, partes con problema,
    incidentes, detecciones, eventos recientes y actividad de las últimas 24 horas).
    """
    from app.api.dashboard import estado_equipos  # import local: evita importación circular
    from app.api.events import enriquecer
    from app.api.puertos import estado_componentes
    from app.incidents.detecciones import listar as listar_detecciones

    _buscar(conn, device_id)
    equipo = next(e for e in estado_equipos(conn) if e["id"] == device_id)
    por_hora = {r[0]: r[1] for r in conn.execute(
        "SELECT strftime('%Y-%m-%dT%H', recibido_en), SUM(repeticiones) FROM events "
        "WHERE device_id = ? AND recibido_en >= ? GROUP BY 1", (device_id, hace(horas=24)))}
    ahora = ahora_utc()
    horas = [(ahora - timedelta(hours=h)).strftime("%Y-%m-%dT%H") for h in range(23, -1, -1)]
    return {
        "equipo": equipo,
        "componentes": estado_componentes(conn, device_id),
        "incidentes": [dict(r) for r in conn.execute(
            "SELECT i.id, i.titulo, i.severidad, i.estado, i.responsable, i.abierto_en, i.cerrado_en, i.recuperado_en "
            "FROM incidents i WHERE i.device_id = ? ORDER BY i.estado = 'cerrado', i.id DESC LIMIT 20", (device_id,))],
        "detecciones": listar_detecciones(conn, None, device_id, limite=20),
        "eventos": [enriquecer(r) for r in conn.execute(
            "SELECT e.*, d.nombre AS equipo, d.marca FROM events e LEFT JOIN devices d ON d.id = e.device_id "
            "WHERE e.device_id = ? ORDER BY e.id DESC LIMIT 25", (device_id,))],
        "actividad_24h": [{"inicio": f"{h}:00:00Z", "eventos": por_hora.get(h, 0)} for h in horas],
        "por_severidad": [r[0] for r in conn.execute(
            "SELECT COUNT(e.id) FROM (SELECT 0 AS s UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 "
            "UNION SELECT 5 UNION SELECT 6 UNION SELECT 7) n LEFT JOIN events e ON e.severidad = n.s "
            "AND e.device_id = ? AND e.recibido_en >= ? GROUP BY n.s ORDER BY n.s", (device_id, hace(horas=24)))],
    }


@router.post("", response_model=Device, status_code=status.HTTP_201_CREATED, dependencies=SOLO_ADMIN)
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


@router.put("/{device_id}", response_model=Device, dependencies=SOLO_ADMIN)
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


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=SOLO_ADMIN)
def eliminar(device_id: int, conn: sqlite3.Connection = Depends(get_db)):
    _buscar(conn, device_id)  # 404 si no existe
    conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    conn.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
