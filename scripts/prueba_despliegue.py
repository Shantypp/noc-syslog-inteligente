"""
prueba_despliegue.py — Ensayo de despliegue y rollback (Corte 3). Datos [SIMULADOS].

Reproduce en una carpeta temporal el procedimiento de docs/despliegue-rollback.md:

  1. Instala la versión ANTERIOR (etiqueta v0.2.0) y la pone a recibir Syslog simulado.
  2. Respalda la base de datos (scripts/backup_db.py).
  3. Despliega la versión NUEVA (la rama o etiqueta indicada) sobre los mismos datos:
     la base se actualiza sola (columnas nuevas) y se verifica que no se perdió nada.
  4. ROLLBACK: detiene, restaura el respaldo, vuelve a v0.2.0 y verifica que arranca
     con los mismos datos.

No toca data/noc.db ni el NOC abierto (puertos 8771 y 5601). Usa el entorno .venv del proyecto.

Uso:
    python scripts/prueba_despliegue.py                         # nueva = HEAD actual
    python scripts/prueba_despliegue.py --nueva v1.0.0
"""

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import closing
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PYTHON = RAIZ / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PUERTO_WEB, PUERTO_UDP = 8771, 5601
URL = f"http://127.0.0.1:{PUERTO_WEB}"


def git(*args, cwd) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def entorno(bd: Path) -> dict:
    return {**os.environ, "NOC_DB_PATH": str(bd), "SYSLOG_UDP_ENABLED": "1", "SYSLOG_UDP_HOST": "127.0.0.1",
            "SYSLOG_UDP_PORT": str(PUERTO_UDP), "NOC_MONITOREO": "0", "TELEGRAM_BOT_TOKEN": "", "SSH_CLAVE": ""}


def iniciar(carpeta: Path, bd: Path) -> tuple[subprocess.Popen, dict, float]:
    t0 = time.perf_counter()
    p = subprocess.Popen([str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PUERTO_WEB),
                          "--log-level", "warning"], cwd=carpeta, env=entorno(bd),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=1) as r:
                return p, json.loads(r.read()), time.perf_counter() - t0
        except OSError:
            time.sleep(0.25)
    p.kill()
    raise SystemExit("El servidor no arrancó")


def detener(p: subprocess.Popen) -> None:
    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()


def conteos(bd: Path) -> dict:
    with closing(sqlite3.connect(bd)) as c:
        columnas = {r[1] for r in c.execute("PRAGMA table_info(devices)")}
        return {"equipos": c.execute("SELECT COUNT(*) FROM devices").fetchone()[0],
                "eventos": c.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                "columna_ssh_habilitado": "ssh_habilitado" in columnas}


def backup(carpeta: Path, bd: Path, *args) -> str:
    r = subprocess.run([str(PYTHON), "scripts/backup_db.py", *args], cwd=carpeta, env=entorno(bd),
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr)
    return r.stdout.strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--anterior", default="v0.2.0")
    p.add_argument("--nueva", default=None, help="etiqueta, rama o commit (por defecto el commit actual)")
    a = p.parse_args()
    nueva = a.nueva or git("rev-parse", "HEAD", cwd=RAIZ)

    tmp = Path(tempfile.mkdtemp(prefix="noc-despliegue-"))
    app_dir, bd = tmp / "noc", tmp / "datos" / "noc.db"
    bd.parent.mkdir()
    pasos, r = [], {"fecha": datetime.now().isoformat(timespec="seconds"), "datos": "SIMULADOS",
                    "anterior": a.anterior, "nueva": nueva[:12]}

    # 1. Versión anterior en producción (simulada) recibiendo Syslog
    git("clone", "--quiet", str(RAIZ), str(app_dir), cwd=tmp)
    git("checkout", "--quiet", a.anterior, cwd=app_dir)
    subprocess.run([str(PYTHON), "-c", "from app.database import init_db; init_db()"], cwd=app_dir, env=entorno(bd), check=True)
    with closing(sqlite3.connect(bd)) as c:
        c.execute("INSERT INTO devices (nombre, ip, marca, origen) VALUES ('SIM-R1', '192.0.2.201', 'Cisco', 'simulado')")
        c.commit()
    srv, salud, arranque = iniciar(app_dir, bd)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for i in range(20):
            s.sendto(f"<190>{time.strftime('%b %d %H:%M:%S')} SIM-R1 [SIMULADO] evento previo al despliegue {i}".encode(),
                     ("127.0.0.1", PUERTO_UDP))
            time.sleep(0.02)
    time.sleep(1)
    detener(srv)
    datos_v_anterior = conteos(bd)
    pasos.append({"paso": f"1. {a.anterior} en marcha", "version_reportada": salud["version"],
                  "arranque_s": round(arranque, 2), **datos_v_anterior})

    # 2. Respaldo antes de desplegar
    respaldo = backup(app_dir, bd).split("Respaldo creado:", 1)[1].strip()
    pasos.append({"paso": "2. Respaldo", "archivo": Path(respaldo).name})

    # 3. Despliegue de la versión nueva sobre los mismos datos
    t0 = time.perf_counter()
    git("checkout", "--quiet", nueva, cwd=app_dir)
    subprocess.run([str(PYTHON), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", "requirements.txt"],
                   cwd=app_dir, check=True)
    srv, salud, arranque = iniciar(app_dir, bd)
    t_despliegue = time.perf_counter() - t0
    detener(srv)
    datos_v_nueva = conteos(bd)
    pasos.append({"paso": "3. Despliegue versión nueva", "version_reportada": salud["version"],
                  "duracion_total_s": round(t_despliegue, 2), **datos_v_nueva,
                  "sin_perdida_de_datos": datos_v_nueva["eventos"] == datos_v_anterior["eventos"]})

    # 4. Rollback: restaurar respaldo + volver a la versión anterior
    t0 = time.perf_counter()
    backup(app_dir, bd, "--restaurar", respaldo)
    git("checkout", "--quiet", a.anterior, cwd=app_dir)
    srv, salud, arranque = iniciar(app_dir, bd)
    t_rollback = time.perf_counter() - t0
    detener(srv)
    datos_rollback = conteos(bd)
    pasos.append({"paso": f"4. Rollback a {a.anterior}", "version_reportada": salud["version"],
                  "duracion_total_s": round(t_rollback, 2), **datos_rollback,
                  "datos_iguales_a_antes_del_despliegue": datos_rollback == datos_v_anterior})

    r["pasos"] = pasos
    r["exito"] = (pasos[2]["sin_perdida_de_datos"] and pasos[3]["datos_iguales_a_antes_del_despliegue"]
                  and pasos[3]["version_reportada"] == pasos[0]["version_reportada"])
    salida = RAIZ / "docs" / "evidencias" / f"despliegue-{datetime.now():%Y%m%d-%H%M}.json"
    salida.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(r, indent=2, ensure_ascii=False))
    print(f"\nGuardado en {salida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
