"""
configgen/templates.py — Generador de configuraciones Syslog comentadas (RF-06, HU-04).

Genera TEXTO para que un administrador autorizado lo revise. Nunca se aplica
automáticamente a un equipo. Cada entrada se valida para que no se puedan
"inyectar" comandos extra dentro de la plantilla.
"""

import ipaddress
import re
from enum import Enum


class Fabricante(str, Enum):
    cisco = "cisco"
    fortinet = "fortinet"
    huawei = "huawei"


# Nombre del nivel en la sintaxis de cada fabricante + severidad numérica equivalente
UMBRALES = {
    "informational": {"cisco": "informational", "fortinet": "information", "huawei": "informational", "sev": 6},
    "warnings":      {"cisco": "warnings",      "fortinet": "warning",     "huawei": "warning",       "sev": 4},
    "errors":        {"cisco": "errors",        "fortinet": "error",       "huawei": "error",         "sev": 3},
    "critical":      {"cisco": "critical",      "fortinet": "critical",    "huawei": "critical",      "sev": 2},
}
FACILITIES = [f"local{i}" for i in range(8)]
_INTERFAZ = re.compile(r"^[A-Za-z][A-Za-z0-9/.\-]{0,40}$")  # ej. GigabitEthernet0/0, Loopback0

ADVERTENCIA = ("La sintaxis varía según modelo y versión (IOS/IOS XE, FortiOS, VRP). Antes de aplicar: "
               "identifique equipo y versión, consulte la documentación oficial, haga backup, pruebe en "
               "laboratorio, obtenga autorización y tenga un plan de reversa.")

INFO = {
    Fabricante.cisco: {"nombre": "Cisco IOS / IOS XE", "comentario": "!",
                       "version": "show version",
                       "verificar": ["show logging", "show running-config | include logging"],
                       "doc": "Cisco IOS XE 17.x — System Management Configuration Guide: System Message Logging"},
    Fabricante.fortinet: {"nombre": "Fortinet FortiGate (FortiOS)", "comentario": "#",
                          "version": "get system status",
                          "verificar": ["show log syslogd setting", "show log syslogd filter"],
                          "doc": "FortiOS CLI Reference — log syslogd setting / log syslogd filter"},
    Fabricante.huawei: {"nombre": "Huawei VRP", "comentario": "#",
                        "version": "display version",
                        "verificar": ["display info-center", "display current-configuration | include info-center"],
                        "doc": "Huawei Command Reference — info-center loghost"},
}


class ParametroInvalido(ValueError):
    pass


def _validar(ip: str, umbral: str, puerto: int, facility: str, interfaz: str | None) -> str:
    try:
        ip = str(ipaddress.ip_address(ip.strip()))
    except ValueError:
        raise ParametroInvalido(f"IP del colector inválida: {ip!r}")
    if umbral not in UMBRALES:
        raise ParametroInvalido(f"Umbral inválido. Opciones: {', '.join(UMBRALES)}")
    if not 1 <= puerto <= 65535:
        raise ParametroInvalido("Puerto fuera de rango (1-65535)")
    if facility not in FACILITIES:
        raise ParametroInvalido(f"Facility inválida. Opciones: {', '.join(FACILITIES)}")
    if interfaz and not _INTERFAZ.match(interfaz):
        raise ParametroInvalido("Nombre de interfaz inválido (solo letras, números, / . -)")
    return ip


def _cisco(ip, nivel, puerto, facility, interfaz):
    return [
        ("configure terminal", "Entrar al modo de configuración global"),
        ("service timestamps log datetime msec localtime show-timezone", "Sello de tiempo con ms y zona horaria: permite correlacionar eventos"),
        ("! ntp server <IP-NTP-AUTORIZADO>", "Sincronizar la hora con NTP (requisito de la política Syslog)"),
        ("logging on", "Habilitar el registro de eventos"),
        (f"logging host {ip} transport udp port {puerto}", "Enviar los eventos al colector NOC"),
        (f"logging trap {nivel}", "Enviar solo este nivel y los más graves"),
        (f"logging facility {facility}", "Facility con la que el colector clasifica los mensajes"),
        (f"logging source-interface {interfaz}" if interfaz else "! logging source-interface <INTERFAZ>",
         "IP de origen fija = la registrada en el inventario (lista permitida del NOC)"),
        ("end", "Salir del modo de configuración"),
        ("write memory", "Guardar SOLO después de verificar y con backup previo"),
    ], [f"no logging host {ip}", "write memory"]


