"""Configuración compartida de pruebas: cada prueba usa una base de datos temporal."""

import os

# En las pruebas no se abre el puerto UDP real
os.environ["SYSLOG_UDP_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.database import get_connection, get_db, init_db
from app.main import app
from app.security.auth import hash_clave

# Usuarios de PRUEBA (solo existen dentro de la base temporal de cada prueba)
CLAVE_PRUEBA = "clave-de-prueba-123"
USUARIOS_PRUEBA = [("admin1", "Admin Uno", "administrador"), ("admin2", "Admin Dos", "administrador"),
                   ("oper", "Operador", "operador"), ("lect", "Lector", "lector")]


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    with get_connection(path) as conn:
        clave = hash_clave(CLAVE_PRUEBA)
        conn.executemany("INSERT INTO users (usuario, nombre, rol, clave_hash) VALUES (?, ?, ?, ?)",
                         [(u, n, r, clave) for u, n, r in USUARIOS_PRUEBA])
    return path


@pytest.fixture
def sin_sesion(db_path):
    """Cliente HTTP conectado a la BD temporal, sin iniciar sesión."""
    def get_test_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = get_test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def como(sin_sesion):
    """Devuelve un cliente con sesión iniciada como el usuario indicado: como("oper")."""
    def iniciar(usuario: str) -> TestClient:
        c = TestClient(app)
        r = c.post("/api/auth/login", json={"usuario": usuario, "clave": CLAVE_PRUEBA})
        assert r.status_code == 200, r.text
        return c
    return iniciar


@pytest.fixture
def client(como):
    """Cliente con sesión de administrador (la mayoría de las pruebas)."""
    return como("admin1")
