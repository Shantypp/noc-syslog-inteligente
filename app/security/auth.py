"""
security/auth.py — Inicio de sesión y control de acceso por rol (RBAC).

Roles (de menor a mayor):
  lector         ve todo; en la consola solo comandos básicos de consulta
  operador       + atiende incidentes, importa eventos, más consultas y PROPONE cambios
  administrador  + inventario, usuarios y APRUEBA (aplica) cambios propuestos por otro usuario

Decisiones de seguridad:
  - La contraseña nunca se guarda: se guarda PBKDF2-SHA256 con sal aleatoria.
  - La sesión es un token aleatorio en una cookie HttpOnly (JavaScript no puede leerla).
    En la base de datos solo se guarda la huella SHA-256 del token.
  - 5 intentos fallidos en 15 minutos bloquean temporalmente la cuenta (fuerza bruta).
  - La identidad SIEMPRE sale de la sesión, nunca de lo que envía el navegador.
"""

import hashlib
import hmac
import secrets
import sqlite3
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status

from app.database import get_db
from app.utils import a_texto, ahora_utc, hace

ROLES = ("lector", "operador", "administrador")
NIVEL = {rol: i for i, rol in enumerate(ROLES)}
NOMBRE_ROL = {"lector": "Lector", "operador": "Operador", "administrador": "Administrador"}

COOKIE = "noc_sesion"
DURACION_SESION = timedelta(hours=8)
MAX_INTENTOS = 5
VENTANA_BLOQUEO_MIN = 15
ITERACIONES = 200_000
LARGO_MINIMO_CLAVE = 8


# ---------------------------------------------------------------- contraseñas

def hash_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${sal.hex()}${derivada.hex()}"


def verificar_clave(clave: str, guardada: str) -> bool:
    try:
        _, iteraciones, sal, esperado = guardada.split("$")
        derivada = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), bytes.fromhex(sal), int(iteraciones))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derivada.hex(), esperado)  # comparación en tiempo constante


def validar_clave_nueva(clave: str) -> None:
    if len(clave) < LARGO_MINIMO_CLAVE:
        raise HTTPException(422, f"La contraseña debe tener al menos {LARGO_MINIMO_CLAVE} caracteres")


# ---------------------------------------------------------------- sesiones

def _huella(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def intentos_fallidos_recientes(conn: sqlite3.Connection, usuario: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM auth_log WHERE usuario = ? COLLATE NOCASE AND exito = 0 AND fecha >= ?",
        (usuario, hace(minutos=VENTANA_BLOQUEO_MIN))).fetchone()[0]


def registrar_intento(conn, usuario: str, ip: str | None, exito: bool, detalle: str) -> None:
    conn.execute("INSERT INTO auth_log (usuario, ip, exito, detalle) VALUES (?, ?, ?, ?)",
                 (usuario[:60], ip, int(exito), detalle))
    conn.commit()


def autenticar(conn: sqlite3.Connection, usuario: str, clave: str, ip: str | None) -> dict:
    """Verifica usuario y contraseña. Devuelve el usuario o lanza 401/429."""
    if intentos_fallidos_recientes(conn, usuario) >= MAX_INTENTOS:
        registrar_intento(conn, usuario, ip, False, "bloqueado por intentos fallidos")
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Cuenta bloqueada temporalmente: {MAX_INTENTOS} intentos fallidos. "
                            f"Intente de nuevo en {VENTANA_BLOQUEO_MIN} minutos.")
    fila = conn.execute("SELECT * FROM users WHERE usuario = ? COLLATE NOCASE", (usuario,)).fetchone()
    # Mismo mensaje si el usuario no existe o la contraseña es incorrecta (no revela qué falló)
    if fila is None or not verificar_clave(clave, fila["clave_hash"]):
        registrar_intento(conn, usuario, ip, False, "credenciales incorrectas")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")
    if not fila["activo"]:
        registrar_intento(conn, usuario, ip, False, "usuario desactivado")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "El usuario está desactivado")
    registrar_intento(conn, fila["usuario"], ip, True, "inicio de sesión")
    return _publico(fila)


def crear_sesion(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM sessions WHERE expira_en < ?", (a_texto(ahora_utc()),))  # limpieza
    conn.execute("INSERT INTO sessions (token_hash, user_id, expira_en) VALUES (?, ?, ?)",
                 (_huella(token), user_id, a_texto(ahora_utc() + DURACION_SESION)))
    conn.commit()
    return token


def cerrar_sesion(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_huella(token),))
        conn.commit()


def _publico(fila) -> dict:
    return {"id": fila["id"], "usuario": fila["usuario"], "nombre": fila["nombre"],
            "rol": fila["rol"], "rol_nombre": NOMBRE_ROL[fila["rol"]]}


# ---------------------------------------------------------------- dependencias de FastAPI

def usuario_actual(request: Request, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Usuario de la sesión. Responde 401 si no hay sesión válida."""
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Debe iniciar sesión")
    fila = conn.execute(
        "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ? AND s.expira_en > ? AND u.activo = 1",
        (_huella(token), a_texto(ahora_utc()))).fetchone()
    if fila is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión venció o no es válida. Inicie sesión de nuevo.")
    return _publico(fila)


def requiere(rol_minimo: str):
    """Dependencia que exige al menos ese rol. Responde 403 si no alcanza."""
    def verificar(usuario: dict = Depends(usuario_actual)) -> dict:
        if NIVEL[usuario["rol"]] < NIVEL[rol_minimo]:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Su rol ({NOMBRE_ROL[usuario['rol']]}) no permite esta acción. "
                                f"Requiere: {NOMBRE_ROL[rol_minimo]}.")
        return usuario
    return verificar


def tiene_rol(usuario: dict, rol_minimo: str) -> bool:
    return NIVEL[usuario["rol"]] >= NIVEL[rol_minimo]
