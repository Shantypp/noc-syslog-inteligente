"""
collector/udp_server.py — Receptor Syslog por UDP (RF-02).

Escucha en SYSLOG_UDP_HOST:SYSLOG_UDP_PORT (por defecto 127.0.0.1:5514).
  - 127.0.0.1 = solo acepta mensajes de este mismo computador (laboratorio seguro).
  - 5514 en lugar de 514 = no requiere permisos de administrador.

Recuerda: UDP no confirma la entrega ni cifra el contenido (RFC 5426).
"""

import asyncio
import logging
import os
import socket

from app.collector.ingest import procesar_mensaje
from app.database import get_connection

log = logging.getLogger("noc.udp")

# Estado del receptor (lo muestra la pantalla Configuración y la Ayuda)
ESTADO = {"activo": False, "host": None, "puerto": None, "error": None}
BUFER_UDP = 8 * 1024 * 1024  # 8 MB


class ReceptorSyslog(asyncio.DatagramProtocol):
    """
    Se llama una vez por cada paquete UDP recibido.

    Corte 3 (prueba de carga): se reutiliza UNA conexión a la base de datos para todos los
    mensajes (antes se abría y cerraba una por mensaje) y el registro por mensaje pasó a nivel
    DEBUG. Con eso el colector procesa más mensajes por segundo y pierde menos por UDP.
    """

    def __init__(self):
        self.conn = None

    def connection_made(self, transport):
        self.conn = get_connection()

    def connection_lost(self, exc):
        if self.conn is not None:
            self.conn.close()

    def datagram_received(self, data: bytes, addr):
        crudo = data.decode("utf-8", errors="replace")  # bytes inválidos no rompen el receptor
        try:
            resultado = procesar_mensaje(self.conn, crudo, addr[0])
            log.debug("UDP %s -> %s", addr[0], resultado["resultado"])
        except Exception:  # un mensaje malo nunca debe tumbar el colector (RNF-04)
            log.exception("Error procesando mensaje UDP de %s", addr[0])
            try:
                self.conn.rollback()
            except Exception:
                self.conn = get_connection()


async def iniciar_receptor_udp():
    """Abre el puerto UDP. Devuelve el transporte (para cerrarlo al apagar) o None."""
    host = os.getenv("SYSLOG_UDP_HOST", "127.0.0.1")
    puerto = int(os.getenv("SYSLOG_UDP_PORT", "5514"))
    ESTADO.update(host=host, puerto=puerto, activo=False, error=None)
    loop = asyncio.get_running_loop()
    try:
        transporte, _ = await loop.create_datagram_endpoint(ReceptorSyslog, local_addr=(host, puerto))
    except OSError as e:
        log.error("No se pudo abrir UDP %s:%s (%s). ¿Hay otro servidor abierto?", host, puerto, e)
        ESTADO["error"] = f"No se pudo abrir el puerto UDP {puerto}: ¿hay otro servidor del NOC abierto?"
        return None
    # Búfer de recepción grande: en una ráfaga los paquetes esperan en el búfer en vez de perderse
    try:
        transporte.get_extra_info("socket").setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFER_UDP)
    except OSError:
        log.warning("No se pudo ampliar el búfer UDP; se usa el del sistema")
    log.info("Receptor Syslog escuchando en udp://%s:%s", host, puerto)
    ESTADO["activo"] = True
    return transporte
