"""
api/console.py — Consola simulada y auditoría (RF-07, RF-08, HU-05).

    GET  /api/console/perfiles              perfiles disponibles y su lista permitida
    POST /api/console/ejecutar              evaluar un comando (siempre queda auditado)
    GET  /api/auditoria                     consultar la bitácora
    GET  /api/auditoria/exportar            descargar la bitácora en CSV
    GET  /api/auditoria/integridad          verificar que nadie alteró los registros
    POST /api/auditoria/{id}/aprobar        revisión humana de una propuesta
    POST /api/auditoria/{id}/rechazar
"""

import csv
import io
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.console import audit
from app.console.simulator import PERFILES, evaluar, rol_minimo
from app.database import get_db
from app.security.auth import NOMBRE_ROL, requiere

router = APIRouter(tags=["consola y auditoría"], dependencies=[Depends(requiere("lector"))])


class Comando(BaseModel):
    perfil: str = Field(examples=["cisco_ios"])
    comando: str = Field(max_length=500, examples=["show version"])
    device_id: int | None = None


class Revision(BaseModel):
    motivo: str | None = Field(None, max_length=300)


@router.get("/api/console/perfiles")
def perfiles():
    return [{"id": k, "nombre": p["nombre"], "marca": p["marca"], "prompt": p["prompt"],
             "permitidos": [{"comando": c, "rol_minimo": rol_minimo(c), "rol_nombre": NOMBRE_ROL[rol_minimo(c)]}
                            for c in p["permitidos"]]} for k, p in PERFILES.items()]


@router.post("/api/console/ejecutar")
def ejecutar(datos: Comando, u: dict = Depends(requiere("lector")), conn: sqlite3.Connection = Depends(get_db)):
    if datos.perfil not in PERFILES:
        raise HTTPException(422, f"Perfil desconocido. Opciones: {', '.join(PERFILES)}")
    if datos.device_id is not None and not conn.execute(
            "SELECT 1 FROM devices WHERE id = ?", (datos.device_id,)).fetchone():
        raise HTTPException(404, "El equipo no existe en el inventario")

    r = evaluar(datos.perfil, datos.comando, u["rol"])  # la decisión depende del rol de la sesión
    resultado = {"PERMITIDO": "Salida simulada mostrada",
                 "PROPUESTA": audit.PENDIENTE}.get(r["decision"], r["motivo"])
    # Se audita lo que el usuario escribió (recortado), no la versión normalizada
    r["audit_id"] = audit.registrar(conn, u["usuario"], datos.device_id,
                                    datos.comando.strip()[:200], r["decision"], resultado)
    return r


@router.get("/api/auditoria")
def listar(decision: str | None = None, pendientes: bool = False, limit: int = 200,
           conn: sqlite3.Connection = Depends(get_db)):
    sql = ("SELECT a.*, d.nombre AS equipo FROM command_audit a "
           "LEFT JOIN devices d ON d.id = a.device_id WHERE 1=1")
    params: list = []
    if decision:
        sql += " AND a.decision = ?"
        params.append(decision)
    if pendientes:
        sql += " AND a.resultado = ?"
        params.append(audit.PENDIENTE)
    rows = conn.execute(sql + " ORDER BY a.id DESC LIMIT ?", params + [min(limit, 1000)]).fetchall()
    return [dict(r) for r in rows]


def _celda_segura(valor) -> str:
    """Evita 'inyección de fórmulas' si el CSV se abre en Excel (=, +, -, @ al inicio)."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@") else texto


@router.get("/api/auditoria/exportar")
def exportar(conn: sqlite3.Connection = Depends(get_db)):
    columnas = ["id", "fecha", "usuario", "equipo", "comando", "decision", "aprobado_por", "resultado", "hash_evidencia"]
    salida = io.StringIO()
    w = csv.writer(salida)
    w.writerow(columnas)
    for r in conn.execute("SELECT a.*, d.nombre AS equipo FROM command_audit a "
                          "LEFT JOIN devices d ON d.id = a.device_id ORDER BY a.id"):
        w.writerow([_celda_segura(r[c]) for c in columnas])
    return Response(content="﻿" + salida.getvalue(),  # BOM: Excel muestra bien las tildes
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="auditoria_noc.csv"'})


@router.get("/api/auditoria/integridad")
def integridad(conn: sqlite3.Connection = Depends(get_db)):
    return audit.verificar_integridad(conn)


def _decidir(audit_id: int, datos: Revision, aprobar: bool, revisor: dict, conn) -> dict:
    try:
        return audit.decidir(conn, audit_id, revisor["usuario"], aprobar, datos.motivo or "")
    except audit.DecisionInvalida as e:
        raise HTTPException(409, str(e))


@router.post("/api/auditoria/{audit_id}/aprobar")
def aprobar(audit_id: int, datos: Revision, u: dict = Depends(requiere("administrador")),
            conn: sqlite3.Connection = Depends(get_db)):
    """Solo un administrador aplica cambios, y nunca los que él mismo propuso."""
    return _decidir(audit_id, datos, True, u, conn)


@router.post("/api/auditoria/{audit_id}/rechazar")
def rechazar(audit_id: int, datos: Revision, u: dict = Depends(requiere("administrador")),
             conn: sqlite3.Connection = Depends(get_db)):
    return _decidir(audit_id, datos, False, u, conn)
