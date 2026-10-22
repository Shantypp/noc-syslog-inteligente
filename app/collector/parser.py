"""
collector/parser.py — Descompone un mensaje Syslog en sus partes (RF-03).

Formatos soportados:
  RFC 5424:   <165>1 2026-10-03T10:17:00Z FW-EDGE fortigate - - - mensaje
  RFC 3164:   <187>Oct  3 10:15:02 R1-NOC %LINK-3-UPDOWN: Interface ... down
  Cisco IOS:  <187>62: *Oct 21 17:19:22.986 COT: %LINK-3-UPDOWN: Interface ... down
              (lo que envía un Cisco real: número de secuencia, hora con milisegundos
               y zona horaria; con "logging origin-id hostname" también el nombre)
  Huawei:     <188>Oct 16 2026 10:15:02 SW-CORE %%01IFNET/4/LINK_STATE(l)[0]:...
  FortiGate:  <189>date=2026-10-16 time=10:15:02 devname="FGT60F" ... msg="..."

La clave es el PRI, el número entre < >:
    facility  = PRI // 8   (división entera)
    severidad = PRI %  8   (residuo)
"""

import re

SEVERIDADES = ["emergency", "alert", "critical", "error",
               "warning", "notice", "informational", "debug"]

FACILITIES = {
    0: "kern", 1: "user", 2: "mail", 3: "daemon", 4: "auth", 5: "syslog",
    6: "lpr", 7: "news", 8: "uucp", 9: "cron", 10: "authpriv", 11: "ftp",
    12: "ntp", 13: "security", 14: "console", 15: "clock",
    **{16 + i: f"local{i}" for i in range(8)},
}

# <PRI>resto   (PRI va de 0 a 191 = facility 23 * 8 + severidad 7)
_PRI = re.compile(r"^<(\d{1,3})>(.*)$", re.DOTALL)
# 1 TIMESTAMP HOSTNAME APP-NAME PROCID MSGID STRUCTURED-DATA MSG
_RFC5424 = re.compile(r"^1 (\S+) (\S+) (\S+) (\S+) (\S+) (-|(?:\[[^\]]*\])+) ?(.*)$", re.DOTALL)
# Mmm dd [aaaa] hh:mm:ss HOSTNAME MSG   (el año opcional lo usa Huawei)
_RFC3164 = re.compile(r"^([A-Z][a-z]{2} {1,2}\d{1,2}(?: \d{4})? \d{2}:\d{2}:\d{2}) (\S+) (.*)$", re.DOTALL)
# Cisco IOS / IOS XE: [secuencia: ][hostname: ][*|.]fecha u hora de encendido: %FACILIDAD-SEV-NOMBRE: texto
#   "*" = el equipo no tiene la hora sincronizada; "." = la perdió (NTP)
_FECHA_CISCO = r"[A-Z][a-z]{2} {1,2}\d{1,2}(?: \d{4})? \d{1,2}:\d{2}:\d{2}(?:\.\d{1,6})?(?: [A-Za-z]{2,5})?"
_UPTIME_CISCO = r"\d{1,2}:\d{2}:\d{2}(?:\.\d{1,6})?|\d+[ywd]\d+[wdh]"
_CISCO = re.compile(
    r"^(?:\d+: )?(?:(?P<host>[A-Za-z][\w.\-]*): )?"
    rf"[*.]?(?P<ts>{_FECHA_CISCO}|{_UPTIME_CISCO}): (?P<msg>%.*)$", re.DOTALL)
# FortiGate (formato propio clave=valor)
_FORTI = re.compile(r'^date=(\S+) time=(\S+) .*?devname="?([^" ]+)"?', re.DOTALL)


class MensajeInvalido(ValueError):
    """El texto recibido no es un mensaje Syslog válido."""


def parse_syslog(crudo: str) -> dict:
    """
    Convierte el texto crudo en un diccionario con:
    facility, severidad, timestamp_equipo, hostname, mensaje, formato.
    Lanza MensajeInvalido si no tiene un PRI válido.
    """
    texto = crudo.strip()
    m = _PRI.match(texto)
    if not m:
        raise MensajeInvalido("falta el PRI <N> al inicio del mensaje")

    pri = int(m.group(1))
    if pri > 191:
        raise MensajeInvalido(f"PRI fuera de rango: {pri}")
    resto = m.group(2)

    resultado = {
        "facility": pri // 8,
        "severidad": pri % 8,
        "timestamp_equipo": None,
        "hostname": None,
        "mensaje": resto.strip(),
        "formato": "desconocido",
    }

    if m5424 := _RFC5424.match(resto):
        resultado.update(
            timestamp_equipo=m5424.group(1),
            hostname=m5424.group(2),
            mensaje=m5424.group(7).strip(),
            formato="RFC5424",
        )
    elif mcisco := _CISCO.match(resto):
        # Se quita el prefijo (secuencia y hora): el mensaje queda limpio y los repetidos
        # se pueden agrupar (cada mensaje Cisco trae un número de secuencia distinto).
        resultado.update(
            timestamp_equipo=mcisco.group("ts"),
            hostname=mcisco.group("host"),
            mensaje=mcisco.group("msg").strip(),
            formato="Cisco IOS",
        )
    elif mforti := _FORTI.match(resto):
        resultado.update(
            timestamp_equipo=f"{mforti.group(1)} {mforti.group(2)}",
            hostname=mforti.group(3),
            formato="FortiGate",
        )
    elif m3164 := _RFC3164.match(resto):
        resultado.update(
            timestamp_equipo=m3164.group(1),
            hostname=m3164.group(2),
            mensaje=m3164.group(3).strip(),
            formato="RFC3164",
        )
    # Si no coincide ningún formato se conserva el texto completo: no se pierde el evento.
    return resultado
