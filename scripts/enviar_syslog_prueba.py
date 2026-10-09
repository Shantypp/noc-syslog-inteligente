"""
enviar_syslog_prueba.py — Simula equipos enviando Syslog por UDP al colector.

Todos los mensajes son [SIMULADOS]. Solo envía a 127.0.0.1 (este computador).

Uso (con el servidor encendido en otra terminal):
    python scripts/enviar_syslog_prueba.py              # envía data/muestras_simuladas.log
    python scripts/enviar_syslog_prueba.py --tormenta   # 500 mensajes iguales (prueba de deduplicación)
    python scripts/enviar_syslog_prueba.py --puerto 5599  # si el colector escucha en otro puerto
"""

import argparse
import socket
import time
from pathlib import Path

HOST = "127.0.0.1"
MUESTRAS = Path(__file__).resolve().parent.parent / "data" / "muestras_simuladas.log"


def enviar(lineas: list[str], pausa: float, puerto: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:  # SOCK_DGRAM = UDP
        for linea in lineas:
            s.sendto(linea.encode("utf-8"), (HOST, puerto))
            time.sleep(pausa)
    print(f"Enviados {len(lineas)} mensajes a udp://{HOST}:{puerto}")


def main() -> None:
    p = argparse.ArgumentParser(description="Generador de Syslog SIMULADO")
    p.add_argument("--tormenta", action="store_true", help="envía 500 mensajes idénticos")
    p.add_argument("--puerto", type=int, default=5514, help="puerto UDP del colector (por defecto 5514)")
    args = p.parse_args()

    if args.tormenta:
        msg = "<187>Oct  3 11:00:00 R1-NOC %LINK-3-UPDOWN: Interface Gi0/2, changed state to down"
        enviar([msg] * 500, pausa=0.001, puerto=args.puerto)
    else:
        lineas = [l for l in MUESTRAS.read_text(encoding="utf-8").splitlines()
                  if l.strip() and not l.startswith("#")]
        enviar(lineas, pausa=0.2, puerto=args.puerto)


if __name__ == "__main__":
    main()
