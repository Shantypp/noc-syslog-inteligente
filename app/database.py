"""
database.py — Conexión a SQLite y creación del modelo de datos.

Tablas (ver docs / vault "Modelo de datos"):
  - devices        : inventario de equipos de red
  - events         : mensajes Syslog recibidos o importados
  - incidents      : incidentes abiertos a partir de eventos
  - incident_log   : seguimiento de cada incidente (quién cambió qué y cuándo)
  - command_audit  : bitácora de comandos de la consola (quién, qué, cuándo, resultado)
  - users          : usuarios con rol (lector, operador, administrador) y contraseña cifrada
  - sessions       : sesiones activas (solo se guarda la huella del token, nunca el token)
  - auth_log       : intentos de inicio de sesión (exitosos y fallidos)

Ejecutar directamente para crear la base de datos:
    python -m app.database
"""

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

# Carga las variables del archivo .env (si existe). Así la configuración
# y cualquier secreto quedan FUERA del código (requisito RNF-01).
load_dotenv()

# Ruta del archivo .db; si no está en .env se usa el valor por defecto.
DB_PATH = os.getenv("NOC_DB_PATH", "data/noc.db")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Abre una conexión a SQLite lista para usar."""
    path = db_path or DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)  # crea data/ si no existe
    # check_same_thread=False: FastAPI puede atender una misma petición en hilos
    # distintos. Es seguro porque cada petición abre y cierra su propia conexión.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row            # cada fila se comporta como un diccionario
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite no valida llaves foráneas si no se activa
    return conn


# Esquema SQL. "IF NOT EXISTS" permite ejecutar init_db() varias veces sin error.
# Las fechas se guardan como texto ISO 8601 en UTC (ej. 2026-10-03T15:04:05Z).
SCHEMA = """
-- ---------------------------------------------------------------
-- Inventario de dispositivos (RF-01)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS devices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,
    ip              TEXT    NOT NULL UNIQUE,      -- una IP no puede repetirse
    marca           TEXT    NOT NULL CHECK (marca IN ('Cisco', 'Fortinet', 'Huawei')),
    modelo          TEXT,
    version_so      TEXT,
    ubicacion       TEXT,
    estado          TEXT    NOT NULL DEFAULT 'activo'
                    CHECK (estado IN ('activo', 'inactivo', 'sin_comunicacion')),
    origen          TEXT    NOT NULL DEFAULT 'simulado'
                    CHECK (origen IN ('simulado', 'real')),  -- datos simulados SIEMPRE rotulados
    actualizado_en  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ---------------------------------------------------------------
-- Eventos Syslog (RF-02, RF-03)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id         INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    recibido_en       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),  -- hora del colector
    timestamp_equipo  TEXT,                       -- hora que trae el mensaje (puede venir mal)
    ip_origen         TEXT    NOT NULL,
    hostname          TEXT,
    facility          INTEGER CHECK (facility BETWEEN 0 AND 23),
    severidad         INTEGER NOT NULL CHECK (severidad BETWEEN 0 AND 7),
    mensaje           TEXT    NOT NULL,           -- texto limpio que se muestra
    mensaje_crudo     TEXT    NOT NULL,           -- texto exacto recibido (evidencia)
    hash_dedup        TEXT,                       -- huella para agrupar repetidos
    repeticiones      INTEGER NOT NULL DEFAULT 1,
    sospechoso        INTEGER NOT NULL DEFAULT 0 CHECK (sospechoso IN (0, 1)),  -- posible inyección
    origen            TEXT    NOT NULL DEFAULT 'simulado' CHECK (origen IN ('simulado', 'real')),
    componente        TEXT,                       -- parte del equipo afectada (ej. GigabitEthernet0/1)
    estado_componente TEXT                        -- estado de esa parte (Caído, Arriba, Falla...)
);

