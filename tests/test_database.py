"""Pruebas de la Fase 1: el modelo de datos se crea correctamente."""

import sqlite3

import pytest

from app.database import get_connection, init_db, list_tables


@pytest.fixture
def db(tmp_path):
    """Crea una base de datos temporal para cada prueba (no toca data/noc.db)."""
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def test_se_crean_todas_las_tablas(db):
    assert list_tables(db) == ["auth_log", "command_audit", "devices", "events", "incident_log", "incidents", "sessions", "users"]


def test_init_db_se_puede_ejecutar_dos_veces(db):
    init_db(db)  # no debe fallar
    assert len(list_tables(db)) == 8


def test_ip_duplicada_es_rechazada(db):
    with get_connection(db) as conn:
        conn.execute("INSERT INTO devices (nombre, ip, marca) VALUES ('R1', '192.0.2.1', 'Cisco')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO devices (nombre, ip, marca) VALUES ('R2', '192.0.2.1', 'Cisco')")


def test_marca_no_permitida_es_rechazada(db):
    with get_connection(db) as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO devices (nombre, ip, marca) VALUES ('X', '192.0.2.9', 'Juniper')")


def test_severidad_fuera_de_rango_es_rechazada(db):
    with get_connection(db) as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO events (ip_origen, severidad, mensaje, mensaje_crudo) "
            "VALUES ('192.0.2.1', 9, 'x', 'x')"
        )


def test_migracion_agrega_columnas_a_una_bd_antigua(tmp_path):
    """Una base creada con la versión anterior (sin 'componente') se actualiza sin perder datos."""
    import re
    from app.database import SCHEMA
    # El esquema de la versión anterior es el actual sin las dos columnas nuevas
    esquema_anterior = re.sub(r",\n\s+componente\s+TEXT,[^\n]*\n\s+estado_componente\s+TEXT[^\n]*", "", SCHEMA)
    assert "componente" not in esquema_anterior
    path = str(tmp_path / "antigua.db")
    conn = get_connection(path)
    conn.executescript(esquema_anterior)
    conn.execute("INSERT INTO events (ip_origen, severidad, mensaje, mensaje_crudo) VALUES ('192.0.2.1', 3, 'evento viejo', 'x')")
    conn.commit()
    conn.close()
    init_db(path)
    conn = get_connection(path)
    columnas = {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
    assert {"componente", "estado_componente"} <= columnas
    assert conn.execute("SELECT mensaje FROM events").fetchone()[0] == "evento viejo"
