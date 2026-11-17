"""
security/defensa_ia.py — Defensa frente a agentes automatizados o de IA (Corte 3).

Responde a la pregunta de investigación con dos controles que se apoyan en Syslog
y en la auditoría del NOC (además de los que ya existían: logs = datos no confiables,
lista permitida de comandos, propuesta + aprobación humana y hash de evidencia):

1. CONTENER — Ráfaga de comandos en la consola.
   Una persona escribe pocos comandos por minuto; un agente automatizado puede enviar
   decenas por segundo para "probar" qué le dejan hacer. Si un usuario supera el máximo
   de comandos por minuto (Configuración › consola_max_por_minuto), su consola queda en
   pausa 5 minutos, el intento queda auditado, se crea una detección y se avisa por Telegram.

2. DETECTAR — Cambio de configuración sin aprobación (ver incidents/detecciones.py).
   Si un equipo reporta por Syslog un cambio de configuración (ej. %SYS-5-CONFIG_I) y en
   el NOC no hay un cambio APROBADO para ese equipo en los últimos minutos, alguien
   (persona o agente) cambió el equipo por fuera del flujo de aprobación: se genera la
   detección "Cambio de configuración sin aprobación".
"""

import threading
import time
from collections import deque

PAUSA_S = 300  # 5 minutos


class ControlRafaga:
    """Cuenta comandos por usuario en una ventana deslizante de 60 s."""

    def __init__(self):
        self._candado = threading.Lock()
        self._comandos: dict[str, deque] = {}
        self._pausa_hasta: dict[str, float] = {}

    def registrar(self, usuario: str, maximo: int, ahora: float | None = None) -> tuple[bool, int, int]:
        """
        Anota un comando. Devuelve (permitido, comandos_en_el_ultimo_minuto, segundos_de_pausa_restantes).
        Cuando se supera el máximo, la consola de ese usuario queda en pausa PAUSA_S segundos.
        """
        ahora = time.monotonic() if ahora is None else ahora
        clave = usuario.lower()
        with self._candado:
            if self._pausa_hasta.get(clave, 0) > ahora:
                return False, maximo, int(self._pausa_hasta[clave] - ahora)
            cola = self._comandos.setdefault(clave, deque())
            while cola and ahora - cola[0] > 60:
                cola.popleft()
            cola.append(ahora)
            if len(cola) > maximo:
                self._pausa_hasta[clave] = ahora + PAUSA_S
                cola.clear()
                return False, maximo + 1, PAUSA_S
            return True, len(cola), 0

    def reiniciar(self) -> None:
        with self._candado:
            self._comandos.clear()
            self._pausa_hasta.clear()


rafagas = ControlRafaga()
