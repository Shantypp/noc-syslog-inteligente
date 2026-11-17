"""
prueba_carga.py — Prueba de carga básica del NOC (Corte 3). Datos [SIMULADOS].

Levanta un NOC APARTE (base de datos temporal, web 127.0.0.1:8768, Syslog UDP 127.0.0.1:5599),
así que no toca data/noc.db ni el NOC que esté abierto. Mide tres cosas:

  A. Rendimiento: N mensajes distintos de 3 equipos simulados a ritmo fijo.
     ¿Cuántos llegan y se guardan? ¿A qué velocidad los procesa el colector?
  B. Tormenta: un solo equipo envía 2.000 mensajes lo más rápido posible con el límite
     normal (300/min). ¿Se protege el sistema? ¿Los demás equipos siguen entrando?
  C. Interfaz bajo carga: tiempo de respuesta del panel (/api/dashboard) mientras llegan mensajes.

Uso:
    python scripts/prueba_carga.py                 # 3.000 mensajes a 500 msg/s (por defecto)
    python scripts/prueba_carga.py --mensajes 6000 --ritmo 1000

El resultado se imprime y se guarda en docs/evidencias/carga-AAAAMMDD-HHMM.json
"""

import argparse
import http.cookiejar
import json
import os
import secrets
import socket
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
PUERTO_WEB, PUERTO_UDP = 8768, 5599
URL = f"http://127.0.0.1:{PUERTO_WEB}"
EQUIPOS = [("SIM-R1", "192.0.2.101", "Cisco"), ("SIM-FW1", "192.0.2.102", "Fortinet"), ("SIM-SW1", "192.0.2.103", "Huawei")]


def preparar_bd(ruta: str, clave: str) -> None:
    from app.database import get_connection, init_db
    from app.security.auth import hash_clave
    init_db(ruta)
    with get_connection(ruta) as c:
        c.executemany("INSERT INTO devices (nombre, ip, marca, origen) VALUES (?, ?, ?, 'simulado')", EQUIPOS)
        c.execute("INSERT INTO users (usuario, nombre, rol, clave_hash) VALUES ('carga', 'Prueba de carga', "
                  "'administrador', ?)", (hash_clave(clave),))


def contar(ruta: str) -> dict:
    with sqlite3.connect(ruta) as c:
        totales = {r[0]: r[1] for r in c.execute("SELECT resultado, SUM(cantidad) FROM ingest_stats GROUP BY resultado")}
        totales["eventos_en_bd"] = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        totales["detecciones_tormenta"] = c.execute("SELECT COUNT(*) FROM detecciones WHERE regla = 'tormenta'").fetchone()[0]
    return totales


def poner_limite(ruta: str, valor: int) -> None:
    from app import config
    with sqlite3.connect(ruta) as c:
        c.row_factory = sqlite3.Row
        config.guardar(c, "limite_por_minuto", valor, "prueba_carga")


def esperar_quietud(ruta: str, max_s: float = 120) -> float:
    """Espera a que el colector termine de procesar (el conteo deja de cambiar 2 s)."""
    inicio, anterior, quieto = time.monotonic(), -1, time.monotonic()
    while time.monotonic() - inicio < max_s:
        actual = sum(v for k, v in contar(ruta).items() if k not in ("eventos_en_bd", "detecciones_tormenta"))
        if actual != anterior:
            anterior, quieto = actual, time.monotonic()
        elif time.monotonic() - quieto > 2:
            return quieto - inicio
        time.sleep(0.2)
    return max_s


def enviar(lineas: list[str], ritmo: float | None) -> float:
    """Envía por UDP. ritmo = mensajes por segundo (None = lo más rápido posible). Devuelve los segundos."""
    inicio = time.perf_counter()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for i, linea in enumerate(lineas):
            s.sendto(linea.encode(), ("127.0.0.1", PUERTO_UDP))
            if ritmo:
                espera = inicio + (i + 1) / ritmo - time.perf_counter()
                if espera > 0:
                    time.sleep(espera)
    return time.perf_counter() - inicio


def medir_panel(clave: str, detener: threading.Event, tiempos: list[float]) -> None:
    abridor = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    pedido = urllib.request.Request(f"{URL}/api/auth/login", data=json.dumps({"usuario": "carga", "clave": clave}).encode(),
                                    headers={"Content-Type": "application/json"})
    abridor.open(pedido, timeout=10).read()
    while not detener.is_set():
        t = time.perf_counter()
        abridor.open(f"{URL}/api/dashboard", timeout=30).read()
        tiempos.append((time.perf_counter() - t) * 1000)
        time.sleep(0.5)


