"""
api/security.py — Módulo de política de defensa frente a agentes de IA.

    GET  /api/seguridad           controles activos con evidencia en vivo
    POST /api/seguridad/analizar  prueba un texto contra el detector (no guarda ni ejecuta nada)

Responde a la pregunta del curso: ¿cómo puede Syslog, mediante políticas explícitas,
ayudar a detectar, contener y mitigar acciones no autorizadas de agentes de IA?
"""

import os
import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.collector import ingest
from app.console import audit
from app.database import get_db
from app import config
from app.incidents.policy import umbral_incidente
from app.security.auth import requiere
from app.security.controls import es_sospechoso, limpiar_mensaje

router = APIRouter(prefix="/api/seguridad", tags=["seguridad IA"], dependencies=[Depends(requiere("lector"))])

FLUJO = ["Evento detectado", "Validación", "Propuesta de acción", "Revisión humana",
         "Aprobación", "Ejecución autorizada", "Verificación", "Auditoría"]


class Texto(BaseModel):
    texto: str = Field(max_length=2048)


@router.get("")
def estado(conn: sqlite3.Connection = Depends(get_db)):
    uno = lambda sql, *p: conn.execute(sql, p).fetchone()[0]  # noqa: E731
    est = ingest.totales(conn)
    umbral = umbral_incidente(conn)
    ventana, limite = config.obtener(conn, "ventana_dedup_s"), config.obtener(conn, "limite_por_minuto")
    detecciones = uno("SELECT COUNT(*) FROM detecciones")
    integ = audit.verificar_integridad(conn)
    fuentes = uno("SELECT COUNT(*) FROM devices")
    sospechosos = uno("SELECT COUNT(*) FROM events WHERE sospechoso = 1")
    agrupados = uno("SELECT COALESCE(SUM(repeticiones - 1), 0) FROM events")
    pendientes = uno("SELECT COUNT(*) FROM command_audit WHERE resultado = ?", audit.PENDIENTE)
    bloqueados = uno("SELECT COUNT(*) FROM command_audit WHERE decision IN ('BLOQUEADO', 'NO_VERIFICADO')")
    fallos_login = uno("SELECT COUNT(*) FROM events WHERE mensaje LIKE '%LOGIN%FAIL%' OR mensaje LIKE '%login failed%'")
    total_eventos = uno("SELECT COUNT(*) FROM events")
    total_incidentes = uno("SELECT COUNT(*) FROM incidents")
    usuarios = uno("SELECT COUNT(*) FROM users WHERE activo = 1")
    fallidos = uno("SELECT COUNT(*) FROM auth_log WHERE exito = 0")

    def c(n, control, implementacion, evidencia, estado="activo"):
        return {"n": n, "control": control, "implementacion": implementacion, "evidencia": evidencia, "estado": estado}

    return {
        "flujo": FLUJO,
        "controles": [
            c(1, "Fuentes autorizadas", "Solo se aceptan mensajes de equipos del inventario (allowlist por IP u hostname en laboratorio).",
              f"{fuentes} fuentes autorizadas · {est.get('fuente_no_autorizada', 0)} mensajes rechazados"),
            c(2, "Centralización de logs", "Colector único: receptor UDP + importación de archivos.",
              f"{total_eventos} eventos centralizados"),
            c(3, "Hora sincronizada (NTP)", "Se guarda la hora del colector (UTC) y la del equipo; las plantillas incluyen timestamps y NTP.",
              "recibido_en (UTC) + timestamp_equipo", "parcial"),
            c(4, "Severidades que generan alerta/incidente", f"Severidad 0–{umbral} genera PROPUESTA de incidente; un humano decide.",
              f"{total_incidentes} incidentes creados por personas"),
            c(5, "Accesos, fallos de autenticación y cambios", "Se clasifican y filtran (LOGIN_FAILED, CONFIG_I, CMDRECORD...). Detección automática de fuerza bruta y de cambios fuera de horario.",
              f"{fallos_login} fallos de login registrados · {detecciones} detecciones automáticas"),
            c(6, "Comandos y cambios no autorizados", "Toda la actividad de consola queda auditada; los cambios solo como propuesta.",
              f"{bloqueados} comandos bloqueados o no verificados"),
            c(7, "Listas permitidas de dispositivos y comandos", "Allowlist por marca/modo; denegar por defecto.",
              "4 perfiles: Cisco IOS XE, FortiGate, Huawei VRP, ROMMON"),
            c(8, "Roles, retención, integridad, respaldo, transporte seguro",
              "Inicio de sesión con roles (lector, operador, administrador) y bloqueo tras 5 intentos fallidos; "
              "hash SHA-256 por registro de auditoría; respaldo descargable desde Configuración; retención automática de eventos "
              f"({config.obtener(conn, 'dias_retencion')} días). TLS en Corte 3.",
              f"{usuarios} usuarios · {fallidos} inicios de sesión fallidos · integridad {integ['integros']}/{integ['total']}" + (f" · registros alterados: {integ['alterados']}" if integ['alterados'] else ""), "parcial"),
            c(9, "Deduplicación, límite de frecuencia y tormentas",
              f"Ventana de {ventana} s y máximo {limite} mensajes/min POR EQUIPO (uno ruidoso no silencia a los demás).",
              f"{agrupados} mensajes repetidos agrupados · {est.get('limitado', 0)} descartados por límite"),
            c(10, "Logs = datos no confiables", "Nunca se ejecutan ni se envían como instrucción; se muestran como texto; patrones de inyección se marcan.",
              f"{sospechosos} eventos sospechosos marcados (guardados como evidencia)"),
            c(11, "Aprobación humana antes de cambios", "Solo un administrador aprueba, y nunca su propia propuesta (identidad tomada del inicio de sesión). En el MVP la ejecución es simulada.",
              f"{pendientes} propuestas esperando revisión"),
        ],
        "configuracion": {
            "udp": f"{os.getenv('SYSLOG_UDP_HOST', '127.0.0.1')}:{os.getenv('SYSLOG_UDP_PORT', '5514')}",
            "ventana_dedup_s": ventana,
            "rate_limit_min": limite,
            "umbral_incidente": umbral,
        },
    }


@router.post("/analizar")
def analizar(datos: Texto):
    """Laboratorio: ¿este texto sería marcado como sospechoso? (no se guarda ni se ejecuta)."""
    limpio = limpiar_mensaje(datos.texto)
    return {"sospechoso": es_sospechoso(limpio), "texto_limpio": limpio,
            "accion": "Se guardaría como DATO marcado como sospechoso. Ninguna acción se ejecuta."
            if es_sospechoso(limpio) else "Se guardaría como dato normal."}
