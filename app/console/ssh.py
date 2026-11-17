"""
console/ssh.py — Gestor SSH por el backend (Corte 3).

La consola deja de ser solo una simulación cuando se cumplen TRES condiciones:
  1. el equipo está en el inventario, es REAL y está activo;
  2. el administrador le habilitó "Gestión por SSH" (lista de hosts permitidos);
  3. las credenciales están en el archivo .env (SSH_USUARIO y SSH_CLAVE), nunca en el código.

Las reglas no cambian: la decisión (permitido / propuesta / bloqueado) la toma primero
console/simulator.py según el rol y la lista de comandos. Por SSH solo viajan:
  - consultas PERMITIDAS (solo lectura), y
  - cambios PROPUESTOS que otro administrador ya aprobó.
Todo queda en la auditoría con su hash. La salida del equipo es texto no confiable:
se limpia, se recorta y nunca se interpreta.
"""

import os
import re

PERFIL_POR_MARCA = {"Cisco": "cisco_ios", "Fortinet": "fortigate", "Huawei": "huawei_vrp"}
TIPO_NETMIKO = {"Cisco": "cisco_ios", "Fortinet": "fortinet", "Huawei": "huawei"}
LARGO_SALIDA = 20_000
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
# Comandos que solo entran al modo configuración: al aprobarlos no hay nada que aplicar
_SOLO_MODO_CONFIG = {"configure terminal", "conf t", "configure", "conf", "system-view", "sys", "config"}


class ErrorSSH(Exception):
    """No se pudo conectar o ejecutar (el mensaje nunca incluye la contraseña)."""


def credenciales() -> tuple[str, str]:
    return os.getenv("SSH_USUARIO", "").strip(), os.getenv("SSH_CLAVE", "")


def configurado() -> bool:
    usuario, clave = credenciales()
    return bool(usuario and clave)


def habilitado(equipo: dict | None) -> bool:
    """¿Este equipo se gestiona por SSH real? (lista de hosts permitidos)"""
    return bool(equipo and equipo.get("origen") == "real" and equipo.get("estado") == "activo"
                and equipo.get("ssh_habilitado") and equipo.get("marca") in TIPO_NETMIKO and configurado())


def _limpiar(texto: str) -> str:
    return _CONTROL.sub("", texto or "")[:LARGO_SALIDA].strip()


def _conectar(equipo: dict):
    from netmiko import ConnectHandler  # import local: el NOC funciona aunque netmiko no esté instalado
    usuario, clave = credenciales()
    try:
        return ConnectHandler(device_type=TIPO_NETMIKO[equipo["marca"]], host=equipo["ip"],
                              username=usuario, password=clave, timeout=15, conn_timeout=10,
                              auth_timeout=15, fast_cli=False)
    except Exception as e:  # se informa el tipo de error, sin datos sensibles
        raise ErrorSSH(f"No se pudo conectar por SSH a {equipo['nombre']} ({equipo['ip']}): {type(e).__name__}") from None


def consultar(equipo: dict, comando: str) -> str:
    """Ejecuta una consulta de SOLO LECTURA ya autorizada y devuelve la salida limpia."""
    conexion = _conectar(equipo)
    try:
        return _limpiar(conexion.send_command(comando, read_timeout=30))
    except Exception as e:
        raise ErrorSSH(f"El equipo no respondió al comando: {type(e).__name__}") from None
    finally:
        conexion.disconnect()


def aplicar_cambio(equipo: dict, comando: str) -> str:
    """Aplica en modo configuración un cambio que OTRO administrador ya aprobó."""
    if " ".join(comando.lower().split()) in _SOLO_MODO_CONFIG:
        return "Nada que aplicar: el comando solo entra al modo de configuración."
    conexion = _conectar(equipo)
    try:
        salida = conexion.send_config_set([comando], read_timeout=30)
        return _limpiar(salida)
    except Exception as e:
        raise ErrorSSH(f"No se pudo aplicar el cambio: {type(e).__name__}") from None
    finally:
        conexion.disconnect()
