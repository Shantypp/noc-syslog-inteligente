"""
collector/componentes.py — Identifica QUÉ PARTE del equipo genera el problema.

A partir del texto del log reconoce el componente afectado y su estado:
    "Interface GigabitEthernet0/1, changed state to down"  -> GigabitEthernet0/1 · Caído
    "interface GE0/0/1 has entered the DOWN state"         -> GE0/0/1 · Caído
    "Power supply 2 failed"                                -> Fuente de poder 2 · Falla
    "Temperature sensor 1 reached critical threshold"     -> Sensor de temperatura 1 · Crítico
    "IPsec tunnel SEDE-NORTE up"                          -> Túnel VPN SEDE-NORTE · Arriba

El texto del log NO es confiable: el nombre extraído se limita a caracteres
seguros y a 60 caracteres antes de guardarlo.
"""

import re

# Estados que significan "hay un problema"
ESTADOS_PROBLEMA = {"Caído", "Falla", "Crítico", "Conmutación", "Advertencia"}

_SEGURO = re.compile(r"[^\w/.:\- ]")
_ABREVIATURAS = {"gi": "GigabitEthernet", "fa": "FastEthernet", "te": "TenGigabitEthernet", "eth": "Ethernet"}

# (expresión, tipo de componente, función que arma (nombre, estado))
_REGLAS = [
    # Cisco: Interface Gi0/1, changed state to down | Line protocol on Interface X, changed state to up
    (re.compile(r"interface ([A-Za-z]+[\d/.:]+),? changed state to (administratively down|up|down)", re.I),
     lambda m: (m.group(1), "Caído" if "down" in m.group(2).lower() else "Arriba")),
    # Huawei: interface GE0/0/1 has entered the DOWN state
    (re.compile(r"interface ([A-Za-z\-]+[\d/.:]+) has entered the (UP|DOWN) state", re.I),
     lambda m: (m.group(1), "Caído" if m.group(2).upper() == "DOWN" else "Arriba")),
    # FortiGate: interface="wan1" ... status="down"  |  port3 link down
    (re.compile(r'interface="?([\w\-]+)"?.*?status="?(up|down)', re.I),
     lambda m: (m.group(1), "Caído" if m.group(2).lower() == "down" else "Arriba")),
    (re.compile(r"\b((?:port|wan|lan|dmz)\d*)\b link (up|down)", re.I),
     lambda m: (m.group(1), "Caído" if m.group(2).lower() == "down" else "Arriba")),
    # Fuente de poder
    (re.compile(r"power supply (\d+)\s*(failed|failure|fail|removed|ok|normal|restored)", re.I),
     lambda m: (f"Fuente de poder {m.group(1)}", "Falla" if m.group(2).lower() in ("failed", "failure", "fail", "removed") else "Arriba")),
    # Sensor de temperatura
    (re.compile(r"temperature sensor (\d+).*?(critical|warning|normal)", re.I),
     lambda m: (f"Sensor de temperatura {m.group(1)}",
                {"critical": "Crítico", "warning": "Advertencia", "normal": "Arriba"}[m.group(2).lower()])),
    # Ventilador
    (re.compile(r"fan (?:tray )?(\d+).*?(fail|failed|failure|ok|normal)", re.I),
     lambda m: (f"Ventilador {m.group(1)}", "Falla" if m.group(2).lower().startswith("fail") else "Arriba")),
    # Alta disponibilidad (clúster de firewalls)
    (re.compile(r"HA failover", re.I), lambda m: ("Clúster HA", "Conmutación")),
    # Túneles VPN
    (re.compile(r"tunnel ([\w\-]+) (up|down)", re.I),
     lambda m: (f"Túnel VPN {m.group(1)}", "Caído" if m.group(2).lower() == "down" else "Arriba")),
]


def _nombre_canonico(nombre: str) -> str:
    """Gi0/2 y GigabitEthernet0/2 son el mismo puerto: se unifican."""
    m = re.match(r"^([A-Za-z]+)([\d/.:]+)$", nombre)
    if m and m.group(1).lower() in _ABREVIATURAS:
        return _ABREVIATURAS[m.group(1).lower()] + m.group(2)
    return nombre


def identificar(mensaje: str) -> tuple[str | None, str | None]:
    """Devuelve (componente, estado) o (None, None) si el mensaje no habla de una parte del equipo."""
    for regla, armar in _REGLAS:
        m = regla.search(mensaje)
        if m:
            nombre, estado = armar(m)
            nombre = _SEGURO.sub("", _nombre_canonico(nombre))[:60].strip()
            return (nombre or None), estado
    return None, None


def es_problema(estado: str | None) -> bool:
    return estado in ESTADOS_PROBLEMA
