"""Configuración compartida de pruebas: cada prueba usa una base de datos temporal."""

import os

# En las pruebas no se abre el puerto UDP real
os.environ["SYSLOG_UDP_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.database import get_connection, get_db, init_db
from app.main import app


@pytest.fixture
def client(tmp_path):
    """Cliente HTTP de prueba conectado a una BD vacía (no toca data/noc.db)."""
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    def get_test_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = get_test_db
    yield TestClient(app)
    app.dependency_overrides.clear()
