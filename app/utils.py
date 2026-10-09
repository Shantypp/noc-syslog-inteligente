"""utils.py — Funciones pequeñas compartidas por varios módulos."""

from datetime import datetime, timedelta, timezone

FORMATO_FECHA = "%Y-%m-%dT%H:%M:%SZ"  # mismo formato que usa SQLite en las tablas


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def a_texto(fecha: datetime) -> str:
    """datetime -> '2026-10-08T15:04:05Z' (UTC)."""
    return fecha.astimezone(timezone.utc).strftime(FORMATO_FECHA)


def hace(minutos: float = 0, horas: float = 0) -> str:
    """Fecha en texto de hace X minutos/horas (para comparar en SQL)."""
    return a_texto(ahora_utc() - timedelta(minutes=minutos, hours=horas))


def normalizar_fecha(valor: str) -> str:
    """
    Acepta '2026-10-08', '2026-10-08T05:00:00.000Z' o con zona horaria
    y lo convierte al formato de la base de datos. Lanza ValueError si es inválida.
    """
    fecha = datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
    if fecha.tzinfo is None:  # sin zona horaria se asume UTC
        fecha = fecha.replace(tzinfo=timezone.utc)
    return a_texto(fecha)


def de_texto(valor: str) -> datetime:
    return datetime.strptime(valor, FORMATO_FECHA).replace(tzinfo=timezone.utc)
