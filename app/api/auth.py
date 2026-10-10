"""
api/auth.py — Inicio y cierre de sesión.

    POST /api/auth/login          usuario + contraseña -> cookie de sesión
    POST /api/auth/logout         cierra la sesión
    GET  /api/auth/yo             usuario de la sesión y su rol
    POST /api/auth/cambiar-clave  el usuario cambia su propia contraseña
"""

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


@router.post("/login")
def login(datos: Credenciales, request: Request, response: Response, conn: sqlite3.Connection = Depends(get_db)):
    ip = request.client.host if request.client else None
    usuario = auth.autenticar(conn, datos.usuario.strip(), datos.clave, ip)
    token = auth.crear_sesion(conn, usuario["id"])
    response.set_cookie(auth.COOKIE, token, httponly=True, samesite="strict", secure=COOKIE_SEGURA,
                        max_age=int(auth.DURACION_SESION.total_seconds()), path="/")
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
