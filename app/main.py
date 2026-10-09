"""
main.py — Punto de entrada de la API.

Ejecutar:
    uvicorn app.main:app --reload
y abrir http://127.0.0.1:8000/docs
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import devices, events
from app.collector.udp_server import iniciar_receptor_udp
from app.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Lo que pasa al encender y al apagar el servidor."""
    init_db()  # crea las tablas si no existen
    transporte = None
    if os.getenv("SYSLOG_UDP_ENABLED", "1") == "1":
        transporte = await iniciar_receptor_udp()
    yield
    if transporte:
        transporte.close()


app = FastAPI(
    title="NOC Syslog Inteligente",
    description="API del NOC académico. Datos SIMULADOS.",
    version="0.1.0",
    lifespan=ciclo_de_vida,
)

# Registro de módulos de la API
app.include_router(devices.router)
app.include_router(events.router)


@app.get("/api/health", tags=["sistema"])
def health():
    """Comprobación rápida de que la API está viva."""
    return {"estado": "ok", "version": app.version}
