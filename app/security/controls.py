"""
security/controls.py — Controles de seguridad sobre los mensajes entrantes.

REGLA DE ORO: los logs son DATOS NO CONFIABLES, nunca instrucciones.
Nada de lo que llega en un mensaje se ejecuta, se evalúa ni se envía a una IA
como orden. Estos controles lo protegen:

  - limpiar_mensaje : quita caracteres de control y limita el tamaño
  - es_sospechoso   : detecta intentos de inyección de prompt / XSS (solo marca)
  - huella_dedup    : huella para agrupar mensajes repetidos (tormentas)
  - LimitadorTasa   : máximo de mensajes por minuto (rate limit)
"""

import hashlib
import re
import threading
import time

LARGO_MAXIMO = 2048

# Patrones típicos de inyección de prompt indirecta o de código.
# Si aparecen, el evento se GUARDA (es evidencia) pero se marca como sospechoso.
_PATRONES_SOSPECHOSOS = [
    r"ignor[ae]\w*\s+(todas\s+)?(las\s+)?(pol[ií]ticas|instrucciones|reglas)",
    r"ignore\s+(all\s+)?(previous|prior|the)?\s*(instructions|rules|policies)",
    r"\bejecut[ae]\w*\b",
    r"\bexecute\b",
    r"system\s*prompt",
    r"\b(eres|act[uú]a como|you are now)\b",
    r"<\s*script",
    r"javascript:",
]
_SOSPECHOSO = re.compile("|".join(_PATRONES_SOSPECHOSOS), re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def limpiar_mensaje(texto: str) -> str:
    """Elimina caracteres de control (pueden romper la terminal o la UI) y recorta."""
    return _CONTROL.sub(" ", texto)[:LARGO_MAXIMO]


def es_sospechoso(texto: str) -> bool:
    """True si el texto parece intentar dar órdenes (a una IA o al navegador)."""
    return bool(_SOSPECHOSO.search(texto))


def huella_dedup(device_id: int, severidad: int, mensaje: str) -> str:
    """Misma huella = mismo equipo + misma severidad + mismo texto."""
    base = f"{device_id}|{severidad}|{mensaje.strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class LimitadorTasa:
    """Permite como máximo `limite` mensajes por cada ventana de 60 segundos."""

    def __init__(self, limite: int):
        self.limite = limite
        self._inicio = time.monotonic()
        self._contador = 0
        self._lock = threading.Lock()

    def permitir(self) -> bool:
        with self._lock:
            ahora = time.monotonic()
            if ahora - self._inicio >= 60:  # empieza un minuto nuevo
                self._inicio, self._contador = ahora, 0
            if self._contador >= self.limite:
                return False
            self._contador += 1
            return True
