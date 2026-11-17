"""
notificaciones/telegram.py — Alertas del NOC por Telegram (Corte 3).

Qué se envía (ver notificaciones/alertas.py):
  - un equipo real deja de responder al ping (caído) o vuelve a responder;
  - el NOC pierde (o recupera) la conexión con la red de gestión;
  - una detección automática NUEVA (fuerza bruta, fuera de horario, inestable, tormenta, manipulación);
  - un evento grave (severidad igual o más grave que la configurada, 2 por defecto).

Seguridad:
  - El token y el chat_id se leen del archivo .env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID).
    Nunca están en el código, nunca se devuelven por la API (solo enmascarados) y nunca
    aparecen en los errores (se reemplazan por "***").
  - El texto de los logs es dato NO confiable: se envía como texto plano (sin Markdown/HTML),
    sin caracteres de control y recortado.
  - Anti-inundación: la misma alerta (misma clave) no se repite antes de N minutos y hay
    un máximo de mensajes por minuto. Lo que se descarta queda contado en el estado.
  - El envío se hace en segundo plano: si Telegram no responde, el NOC sigue recibiendo Syslog.
"""

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from collections import deque

log = logging.getLogger("noc.telegram")

MAX_POR_MINUTO = 20
LARGO_MAXIMO = 900
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_candado = threading.Lock()
_ultima_por_clave: dict[str, float] = {}
_envios_recientes: deque = deque()
ESTADO = {"enviadas": 0, "descartadas_por_inundacion": 0, "errores": 0, "ultimo_error": None, "ultimo_envio": None}


def credenciales() -> tuple[str, str]:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()


def configurado() -> bool:
    token, chat = credenciales()
    return bool(token and chat)


def enmascarar(valor: str) -> str:
    """Solo los primeros 4 caracteres: sirve para saber que existe, nunca muestra el valor."""
    return f"{valor[:4]}…" if valor else ""


def _sin_secretos(texto: str) -> str:
    for secreto in credenciales():
        if secreto:
            texto = texto.replace(secreto, "***")
    return texto


def limpiar(texto: str) -> str:
    return _CONTROL.sub(" ", texto or "")[:LARGO_MAXIMO]


def _enviar_http(token: str, chat_id: str, texto: str) -> None:
    """Llamada real a la API de Telegram (en las pruebas se reemplaza por una simulada)."""
    datos = json.dumps({"chat_id": chat_id, "text": texto, "disable_web_page_preview": True}).encode()
    pedido = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=datos,
                                    headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(pedido, timeout=10) as r:
        respuesta = json.loads(r.read() or b"{}")
    if not respuesta.get("ok"):
        raise RuntimeError(respuesta.get("description", "Telegram rechazó el mensaje"))


def _fallo(motivo: str) -> tuple[bool, str]:
    ESTADO["errores"] += 1
    ESTADO["ultimo_error"] = _sin_secretos(motivo)
    log.warning("Telegram: %s", ESTADO["ultimo_error"])
    return False, ESTADO["ultimo_error"]


def enviar_ahora(texto: str) -> tuple[bool, str]:
    """Envía y espera la respuesta (lo usa el botón 'Enviar mensaje de prueba')."""
    if not configurado():
        return False, "Telegram no está configurado: faltan TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en .env"
    token, chat = credenciales()
    try:
        _enviar_http(token, chat, limpiar(texto))
    except urllib.error.HTTPError as e:
        detalle = {401: "token inválido", 400: "chat_id inválido o el bot no tiene acceso al chat",
                   403: "el bot fue bloqueado o no está en el chat", 404: "token inválido",
                   429: "Telegram pidió esperar (demasiados mensajes)"}
        return _fallo(f"HTTP {e.code}: {detalle.get(e.code, 'error de Telegram')}")
    except Exception as e:  # sin red, DNS, tiempo agotado...
        return _fallo(f"{type(e).__name__}: {_sin_secretos(str(e))[:160]}")
    ESTADO["enviadas"] += 1
    ESTADO["ultimo_envio"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return True, "Mensaje enviado"


def permitido(clave: str, espera_s: float, ahora: float | None = None) -> bool:
    """Anti-inundación: la misma clave no se repite antes de 'espera_s' y hay tope por minuto."""
    ahora = time.monotonic() if ahora is None else ahora
    with _candado:
        while _envios_recientes and ahora - _envios_recientes[0] > 60:
            _envios_recientes.popleft()
        repetida = clave in _ultima_por_clave and ahora - _ultima_por_clave[clave] < espera_s
        if repetida or len(_envios_recientes) >= MAX_POR_MINUTO:
            ESTADO["descartadas_por_inundacion"] += 1
            return False
        _ultima_por_clave[clave] = ahora
        _envios_recientes.append(ahora)
        return True


def notificar(clave: str, texto: str, espera_min: int = 5, en_segundo_plano: bool = True) -> bool:
    """Encola una alerta. Devuelve True si se va a enviar (configurado y sin inundación)."""
    if not configurado() or not permitido(clave, espera_min * 60):
        return False
    texto = "NOC Syslog · " + limpiar(texto)
    if en_segundo_plano:
        threading.Thread(target=enviar_ahora, args=(texto,), daemon=True, name="telegram").start()
    else:
        enviar_ahora(texto)
    return True


def reiniciar() -> None:
    """Solo para pruebas: limpia el anti-inundación y los contadores."""
    with _candado:
        _ultima_por_clave.clear()
        _envios_recientes.clear()
    ESTADO.update(enviadas=0, descartadas_por_inundacion=0, errores=0, ultimo_error=None, ultimo_envio=None)


def estado() -> dict:
    token, chat = credenciales()
    return {"configurado": configurado(), "token": enmascarar(token), "chat_id": enmascarar(chat),
            "max_por_minuto": MAX_POR_MINUTO, **ESTADO}
