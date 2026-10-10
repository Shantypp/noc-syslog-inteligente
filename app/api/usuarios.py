"""
api/usuarios.py — Gestión de usuarios (solo administrador).

    GET   /api/usuarios               listar usuarios
    POST  /api/usuarios               crear usuario
    PATCH /api/usuarios/{id}          cambiar nombre, rol o activar/desactivar
    POST  /api/usuarios/{id}/clave    restablecer contraseña
    GET   /api/usuarios/accesos       últimos intentos de inicio de sesión
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.security import auth

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"], dependencies=[Depends(auth.requiere("administrador"))])


class UsuarioNuevo(BaseModel):
    usuario: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    nombre: str = Field(min_length=1, max_length=80)
    rol: str
    clave: str = Field(min_length=1, max_length=200)

    @field_validator("rol")
    @classmethod
    def rol_valido(cls, v):
        if v not in auth.ROLES:
            raise ValueError(f"rol inválido; opciones: {', '.join(auth.ROLES)}")
        return v


class UsuarioCambio(BaseModel):
    nombre: str | None = Field(None, min_length=1, max_length=80)
    rol: str | None = None
    activo: bool | None = None

    @field_validator("rol")
    @classmethod
    def rol_valido(cls, v):
        if v is not None and v not in auth.ROLES:
            raise ValueError(f"rol inválido; opciones: {', '.join(auth.ROLES)}")
        return v


class ClaveNueva(BaseModel):
    clave: str = Field(min_length=1, max_length=200)


COLUMNAS = "id, usuario, nombre, rol, activo, creado_en"


def _buscar(conn, user_id: int):
    fila = conn.execute(f"SELECT {COLUMNAS} FROM users WHERE id = ?", (user_id,)).fetchone()
    if fila is None:
        raise HTTPException(404, f"No existe el usuario {user_id}")
    return dict(fila)


def _admins_activos(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM users WHERE rol = 'administrador' AND activo = 1").fetchone()[0]


@router.get("")
def listar(conn: sqlite3.Connection = Depends(get_db)):
    return [dict(r) for r in conn.execute(f"SELECT {COLUMNAS} FROM users ORDER BY rol DESC, usuario")]


@router.get("/accesos")
def accesos(conn: sqlite3.Connection = Depends(get_db)):
    return [dict(r) for r in conn.execute("SELECT * FROM auth_log ORDER BY id DESC LIMIT 50")]


@router.post("", status_code=201)
def crear(datos: UsuarioNuevo, conn: sqlite3.Connection = Depends(get_db)):
    auth.validar_clave_nueva(datos.clave)
    try:
        cur = conn.execute("INSERT INTO users (usuario, nombre, rol, clave_hash) VALUES (?, ?, ?, ?)",
                           (datos.usuario, datos.nombre.strip(), datos.rol, auth.hash_clave(datos.clave)))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, f"Ya existe el usuario {datos.usuario}")
    return _buscar(conn, cur.lastrowid)


@router.patch("/{user_id}")
def actualizar(user_id: int, datos: UsuarioCambio, admin: dict = Depends(auth.requiere("administrador")),
               conn: sqlite3.Connection = Depends(get_db)):
    actual = _buscar(conn, user_id)
    pierde_admin = actual["rol"] == "administrador" and actual["activo"] and (
        (datos.rol is not None and datos.rol != "administrador") or datos.activo is False)
    if pierde_admin and _admins_activos(conn) <= 1:
        raise HTTPException(409, "Debe quedar al menos un administrador activo")
    if user_id == admin["id"] and datos.activo is False:
        raise HTTPException(409, "No puede desactivar su propio usuario")
    conn.execute("UPDATE users SET nombre = COALESCE(?, nombre), rol = COALESCE(?, rol), activo = COALESCE(?, activo) WHERE id = ?",
                 (datos.nombre, datos.rol, None if datos.activo is None else int(datos.activo), user_id))
    if datos.activo is False or (datos.rol and datos.rol != actual["rol"]):
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))  # aplica el cambio de inmediato
    conn.commit()
    return _buscar(conn, user_id)


@router.post("/{user_id}/clave")
def restablecer_clave(user_id: int, datos: ClaveNueva, conn: sqlite3.Connection = Depends(get_db)):
    _buscar(conn, user_id)
    auth.validar_clave_nueva(datos.clave)
    conn.execute("UPDATE users SET clave_hash = ? WHERE id = ?", (auth.hash_clave(datos.clave), user_id))
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    return {"estado": "contraseña restablecida"}
