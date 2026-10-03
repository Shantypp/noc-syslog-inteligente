"""
models.py — Esquemas de datos (Pydantic).

Pydantic valida AUTOMÁTICAMENTE lo que llega a la API:
si un dato no cumple las reglas, FastAPI responde 422 sin tocar la base de datos.
"""

import ipaddress
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Marca(str, Enum):
    """Fabricantes soportados por el NOC."""
    cisco = "Cisco"
    fortinet = "Fortinet"
    huawei = "Huawei"


class EstadoDevice(str, Enum):
    activo = "activo"
    inactivo = "inactivo"
    sin_comunicacion = "sin_comunicacion"


class Origen(str, Enum):
    """Regla del curso: los datos simulados deben estar identificados."""
    simulado = "simulado"
    real = "real"


class DeviceIn(BaseModel):
    """Datos que el usuario envía para crear o editar un equipo."""
    nombre: str = Field(min_length=1, max_length=60, examples=["R1-NOC"])
    ip: str = Field(examples=["192.0.2.1"])
    marca: Marca
    modelo: str | None = Field(default=None, max_length=60)
    version_so: str | None = Field(default=None, max_length=60)
    ubicacion: str | None = Field(default=None, max_length=100)
    estado: EstadoDevice = EstadoDevice.activo
    origen: Origen = Origen.simulado

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("el nombre no puede estar vacío")
        return v

    @field_validator("ip")
    @classmethod
    def validar_ip(cls, v: str) -> str:
        # El módulo ipaddress de Python rechaza IPs inválidas como 999.1.1.1
        try:
            return str(ipaddress.ip_address(v.strip()))
        except ValueError:
            raise ValueError(f"'{v}' no es una dirección IP válida")


class Device(DeviceIn):
    """Equipo tal como se devuelve desde la base de datos."""
    id: int
    actualizado_en: str
