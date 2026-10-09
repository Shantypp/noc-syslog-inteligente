"""
seed.py — Carga equipos de ejemplo [SIMULADOS] en el inventario.

Usa IPs del rango 192.0.2.0/24, reservado para documentación (RFC 5737):
no pertenecen a ninguna red real.

Ejecutar:
    python -m app.seed
"""

from app.database import get_connection, init_db

EQUIPOS_SIMULADOS = [
    # (nombre, ip, marca, modelo, version_so, ubicacion)
    ("R1-NOC",  "192.0.2.1", "Cisco",    "Catalyst 8200 (simulado)", "IOS XE 17.9",  "Laboratorio - Rack 1"),
    ("FW-EDGE", "192.0.2.2", "Fortinet", "FortiGate 60F (simulado)", "FortiOS 7.2",  "Laboratorio - Perímetro"),
    ("SW-CORE", "192.0.2.3", "Huawei",   "S5735 (simulado)",         "VRP V200R021", "Laboratorio - Rack 2"),
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


if __name__ == "__main__":
    print(f"Equipos simulados insertados: {cargar_semilla()}")
