"""
main.py — Punto de entrada de la aplicación.

Ejecutar:
    uvicorn app.main:app --reload
y abrir:
    http://127.0.0.1:8000        -> interfaz web del NOC
    http://127.0.0.1:8000/docs   -> documentación interactiva de la API
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import (auth, configgen, console, dashboard, detecciones, devices, events, incidents, puertos,
                     security, sistema, usuarios)
from app import VERSION, mantenimiento
from app.collector import monitoreo
from app.collector.udp_server import iniciar_receptor_udp
from app.database import get_connection, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

CARPETA_WEB = Path(__file__).parent / "web"


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Lo que pasa al encender y al apagar el servidor."""
    init_db()  # crea las tablas si no existen (y agrega columnas nuevas sin borrar datos)
    with get_connection() as conn:  # retención: borra eventos más viejos que los días configurados
        purga = mantenimiento.purgar_antiguos(conn)
    if purga["eventos_eliminados"]:
        logging.getLogger("noc").info("Retención: %s eventos antiguos eliminados", purga["eventos_eliminados"])
    transporte = None
    if os.getenv("SYSLOG_UDP_ENABLED", "1") == "1":
        transporte = await iniciar_receptor_udp()
    # Ping periódico a los equipos reales: saber si están vivos aunque no envíen mensajes
    tarea_ping = asyncio.create_task(monitoreo.ciclo()) if os.getenv("NOC_MONITOREO", "1") == "1" else None
    yield
    if tarea_ping:
        tarea_ping.cancel()
    if transporte:
        transporte.close()


app = FastAPI(
    title="NOC Syslog Inteligente",
    description="API del NOC académico. Datos SIMULADOS.",
    version=VERSION,
    lifespan=ciclo_de_vida,
)

# Registro de módulos de la API
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(devices.router)
app.include_router(events.router)
app.include_router(puertos.router)
app.include_router(incidents.router)
app.include_router(dashboard.router)
app.include_router(configgen.router)
app.include_router(console.router)
app.include_router(security.router)
app.include_router(detecciones.router)
app.include_router(sistema.router)


@app.middleware("http")
async def sin_cache_en_la_interfaz(request, call_next):
    """El navegador revalida HTML/JS/CSS en cada carga: evita ver una versión vieja tras actualizar."""
    respuesta = await call_next(request)
    if not request.url.path.startswith("/api"):
        respuesta.headers["Cache-Control"] = "no-cache"
    return respuesta


@app.get("/api/health", tags=["sistema"])
def health():
    """Comprobación rápida de que la API está viva."""
    return {"estado": "ok", "version": app.version}


# La interfaz web (HTML/CSS/JS) se sirve desde la raíz. Va AL FINAL para no tapar las rutas /api.
app.mount("/", StaticFiles(directory=CARPETA_WEB, html=True), name="web")
