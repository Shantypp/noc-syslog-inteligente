"""
main.py — Punto de entrada de la API.

Ejecutar:
    uvicorn app.main:app --reload
y abrir http://127.0.0.1:8000/docs
"""

from fastapi import FastAPI

from app.database import init_db

app = FastAPI(
    title="NOC Syslog Inteligente",
    description="API del NOC académico. Datos SIMULADOS.",
    version="0.1.0",
)

# Crea las tablas al arrancar (si ya existen, no hace nada).
init_db()


@app.get("/api/health", tags=["sistema"])
def health():
    """Comprobación rápida de que la API está viva."""
    return {"estado": "ok", "version": app.version}
