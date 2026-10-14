"""
api/auth.py — Inicio y cierre de sesión.

    GET  /api/auth/estado         ¿falta la configuración inicial? (no hay usuarios)
    POST /api/auth/configuracion-inicial   crea el primer administrador e inicia su sesión
    POST /api/auth/login          usuario + contraseña -> cookie de sesión
    POST /api/auth/logout         cierra la sesión
    GET  /api/auth/yo             usuario de la sesión y su rol
    POST /api/auth/cambiar-clave  el usuario cambia su propia contraseña
"""

import ipaddress
import os
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.database import get_db
from app.security import auth

router = APIRouter(prefix="/api/auth", tags=["sesión"])

# En producción con HTTPS debe ser 1 para que la cookie solo viaje cifrada
COOKIE_SEGURA = os.getenv("NOC_COOKIE_SEGURA", "0") == "1"


class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=60)
    clave: str = Field(min_length=1, max_length=200)


class CambioClave(BaseModel):
    actual: str = Field(min_length=1, max_length=200)
    nueva: str = Field(min_length=1, max_length=200)


class PrimerAdministrador(BaseModel):
    usuario: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    nombre: str = Field(min_length=3, max_length=80)
    clave: str = Field(min_length=1, max_length=200)


def _abrir_sesion(conn, response: Response, user_id: int) -> None:
    token = auth.crear_sesion(conn, user_id)
    response.set_cookie(auth.COOKIE, token, httponly=True, samesite="strict", secure=COOKIE_SEGURA,
                        max_age=int(auth.DURACION_SESION.total_seconds()), path="/")


@router.get("/estado")
def estado(conn: sqlite3.Connection = Depends(get_db)):
    """¿El sistema ya tiene usuarios? Si no, la interfaz muestra la configuración inicial."""
    return {"requiere_configuracion": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0}


@router.post("/configuracion-inicial", status_code=201)
def configuracion_inicial(datos: PrimerAdministrador, request: Request, response: Response,
                          conn: sqlite3.Connection = Depends(get_db)):
    """
    Crea el PRIMER administrador. Solo funciona mientras no exista ningún usuario
    y solo desde este mismo computador (nadie en la red puede adueñarse del sistema).
    """
    ip = request.client.host if request.client else None
    try:
        es_remoto = ip is not None and not ipaddress.ip_address(ip).is_loopback
    except ValueError:  # el cliente de pruebas no tiene IP
        es_remoto = False
    if es_remoto:
        raise HTTPException(403, "La configuración inicial solo se puede hacer desde el computador donde corre el NOC")
    auth.validar_clave_nueva(datos.clave)
    # Un solo INSERT condicionado: si dos personas lo intentan a la vez, solo una lo logra
    cur = conn.execute(
        "INSERT INTO users (usuario, nombre, rol, clave_hash) SELECT ?, ?, 'administrador', ? "
        "WHERE NOT EXISTS (SELECT 1 FROM users)",
        (datos.usuario.strip(), datos.nombre.strip(), auth.hash_clave(datos.clave)))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(409, "El sistema ya fue configurado. Inicie sesión con su usuario.")
    auth.registrar_intento(conn, datos.usuario, ip, True, "configuración inicial: primer administrador")
    _abrir_sesion(conn, response, cur.lastrowid)
    return auth._publico(conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.post("/login")
def login(datos: Credenciales, request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    ip = request.client.host if request.client else None
    usuario = auth.autenticar(conn, datos.usuario.strip(), datos.clave, ip)
    _abrir_sesion(conn, response, usuario["id"])
    return usuario


@router.post("/logout")
def logout(request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    auth.cerrar_sesion(conn, request.cookies.get(auth.COOKIE))
    response.delete_cookie(auth.COOKIE, path="/")
    return {"estado": "sesión cerrada"}


@router.get("/yo")
def yo(usuario: dict = Depends(auth.usuario_actual)):
    return usuario


@router.post("/cambiar-clave")
def cambiar_clave(datos: CambioClave, usuario: dict = Depends(auth.usuario_actual),
                  conn: sqlite3.Connection = Depends(get_db)):
    fila = conn.execute("SELECT clave_hash FROM users WHERE id = ?", (usuario["id"],)).fetchone()
    if not auth.verificar_clave(datos.actual, fila["clave_hash"]):
        raise HTTPException(400, "La contraseña actual no es correcta")
    auth.validar_clave_nueva(datos.nueva)
    conn.execute("UPDATE users SET clave_hash = ? WHERE id = ?", (auth.hash_clave(datos.nueva), usuario["id"]))
    conn.commit()
    return {"estado": "contraseña actualizada"}
