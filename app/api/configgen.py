"""
api/configgen.py — Generador de configuraciones Syslog (RF-06, HU-04).

    GET /api/configgen/opciones   fabricantes, umbrales y facilities disponibles
    GET /api/configgen            genera la plantilla comentada
"""

from fastapi import APIRouter, HTTPException, Query

from app.configgen.templates import (FACILITIES, INFO, UMBRALES, Fabricante,
                                     ParametroInvalido, generar)

router = APIRouter(prefix="/api/configgen", tags=["configuraciones"])


@router.get("/opciones")
def opciones():
    return {
        "fabricantes": [{"id": f.value, "nombre": INFO[f]["nombre"]} for f in Fabricante],
        "umbrales": [{"id": k, "severidad_max": v["sev"]} for k, v in UMBRALES.items()],
        "facilities": FACILITIES,
    }


@router.get("")
def generar_plantilla(fabricante: Fabricante,
                      ip: str = Query(..., examples=["192.0.2.10"], description="IP del colector NOC"),
                      umbral: str = "warnings", puerto: int = 514, facility: str = "local7",
                      interfaz: str | None = None):
    try:
        return generar(fabricante, ip, umbral, puerto, facility, interfaz or None)
    except ParametroInvalido as e:
        raise HTTPException(422, str(e))
