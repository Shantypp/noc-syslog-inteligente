"""
usuarios.py — Administración de usuarios desde la terminal (por si se pierde el acceso).

    python -m app.usuarios listar
    python -m app.usuarios crear USUARIO --nombre "Nombre" --rol administrador
    python -m app.usuarios clave USUARIO          # pide la nueva contraseña sin mostrarla

La contraseña se pide con getpass: no queda en el historial de la terminal.
"""

import argparse
import getpass
import sys

from app.database import get_connection, init_db
from app.security.auth import LARGO_MINIMO_CLAVE, ROLES, hash_clave


def pedir_clave() -> str:
    clave = getpass.getpass("Nueva contraseña: ")
    if len(clave) < LARGO_MINIMO_CLAVE:
        sys.exit(f"La contraseña debe tener al menos {LARGO_MINIMO_CLAVE} caracteres")
    if clave != getpass.getpass("Repita la contraseña: "):
        sys.exit("Las contraseñas no coinciden")
    return clave


def main() -> None:
    p = argparse.ArgumentParser(description="Usuarios del NOC")
    sub = p.add_subparsers(dest="accion", required=True)
    sub.add_parser("listar")
    c = sub.add_parser("crear")
    c.add_argument("usuario")
    c.add_argument("--nombre", required=True)
    c.add_argument("--rol", choices=ROLES, required=True)
    k = sub.add_parser("clave")
    k.add_argument("usuario")
    a = p.parse_args()

    init_db()
    with get_connection() as conn:
        if a.accion == "listar":
            for r in conn.execute("SELECT usuario, nombre, rol, activo FROM users ORDER BY usuario"):
                print(f"{r['usuario']:<14} {r['rol']:<14} {'activo' if r['activo'] else 'inactivo':<9} {r['nombre']}")
        elif a.accion == "crear":
            conn.execute("INSERT INTO users (usuario, nombre, rol, clave_hash) VALUES (?, ?, ?, ?)",
                         (a.usuario, a.nombre, a.rol, hash_clave(pedir_clave())))
            print(f"Usuario {a.usuario} creado con rol {a.rol}")
        elif a.accion == "clave":
            if not conn.execute("SELECT 1 FROM users WHERE usuario = ? COLLATE NOCASE", (a.usuario,)).fetchone():
                sys.exit(f"No existe el usuario {a.usuario}")
            conn.execute("UPDATE users SET clave_hash = ? WHERE usuario = ? COLLATE NOCASE", (hash_clave(pedir_clave()), a.usuario))
            conn.execute("DELETE FROM sessions WHERE user_id = (SELECT id FROM users WHERE usuario = ? COLLATE NOCASE)", (a.usuario,))
            conn.execute("DELETE FROM auth_log WHERE usuario = ? COLLATE NOCASE AND exito = 0", (a.usuario,))  # desbloquea
            print(f"Contraseña de {a.usuario} actualizada")


if __name__ == "__main__":
    main()