def _fortinet(ip, nivel, puerto, facility, interfaz):
    return [
        ("config log syslogd setting", "Configuración del servidor Syslog remoto"),
        ("    set status enable", "Activar el envío"),
        (f'    set server "{ip}"', "IP del colector NOC"),
        ("    set mode udp", "Transporte (algunas versiones ofrecen reliable/TCP o TLS)"),
        (f"    set port {puerto}", "Puerto del colector"),
        (f"    set facility {facility}", "Facility para clasificar"),
        (f'    set source-ip-interface "{interfaz}"' if interfaz else "    # set source-ip <IP-ORIGEN>",
         "Origen fijo = el registrado en el inventario (según versión de FortiOS)"),
        ("end", "Aplicar el bloque (FortiOS guarda automáticamente)"),
        ("config log syslogd filter", "Filtro de severidad"),
        (f"    set severity {nivel}", "Este nivel y los más graves"),
        ("end", "Aplicar"),
    ], ["config log syslogd setting", "    set status disable", "end"]


def _huawei(ip, nivel, puerto, facility, interfaz):
    loghost = f"info-center loghost {ip}" + ("" if puerto == 514 else f" port {puerto}") + f" facility {facility}"
    return [
        ("system-view", "Entrar a la vista de sistema"),
        ("info-center enable", "Habilitar el centro de información (logs)"),
        (loghost, "Definir el colector NOC" + ("" if puerto == 514 else " (verifique soporte de 'port' en su VRP)")),
        (f"info-center loghost source {interfaz}" if interfaz else "# info-center loghost source <INTERFAZ>",
         "Interfaz de origen fija = la del inventario"),
        (f"info-center source default channel loghost log level {nivel}", "Nivel enviado al canal loghost"),
        ("info-center timestamp log date", "Sello de fecha en los mensajes"),
        ("return", "Volver a la vista de usuario"),
        ("save", "Guardar (algunas plataformas requieren 'commit' antes)"),
    ], ["system-view", f"undo info-center loghost {ip}", "return", "save"]


_GENERADORES = {Fabricante.cisco: _cisco, Fabricante.fortinet: _fortinet, Fabricante.huawei: _huawei}


def generar(fabricante: Fabricante, ip: str, umbral: str = "warnings", puerto: int = 514,
            facility: str = "local7", interfaz: str | None = None) -> dict:
    """Devuelve la plantilla comentada, comandos de verificación, reversa y advertencia."""
    ip = _validar(ip, umbral, puerto, facility, interfaz)
    info = INFO[fabricante]
    c = info["comentario"]
    nivel = UMBRALES[umbral][fabricante.value]
    lineas, reversa = _GENERADORES[fabricante](ip, nivel, puerto, facility, interfaz)

    texto = [
        f"{c} ==== Syslog -> NOC | {info['nombre']} | generado por NOC Syslog Inteligente ====",
        f"{c} ADVERTENCIA: {ADVERTENCIA}",
        f"{c} Paso 0 - identificar versión:  {info['version']}",
        f"{c} Colector {ip}:{puerto}/udp · umbral {umbral} (severidad 0-{UMBRALES[umbral]['sev']}) · {facility}",
        c,
    ]
    for comando, explicacion in lineas:
        texto.append(f"{c} {explicacion}")
        texto.append(comando)

    return {
        "fabricante": fabricante.value,
        "nombre": info["nombre"],
        "parametros": {"ip": ip, "umbral": umbral, "nivel": nivel, "puerto": puerto,
                       "facility": facility, "interfaz": interfaz},
        "plantilla": "\n".join(texto),
        "identificar_version": info["version"],
        "verificacion": info["verificar"],
        "reversa": reversa,
        "advertencia": ADVERTENCIA,
        "documentacion": info["doc"],
    }
