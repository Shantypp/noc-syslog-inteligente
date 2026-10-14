"""
api/events.py — Endpoints de eventos Syslog (RF-02, RF-03, RF-04).

    GET  /api/events               listar con filtros (fecha, marca, equipo, severidad, texto)
    GET  /api/events/exportar.csv  descargar los eventos filtrados (Excel)
    POST /api/events/importar      importar un archivo .log
    GET  /api/events/estadisticas  qué pasó con los mensajes (guardados, rechazados, etc.)
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.collector import ingest
from app.collector.parser import FACILITIES, SEVERIDADES
from app.database import get_db
from app.models import Marca
from app.security.auth import requiere
from app.utils import a_csv, normalizar_fecha

router = APIRouter(prefix="/api/events", tags=["eventos"], dependencies=[Depends(requiere("lector"))])

TAMANO_MAXIMO_ARCHIVO = 1_000_000  # 1 MB: evita que un archivo enorme bloquee el servidor


def _fecha(valor: str | None, campo: str) -> str | None:
    if not valor:
        return None
    try:
        return normalizar_fecha(valor)
    except ValueError:
        raise HTTPException(422, f"Fecha inválida en '{campo}': {valor}")


def enriquecer(row) -> dict:
    """Agrega los nombres legibles de severidad y facility."""
    e = dict(row)
    e["severidad_nombre"] = SEVERIDADES[e["severidad"]]
    e["facility_nombre"] = FACILITIES.get(e["facility"])
    return e


class Filtros:
    """Filtros comunes del listado y de la exportación (FastAPI los toma de la URL)."""

    def __init__(self,
                 desde: str | None = Query(None, description="Fecha/hora inicial (ISO 8601)"),
                 hasta: str | None = Query(None, description="Fecha/hora final (ISO 8601)"),
                 marca: Marca | None = None,
                 device_id: int | None = None,
                 sev_min: int = Query(0, ge=0, le=7),
                 sev_max: int = Query(7, ge=0, le=7, description="Ej. 3 = errores o más graves"),
                 solo_sospechosos: bool = False,
                 q: str | None = Query(None, max_length=100, description="Texto a buscar en el mensaje, equipo o componente"),
                 componente: str | None = Query(None, max_length=60)):
        # Cada filtro agrega una condición con parámetro "?" (nunca texto concatenado: evita inyección SQL)
        self.condiciones, self.params = ["e.severidad BETWEEN ? AND ?"], [sev_min, sev_max]
        if (d := _fecha(desde, "desde")):
            self._y("e.recibido_en >= ?", d)
        if (h := _fecha(hasta, "hasta")):
            self._y("e.recibido_en <= ?", h)
        if marca:
            self._y("d.marca = ?", marca.value)
        if device_id is not None:
            self._y("e.device_id = ?", device_id)
        if solo_sospechosos:
            self.condiciones.append("e.sospechoso = 1")
        if componente:
            self._y("e.componente = ?", componente)
        if q and q.strip():
            # % y _ son comodines en LIKE: se escapan para buscar el texto tal cual
            patron = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            self.condiciones.append("(e.mensaje LIKE ? ESCAPE '\\' OR d.nombre LIKE ? ESCAPE '\\' "
                                    "OR IFNULL(e.componente, '') LIKE ? ESCAPE '\\')")
            self.params += [patron, patron, patron]

    def _y(self, condicion: str, valor):
        self.condiciones.append(condicion)
        self.params.append(valor)

    @property
    def base(self) -> str:
        return (" FROM events e LEFT JOIN devices d ON d.id = e.device_id "
                "LEFT JOIN incidents i ON i.event_id = e.id "
                "WHERE " + " AND ".join(self.condiciones))


@router.get("")
def listar(f: Filtros = Depends(),
           limit: int = Query(100, ge=1, le=500),
           offset: int = Query(0, ge=0),
           conn: sqlite3.Connection = Depends(get_db)):
    """Devuelve {total, eventos}. `total` cuenta TODOS los que cumplen el filtro (HU-02)."""
    total = conn.execute("SELECT COUNT(*)" + f.base, f.params).fetchone()[0]
    rows = conn.execute(
        "SELECT e.*, d.nombre AS equipo, d.marca, i.id AS incident_id" + f.base +
        " ORDER BY e.id DESC LIMIT ? OFFSET ?", f.params + [limit, offset]).fetchall()
    return {"total": total, "eventos": [enriquecer(r) for r in rows]}


@router.get("/exportar.csv")
def exportar(f: Filtros = Depends(), conn: sqlite3.Connection = Depends(get_db)):
    """Descarga los eventos filtrados en CSV (máximo 50 000 filas)."""
    columnas = ["id", "recibido_en", "equipo", "marca", "severidad", "severidad_nombre", "componente",
                "estado_componente", "mensaje", "repeticiones", "sospechoso", "origen", "incident_id"]
    rows = conn.execute("SELECT e.*, d.nombre AS equipo, d.marca, i.id AS incident_id" + f.base +
                        " ORDER BY e.id DESC LIMIT 50000", f.params)
    return Response(content=a_csv(columnas, (enriquecer(r) for r in rows)), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="eventos_noc.csv"'})


@router.post("/importar", dependencies=[Depends(requiere("operador"))])
async def importar(archivo: UploadFile, conn: sqlite3.Connection = Depends(get_db)):
    """Importa un archivo de texto con un mensaje Syslog por línea."""
    contenido = await archivo.read(TAMANO_MAXIMO_ARCHIVO + 1)
    if len(contenido) > TAMANO_MAXIMO_ARCHIVO:
        raise HTTPException(413, "El archivo supera 1 MB")
    resumen = ingest.importar_texto(conn, contenido.decode("utf-8", errors="replace"))
    return {"archivo": archivo.filename, "resumen": dict(resumen)}


@router.get("/estadisticas")
def estadisticas(conn: sqlite3.Connection = Depends(get_db)):
    """Qué pasó con los mensajes recibidos: hoy y en total (evidencia de los controles de seguridad)."""
    return {"hoy": ingest.totales(conn, dias=1), "total": ingest.totales(conn),
            "desde_el_arranque": dict(ingest.estadisticas)}
