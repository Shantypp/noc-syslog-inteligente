"""
console/simulator.py — Consola tipo PuTTY SIMULADA de solo lectura (RF-07).

No existe ninguna conexión a equipos reales. Regla: DENEGAR POR DEFECTO.

Decisiones posibles para cada comando:
  PERMITIDO      está en la lista permitida (solo lectura) -> muestra salida simulada
  PROPUESTA      comando de cambio -> NO se ejecuta; queda pendiente de revisión humana
  BLOQUEADO      destructivo, encadenado, desconocido o fuera de la lista
  NO_VERIFICADO  pertenece a otra marca o a otro modo (ej. IOS dentro de ROMMON):
                 "alucinación operacional" típica de una IA
"""

import re

LARGO_MAXIMO = 120
_PELIGROSOS = re.compile(r"[;&`$<>\n\r\\]")  # encadenar o redirigir comandos

# Palabras con las que empiezan los comandos de cada plataforma
_TODAS_LAS_PLATAFORMAS = {"show", "display", "get", "diagnose", "execute", "configure", "conf",
                          "config", "system-view", "sys", "undo", "edit", "confreg", "boot", "tftpdnld"}

SIM = "[SIMULADO] "

PERFILES = {
    "cisco_ios": {
        "nombre": "Cisco IOS XE", "marca": "Cisco", "prompt": "R1-NOC#",
        "permitidos": {
            "show version": SIM + "Cisco IOS XE Software, Version 17.09.04a\nR1-NOC uptime is 12 days, 3 hours\nSystem image file is \"bootflash:c8000be-universalk9.17.09.04a.SPA.bin\"",
            "show ip interface brief": SIM + "Interface              IP-Address      OK? Method Status   Protocol\nGigabitEthernet0/0     192.0.2.1       YES manual up       up\nGigabitEthernet0/1     unassigned      YES unset  down     down",
            "show logging": SIM + "Syslog logging: enabled\n    Trap logging: level warnings\n    Logging to 192.0.2.10 (udp port 514, audit disabled, link up)",
            "show running-config | include logging": SIM + "logging trap warnings\nlogging facility local7\nlogging source-interface GigabitEthernet0/0\nlogging host 192.0.2.10",
            "show clock": SIM + "*10:15:02.123 COT Thu Oct 8 2026",
        },
        "cambio": {"configure", "conf", "interface", "logging", "no", "ip", "hostname", "username", "copy", "write", "ntp"},
        "destructivos": ["reload", "write erase", "erase", "delete", "format", "debug all", "crypto key zeroize"],
    },
    "fortigate": {
        "nombre": "FortiGate (FortiOS)", "marca": "Fortinet", "prompt": "FW-EDGE #",
        "permitidos": {
            "get system status": SIM + "Version: FortiGate-60F v7.2.8,build1639\nHostname: FW-EDGE\nOperation Mode: NAT\nSystem time: Thu Oct  8 10:15:02 2026",
            "show log syslogd setting": SIM + "config log syslogd setting\n    set status enable\n    set server \"192.0.2.10\"\n    set facility local7\nend",
            "show log syslogd filter": SIM + "config log syslogd filter\n    set severity warning\nend",
            "get system interface physical": SIM + "== [wan1]\n  mode: static  ip: 192.0.2.2 255.255.255.0  status: up",
        },
        "cambio": {"config", "set", "unset", "edit", "next", "end", "append"},
        "destructivos": ["execute reboot", "execute factoryreset", "execute shutdown", "execute formatlogdisk", "execute restore"],
    },
    "huawei_vrp": {
        "nombre": "Huawei VRP", "marca": "Huawei", "prompt": "<SW-CORE>",
        "permitidos": {
            "display version": SIM + "Huawei Versatile Routing Platform Software\nVRP (R) software, Version 8.191 (S5735 V200R021C10)\nSW-CORE uptime is 20 days, 4 hours",
            "display info-center": SIM + "Information Center:enabled\nLog host:\n    192.0.2.10 <public>, channel number 2, channel name loghost, language English, host facility local7",
            "display interface brief": SIM + "Interface        PHY   Protocol InUti OutUti\nGE0/0/1          down  down        0%     0%\nGE0/0/2          up    up          3%     1%",
            "display clock": SIM + "2026-10-08 10:15:02 UTC-05:00",
        },
        "cambio": {"system-view", "sys", "interface", "info-center", "undo", "save", "commit", "sysname"},
        "destructivos": ["reboot", "reset saved-configuration", "delete", "format"],
    },
    "cisco_rommon": {
        "nombre": "Cisco ROMMON (modo recuperación)", "marca": "Cisco", "prompt": "rommon 1 >",
        "permitidos": {
            "set": SIM + "PS1=rommon ! >\nIP_ADDRESS=\nBOOT=bootflash:c8000be-universalk9.17.09.04a.SPA.bin",
            "confreg": SIM + "Configuration Summary\n  enabled are: console baud: 9600\n  boot: image specified by the boot system commands",
        },
        "cambio": {"confreg", "boot", "tftpdnld", "unset"},
        "destructivos": ["reset", "format", "delete"],
        "aviso_foraneo": "En ROMMON no existen los comandos de IOS (show, configure...). Primero se debe arrancar el sistema operativo.",
    },
}


def normalizar(comando: str) -> str:
    """minúsculas + espacios simples: 'SHOW   Version ' -> 'show version'"""
    return " ".join(comando.strip().lower().split())


def _palabras_nativas(p: dict) -> set:
    return ({c.split()[0] for c in p["permitidos"]} | p["cambio"]
            | {d.split()[0] for d in p["destructivos"]} | {"help", "?"})


def evaluar(perfil_id: str, comando: str) -> dict:
    """Decide qué hacer con un comando. Devuelve {decision, motivo, salida}."""
    p = PERFILES[perfil_id]
    cmd = normalizar(comando)

    def r(decision, motivo, salida=None):
        return {"decision": decision, "motivo": motivo, "salida": salida, "comando": cmd}

    if not cmd:
        return r("BLOQUEADO", "Comando vacío")
    if len(cmd) > LARGO_MAXIMO:
        return r("BLOQUEADO", f"Comando demasiado largo (máx. {LARGO_MAXIMO})")
    if _PELIGROSOS.search(cmd):
        return r("BLOQUEADO", "Caracteres de encadenamiento/redirección no permitidos (; & ` $ < > \\)")
    if cmd in ("help", "?"):
        return r("PERMITIDO", "Ayuda", "Comandos permitidos (solo lectura):\n  " + "\n  ".join(p["permitidos"]))
    if cmd in p["permitidos"]:
        return r("PERMITIDO", "En la lista permitida (solo lectura)", p["permitidos"][cmd])
    if "|" in cmd:
        return r("BLOQUEADO", "Uso de '|' fuera de la lista permitida")
    if any(cmd == d or cmd.startswith(d + " ") for d in p["destructivos"]):
        return r("BLOQUEADO", "Comando destructivo: prohibido en esta consola")

    primera = cmd.split()[0]
    if primera in _TODAS_LAS_PLATAFORMAS - _palabras_nativas(p):
        return r("NO_VERIFICADO", p.get("aviso_foraneo") or
                 f"El comando no corresponde a {p['nombre']} (otra marca o modo). No se ejecuta.")
    if primera in p["cambio"]:
        return r("PROPUESTA", "Comando de cambio: requiere revisión y aprobación humana. NO se ejecutó.")
    if any(c.split()[0] == primera for c in p["permitidos"]):
        return r("BLOQUEADO", "Consulta no incluida en la lista permitida")
    return r("BLOQUEADO", "Comando desconocido: se deniega por defecto")
