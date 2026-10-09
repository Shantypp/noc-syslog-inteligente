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

from app.collector.ingest import procesar_mensaje
from app.database import get_connection

log = logging.getLogger("noc.udp")


class ReceptorSyslog(asyncio.DatagramProtocol):
    """Se llama una vez por cada paquete UDP recibido."""

    def datagram_received(self, data: bytes, addr):
        crudo = data.decode("utf-8", errors="replace")  # bytes inválidos no rompen el receptor
        conn = get_connection()
        try:
            resultado = procesar_mensaje(conn, crudo, addr[0])
            log.info("UDP %s -> %s", addr[0], resultado["resultado"])
        except Exception:  # un mensaje malo nunca debe tumbar el colector (RNF-04)
            log.exception("Error procesando mensaje UDP de %s", addr[0])
        finally:
            conn.close()


async def iniciar_receptor_udp():
    """Abre el puerto UDP. Devuelve el transporte (para cerrarlo al apagar) o None."""
    host = os.getenv("SYSLOG_UDP_HOST", "127.0.0.1")
    puerto = int(os.getenv("SYSLOG_UDP_PORT", "5514"))
    loop = asyncio.get_running_loop()
    try:
        transporte, _ = await loop.create_datagram_endpoint(ReceptorSyslog, local_addr=(host, puerto))
    except OSError as e:
        log.error("No se pudo abrir UDP %s:%s (%s). ¿Hay otro servidor abierto?", host, puerto, e)
        return None
    log.info("Receptor Syslog escuchando en udp://%s:%s", host, puerto)
    return transporte
