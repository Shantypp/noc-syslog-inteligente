"""
seed.py — Carga los datos iniciales del laboratorio.

  1. Equipos de ejemplo [SIMULADOS] con IPs del rango de documentación 192.0.2.0/24
     (RFC 5737): no pertenecen a ninguna red real.
  2. Usuarios de laboratorio, uno por rol. Su contraseña inicial se lee de la
     variable NOC_CLAVE_INICIAL del archivo .env (nunca se escribe en el código).

Ejecutar:
    python -m app.seed
"""

import os

from app.database import get_connection, init_db
from app.security.auth import LARGO_MINIMO_CLAVE, hash_clave

EQUIPOS_SIMULADOS = [
    # (nombre, ip, marca, modelo, version_so, ubicacion)
    ("R1-NOC",  "192.0.2.1", "Cisco",    "Catalyst 8200 (simulado)", "IOS XE 17.9",  "Laboratorio - Rack 1"),
    ("FW-EDGE", "192.0.2.2", "Fortinet", "FortiGate 60F (simulado)", "FortiOS 7.2",  "Laboratorio - Perímetro"),
    ("SW-CORE", "192.0.2.3", "Huawei",   "S5735 (simulado)",         "VRP V200R021", "Laboratorio - Rack 2"),
]

USUARIOS_LABORATORIO = [
    # (usuario, nombre, rol)
    ("jpachon",    "Jhoan Pachón",       "administrador"),
    ("supervisor", "Supervisor de turno", "administrador"),
    ("operador",   "Operador NOC",        "operador"),
    ("consulta",   "Usuario de consulta", "lector"),
]


def cargar_semilla() -> int:
    """Inserta los equipos simulados que falten. Devuelve cuántos se insertaron."""
    init_db()
    with get_connection() as conn:
        antes = conn.total_changes
        # INSERT OR IGNORE: si la IP ya existe, la omite (se puede ejecutar varias veces)
        conn.executemany(
            "INSERT OR IGNORE INTO devices (nombre, ip, marca, modelo, version_so, ubicacion, origen) "
            "VALUES (?, ?, ?, ?, ?, ?, 'simulado')",
            EQUIPOS_SIMULADOS,
        )
        return conn.total_changes - antes


def cargar_usuarios(clave: str | None = None) -> int:
    """Crea los usuarios de laboratorio que falten. Devuelve cuántos se crearon (-1 si no hay clave)."""
    clave = clave if clave is not None else os.getenv("NOC_CLAVE_INICIAL", "")
    if len(clave) < LARGO_MINIMO_CLAVE:
        return -1
    init_db()
    with get_connection() as conn:
        antes = conn.total_changes
        conn.executemany("INSERT OR IGNORE INTO users (usuario, nombre, rol, clave_hash) VALUES (?, ?, ?, ?)",
                         [(u, n, r, hash_clave(clave)) for u, n, r in USUARIOS_LABORATORIO])
        return conn.total_changes - antes


if __name__ == "__main__":
    print(f"Equipos simulados insertados: {cargar_semilla()}")
    creados = cargar_usuarios()
    if creados < 0:
        print(f"Usuarios NO creados: defina NOC_CLAVE_INICIAL (mínimo {LARGO_MINIMO_CLAVE} caracteres) "
              "en el archivo .env y vuelva a ejecutar este comando.")
    else:
        print(f"Usuarios de laboratorio creados: {creados} "
              f"({', '.join(f'{u} [{r}]' for u, _, r in USUARIOS_LABORATORIO)}). "
              "Contraseña inicial: la de NOC_CLAVE_INICIAL en su archivo .env")
