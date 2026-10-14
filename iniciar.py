"""
iniciar.py — Instala (si hace falta) y abre el NOC con UN solo comando.

    python iniciar.py              modo laboratorio: solo recibe Syslog de este computador
    python iniciar.py --red        recibe Syslog de los equipos de la red (routers, firewalls...)
    python iniciar.py --puerto 8080    usar otro puerto web (por defecto 8000)
    python iniciar.py --desarrollo     recarga automática al editar el código

En Windows basta con doble clic en iniciar.bat.

Qué hace, en orden:
  1. Verifica que Python sea 3.12 o superior.
  2. Crea el entorno virtual .venv (solo la primera vez).
  3. Instala las dependencias (solo si requirements.txt cambió desde la última vez).
  4. Crea el archivo .env a partir de .env.example si no existe.
  5. Inicia el servidor, espera a que responda y abre el navegador.
La primera vez, la aplicación pide crear el usuario administrador (sin editar archivos).
Para detener: Ctrl+C en esta ventana.
"""

import argparse
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
VENV = RAIZ / ".venv"
PYTHON_VENV = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQUISITOS = RAIZ / "requirements.txt"
HUELLA = VENV / ".requisitos.sha256"


def paso(texto: str) -> None:
    print(f"  > {texto}", flush=True)


def salir(texto: str) -> None:
    print(f"\n  [ERROR] {texto}\n", flush=True)
    sys.exit(1)


def preparar_entorno() -> None:
    if sys.version_info < (3, 12):
        salir(f"Se necesita Python 3.12 o superior (tiene {sys.version.split()[0]}). "
              "Descárguelo de https://www.python.org/downloads/")
    if not PYTHON_VENV.exists():
        paso("Primera ejecución: creando el entorno virtual (.venv)...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    huella = hashlib.sha256(REQUISITOS.read_bytes()).hexdigest()
    if not HUELLA.exists() or HUELLA.read_text().strip() != huella:
        paso("Instalando dependencias (puede tardar 1-2 minutos la primera vez)...")
        r = subprocess.run([str(PYTHON_VENV), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                            "-r", str(REQUISITOS)])
        if r.returncode != 0:
            salir("No se pudieron instalar las dependencias. Revise su conexión a internet y vuelva a intentar.")
        HUELLA.write_text(huella)
    env = RAIZ / ".env"
    if not env.exists():
        shutil.copy(RAIZ / ".env.example", env)
        paso("Se creó el archivo de configuración .env (valores por defecto).")


def puerto_libre(puerto: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", puerto)) != 0


def responde(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=1) as r:
            import json
            return json.loads(r.read())
    except Exception:
        return None


def ips_locales() -> list[str]:
    try:
        return sorted({ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")})
    except OSError:
        return []


def main() -> None:
    p = argparse.ArgumentParser(description="Inicia el NOC Syslog")
    p.add_argument("--red", action="store_true", help="recibir Syslog de equipos de la red (no solo de este computador)")
    p.add_argument("--puerto", type=int, default=8000, help="puerto de la interfaz web (por defecto 8000)")
    p.add_argument("--desarrollo", action="store_true", help="recarga automática al cambiar el código")
    p.add_argument("--sin-navegador", action="store_true", help="no abrir el navegador")
    args = p.parse_args()

    os.chdir(RAIZ)  # las rutas relativas (data/noc.db, .env) siempre desde la carpeta del proyecto
    print("\n  NOC Syslog Inteligente\n  " + "=" * 40, flush=True)
    preparar_entorno()

    url = f"http://127.0.0.1:{args.puerto}"
    if not puerto_libre(args.puerto):
        if responde(url):  # ya hay un NOC abierto: solo se abre el navegador
            paso(f"El NOC ya está abierto en {url}")
            if not args.sin_navegador:
                webbrowser.open(url)
            return
        salir(f"El puerto {args.puerto} está ocupado por otro programa. Use: python iniciar.py --puerto 8080")

    entorno = dict(os.environ)
    if args.red:
        entorno["SYSLOG_UDP_HOST"] = "0.0.0.0"
    comando = [str(PYTHON_VENV), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
               "--port", str(args.puerto), "--log-level", "warning"]
    if args.desarrollo:
        comando.append("--reload")

    paso("Iniciando el servidor...")
    servidor = subprocess.Popen(comando, env=entorno)
    try:
        for _ in range(60):  # espera hasta 30 s a que responda
            if servidor.poll() is not None:
                salir("El servidor se cerró al iniciar. Revise los mensajes de arriba.")
            if responde(url):
                break
            time.sleep(0.5)
        else:
            salir("El servidor no respondió a tiempo.")

        puerto_udp = os.getenv("SYSLOG_UDP_PORT", "5514")
        print("\n  " + "=" * 40)
        print(f"  LISTO. Abra en el navegador:  {url}")
        if args.red:
            ips = " o ".join(ips_locales()) or "la IP de este computador"
            print(f"  Syslog: configure los equipos hacia {ips}, puerto UDP {puerto_udp}")
            print("  (Si Windows pregunta por el acceso a la red, elija 'Redes privadas'.)")
        else:
            print(f"  Syslog: modo laboratorio, solo este computador (UDP {puerto_udp}).")
            print("          Para recibir de routers reales: python iniciar.py --red")
        print("  Para detener el NOC: presione Ctrl+C en esta ventana.")
        print("  " + "=" * 40 + "\n", flush=True)
        if not args.sin_navegador:
            webbrowser.open(url)
        servidor.wait()
    except KeyboardInterrupt:
        print("\n  Deteniendo el NOC...", flush=True)
    finally:
        if servidor.poll() is None:
            servidor.terminate()
            try:
                servidor.wait(timeout=10)
            except subprocess.TimeoutExpired:
                servidor.kill()
        print("  NOC detenido.\n", flush=True)


if __name__ == "__main__":
    main()
