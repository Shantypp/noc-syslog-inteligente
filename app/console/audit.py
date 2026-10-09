"""
console/audit.py — Auditoría de comandos con integridad (RF-08, HU-05).

Cada registro guarda un hash SHA-256 de su contenido. Si alguien modifica
la fila directamente en la base de datos, el hash ya no coincide y la
verificación de integridad lo detecta.
"""

import hashlib
import sqlite3

from app.utils import a_texto, ahora_utc

PENDIENTE = "PENDIENTE_APROBACION"


def calcular_hash(fila: dict) -> str:
    base = "|".join(str(fila.get(k) or "") for k in
                    ("usuario", "device_id", "comando", "decision", "aprobado_por", "resultado", "fecha"))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def registrar(conn: sqlite3.Connection, usuario: str, device_id: int | None, comando: str,
              decision: str, resultado: str) -> int:
    fila = {"usuario": usuario, "device_id": device_id, "comando": comando, "decision": decision,
            "aprobado_por": None, "resultado": resultado, "fecha": a_texto(ahora_utc())}
    cur = conn.execute(
        "INSERT INTO command_audit (usuario, device_id, comando, decision, aprobado_por, resultado, "
        "hash_evidencia, fecha) VALUES (:usuario, :device_id, :comando, :decision, :aprobado_por, "
        ":resultado, :hash, :fecha)", {**fila, "hash": calcular_hash(fila)})
    conn.commit()
    return cur.lastrowid


class DecisionInvalida(Exception):
    """La propuesta no existe, ya fue decidida o el aprobador no es válido."""


def decidir(conn: sqlite3.Connection, audit_id: int, revisor: str, aprobar: bool, motivo: str = "") -> dict:
    """
    Revisión humana de una PROPUESTA (pasos 4-8 del flujo seguro).
    Separación de funciones: quien propone NO puede aprobar su propia propuesta.
    """
    row = conn.execute("SELECT * FROM command_audit WHERE id = ?", (audit_id,)).fetchone()
    if row is None:
        raise DecisionInvalida(f"No existe el registro {audit_id}")
    fila = dict(row)
    if fila["decision"] != "PROPUESTA" or fila["resultado"] != PENDIENTE:
        raise DecisionInvalida("Solo se pueden decidir propuestas pendientes")
    if revisor.strip().lower() == fila["usuario"].strip().lower():
        raise DecisionInvalida("Separación de funciones: quien propone no puede aprobar su propia propuesta")

    fila["aprobado_por"] = revisor
    fila["resultado"] = ("APROBADA · ejecución SIMULADA: en el MVP no se envía nada a ningún equipo"
                         if aprobar else f"RECHAZADA · {motivo or 'sin motivo'}")
    conn.execute("UPDATE command_audit SET aprobado_por = ?, resultado = ?, hash_evidencia = ? WHERE id = ?",
                 (fila["aprobado_por"], fila["resultado"], calcular_hash(fila), audit_id))
    conn.commit()
    return fila


def verificar_integridad(conn: sqlite3.Connection) -> dict:
    """Recalcula el hash de cada registro y reporta los que fueron alterados."""
    alterados, total = [], 0
    for row in conn.execute("SELECT * FROM command_audit ORDER BY id"):
        total += 1
        if calcular_hash(dict(row)) != row["hash_evidencia"]:
            alterados.append(row["id"])
    return {"total": total, "integros": total - len(alterados), "alterados": alterados}