-- Índices: aceleran los filtros del dashboard (RNF-07 rendimiento)
CREATE INDEX IF NOT EXISTS idx_events_severidad   ON events(severidad);
CREATE INDEX IF NOT EXISTS idx_events_recibido_en ON events(recibido_en);
CREATE INDEX IF NOT EXISTS idx_events_device      ON events(device_id);
CREATE INDEX IF NOT EXISTS idx_events_hash        ON events(hash_dedup);

-- ---------------------------------------------------------------
-- Incidentes (RF-05)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incidents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        INTEGER REFERENCES events(id)  ON DELETE SET NULL,  -- evento que lo originó
    device_id       INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    titulo          TEXT    NOT NULL,
    severidad       INTEGER NOT NULL CHECK (severidad BETWEEN 0 AND 7),
    estado          TEXT    NOT NULL DEFAULT 'abierto'
                    CHECK (estado IN ('abierto', 'asignado', 'en_progreso', 'cerrado')),
    responsable     TEXT,
    abierto_en      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    actualizado_en  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    cerrado_en      TEXT,
    causa           TEXT,
    solucion        TEXT
);

-- ---------------------------------------------------------------
-- Seguimiento de incidentes: cada cambio queda con fecha y actor (RNF-03)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incident_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id     INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    usuario         TEXT    NOT NULL,
    accion          TEXT    NOT NULL,             -- creado, asignado, estado, nota, cerrado
    detalle         TEXT,
    fecha           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_incident_log ON incident_log(incident_id);

-- ---------------------------------------------------------------
-- Auditoría de comandos (RF-07, RF-08) — trazabilidad completa
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS command_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario         TEXT    NOT NULL,
    device_id       INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    comando         TEXT    NOT NULL,
    decision        TEXT    NOT NULL
                    CHECK (decision IN ('PERMITIDO', 'BLOQUEADO', 'PROPUESTA', 'NO_VERIFICADO')),
    aprobado_por    TEXT,                         -- quién aprobó (si aplica)
    resultado       TEXT,
    hash_evidencia  TEXT,                         -- SHA-256 para detectar alteraciones
    fecha           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- ---------------------------------------------------------------
-- Usuarios, roles y sesiones (control de acceso por rol: RBAC)
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    nombre          TEXT    NOT NULL,
    rol             TEXT    NOT NULL CHECK (rol IN ('lector', 'operador', 'administrador')),
    clave_hash      TEXT    NOT NULL,             -- PBKDF2-SHA256 con sal: nunca la contraseña
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash      TEXT    PRIMARY KEY,          -- SHA-256 del token de la cookie
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    creada_en       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    expira_en       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario         TEXT    NOT NULL,
    ip              TEXT,
    exito           INTEGER NOT NULL CHECK (exito IN (0, 1)),
    detalle         TEXT,
    fecha           TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_auth_log ON auth_log(usuario, fecha);
"""

# Columnas agregadas después de la primera versión. Si la base de datos ya existía,
# se añaden sin borrar datos (migración simple).
COLUMNAS_NUEVAS = {"events": ["componente TEXT", "estado_componente TEXT"]}


def init_db(db_path: str | None = None) -> None:
    """Crea todas las tablas e índices si todavía no existen."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        for tabla, columnas in COLUMNAS_NUEVAS.items():
            existentes = {r["name"] for r in conn.execute(f"PRAGMA table_info({tabla})")}
            for col in columnas:
                if col.split()[0] not in existentes:
                    conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_componente ON events(device_id, componente)")


def get_db():
    """
    Dependencia de FastAPI: entrega una conexión a cada petición y la cierra al terminar.
    Las pruebas la reemplazan por una base de datos temporal.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def list_tables(db_path: str | None = None) -> list[str]:
    """Devuelve los nombres de las tablas creadas (útil para verificar)."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return [r["name"] for r in rows]


# Permite ejecutar: python -m app.database
if __name__ == "__main__":
    init_db()
    print(f"Base de datos lista en: {DB_PATH}")
    print("Tablas:", ", ".join(list_tables()))