def main() -> None:
    p = argparse.ArgumentParser(description="Prueba de carga básica (datos simulados)")
    p.add_argument("--mensajes", type=int, default=3000)
    p.add_argument("--ritmo", type=float, default=500, help="mensajes por segundo en la fase A")
    a = p.parse_args()

    carpeta = Path(tempfile.mkdtemp(prefix="noc-carga-"))
    ruta = str(carpeta / "carga.db")
    clave = secrets.token_urlsafe(16)  # contraseña desechable, solo existe durante la prueba
    preparar_bd(ruta, clave)
    entorno = {**os.environ, "NOC_DB_PATH": ruta, "SYSLOG_UDP_ENABLED": "1", "SYSLOG_UDP_HOST": "127.0.0.1",
               "SYSLOG_UDP_PORT": str(PUERTO_UDP), "NOC_MONITOREO": "0", "TELEGRAM_BOT_TOKEN": "", "SSH_CLAVE": ""}
    python = RAIZ / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    servidor = subprocess.Popen([str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                 "--port", str(PUERTO_WEB), "--log-level", "warning"], cwd=RAIZ, env=entorno,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # un registro por mensaje taparía el resultado
    resultado = {"fecha": datetime.now().isoformat(timespec="seconds"), "datos": "SIMULADOS",
                 "equipo": f"portátil de pruebas, Windows, Python {sys.version.split()[0]}"}
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{URL}/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.5)

        # ---- A. Rendimiento (límite alto para medir solo la capacidad)
        poner_limite(ruta, 100000)
        lineas = [f"<190>{time.strftime('%b %d %H:%M:%S')} {EQUIPOS[i % 3][0]} [SIMULADO] prueba de carga mensaje {i} Gi0/{i % 48}"
                  for i in range(a.mensajes)]
        tiempos_panel: list[float] = []
        detener = threading.Event()
        hilo = threading.Thread(target=medir_panel, args=(clave, detener, tiempos_panel), daemon=True)
        hilo.start()
        envio_s = enviar(lineas, a.ritmo)
        proceso_s = esperar_quietud(ruta)
        detener.set()
        hilo.join(timeout=35)
        c = contar(ruta)
        resultado["A_rendimiento"] = {
            "enviados": a.mensajes, "ritmo_objetivo_msg_s": a.ritmo, "segundos_enviando": round(envio_s, 2),
            "guardados": c.get("guardado", 0), "perdidos_udp": a.mensajes - sum(c.get(k, 0) for k in
                                                                              ("guardado", "duplicado", "limitado", "invalido", "fuente_no_autorizada")),
            "segundos_hasta_procesar_todo": round(proceso_s, 2),
            "msg_por_segundo_procesados": round(c.get("guardado", 0) / max(proceso_s, envio_s), 1),
        }
        resultado["C_panel_bajo_carga_ms"] = {
            "consultas": len(tiempos_panel),
            "mediana": round(statistics.median(tiempos_panel), 1) if tiempos_panel else None,
            "p95": round(sorted(tiempos_panel)[int(len(tiempos_panel) * 0.95) - 1], 1) if len(tiempos_panel) >= 2 else None,
            "maximo": round(max(tiempos_panel), 1) if tiempos_panel else None,
        }

        # ---- B. Tormenta de un equipo con el límite normal
        time.sleep(61)  # el límite cuenta por minuto: se espera a que la fase A salga de la ventana
        poner_limite(ruta, 300)
        antes = contar(ruta)
        enviar([f"<187>{time.strftime('%b %d %H:%M:%S')} SIM-R1 [SIMULADO] tormenta {i} %LINK-3-UPDOWN: Interface Gi0/1, changed state to down"
                for i in range(2000)], 1000)  # 1.000 msg/s durante 2 s
        enviar([f"<190>{time.strftime('%b %d %H:%M:%S')} SIM-FW1 [SIMULADO] tráfico normal durante la tormenta {i}" for i in range(50)], 100)
        esperar_quietud(ruta)
        despues = contar(ruta)
        with sqlite3.connect(ruta) as cx:
            fw = cx.execute("SELECT COUNT(*) FROM events e JOIN devices d ON d.id = e.device_id "
                            "WHERE d.nombre = 'SIM-FW1' AND e.mensaje LIKE '%durante la tormenta%'").fetchone()[0]
        resultado["B_tormenta"] = {
            "enviados_por_SIM-R1": 2000, "ritmo_msg_s": 1000, "aceptados_SIM-R1": despues.get("guardado", 0) - antes.get("guardado", 0) - fw,
            "descartados_por_limite": despues.get("limitado", 0) - antes.get("limitado", 0),
            "detecciones_de_tormenta": despues["detecciones_tormenta"],
            "SIM-FW1_enviados_durante_la_tormenta": 50, "SIM-FW1_guardados": fw,
        }
        r = urllib.request.urlopen(f"{URL}/api/health", timeout=5)
        resultado["servidor_sigue_respondiendo"] = r.status == 200
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            servidor.kill()

    salida = RAIZ / "docs" / "evidencias" / f"carga-{datetime.now():%Y%m%d-%H%M}.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print(f"\nGuardado en {salida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
