"""
prueba_respaldo.py — Prueba de respaldo y recuperación (Corte 3).

Trabaja sobre una COPIA de la base de datos en una carpeta temporal: nunca modifica data/noc.db.

  1. Copia la base de datos (o crea una de prueba si no existe) y cuenta sus registros.
  2. Respaldo con scripts/backup_db.py (API de respaldo de SQLite).
  3. Desastre simulado: se borran eventos y se daña el archivo.
  4. Restauración con scripts/backup_db.py --restaurar.
  5. Verificación: mismos conteos, PRAGMA integrity_check = ok y la auditoría igual que antes (hash).

Uso:
    python scripts/prueba_respaldo.py
El resultado se imprime y se guarda en docs/evidencias/respaldo-AAAAMMDD-HHMM.json
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
TABLAS = ["devices", "events", "incidents", "detecciones", "command_audit", "users", "settings"]


def conteos(ruta: Path) -> dict:
    with closing(sqlite3.connect(ruta)) as c:
        return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLAS}


def integridad(ruta: Path) -> dict:
    from app.console.audit import verificar_integridad
    with closing(sqlite3.connect(ruta)) as c:
        c.row_factory = sqlite3.Row
        return {"sqlite": c.execute("PRAGMA integrity_check").fetchone()[0], "auditoria": verificar_integridad(c)}


def correr(args: list[str], bd: Path) -> str:
    env = {**os.environ, "NOC_DB_PATH": str(bd)}
    r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "backup_db.py"), *args],
                       env=env, capture_output=True, text=True, cwd=RAIZ)
    if r.returncode != 0:
        raise SystemExit(f"backup_db.py falló: {r.stderr or r.stdout}")
    return r.stdout.strip()


def main() -> None:
    carpeta = Path(tempfile.mkdtemp(prefix="noc-respaldo-"))
    bd = carpeta / "noc.db"
    real = RAIZ / "data" / "noc.db"
    if real.exists():
        with closing(sqlite3.connect(real)) as origen, closing(sqlite3.connect(bd)) as copia:
            origen.backup(copia)  # copia consistente aunque el NOC esté abierto
        fuente = "copia de la base de datos de trabajo (data/noc.db)"
    else:
        from app.database import init_db
        init_db(str(bd))
        fuente = "base de datos nueva de prueba"

    antes = conteos(bd)
    integridad_antes = integridad(bd)
    t0 = time.perf_counter()
    salida = correr([], bd)
    respaldo = Path(salida.split("Respaldo creado:", 1)[1].strip())
    t_respaldo = time.perf_counter() - t0

    # Desastre simulado: se pierden eventos y luego el archivo queda dañado
    with closing(sqlite3.connect(bd)) as c:
        c.execute("DELETE FROM events")
        c.commit()  # el borrado queda en noc.db-wal (modo WAL), como en el NOC real
    perdidos = conteos(bd)["events"]
    with open(bd, "r+b") as f:
        f.seek(100)
        f.write(b"\x00" * 4096)  # se escriben ceros sobre la cabecera de páginas
    try:
        with closing(sqlite3.connect(bd)) as c:
            dañada = c.execute("PRAGMA integrity_check").fetchone()[0]
    except sqlite3.DatabaseError as e:
        dañada = f"error: {e}"

    t0 = time.perf_counter()
    correr(["--restaurar", str(respaldo)], bd)
    t_restaurar = time.perf_counter() - t0
    despues = conteos(bd)
    verif = integridad(bd)

    resultado = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "fuente": fuente,
        "conteos_antes": antes,
        "respaldo_segundos": round(t_respaldo, 2),
        "respaldo_tamano_kb": respaldo.stat().st_size // 1024,
        "desastre": {"eventos_tras_borrado": perdidos, "integrity_check_tras_dano": dañada},
        "restauracion_segundos": round(t_restaurar, 2),
        "conteos_despues": despues,
        "conteos_iguales": antes == despues,
        "verificacion_antes": integridad_antes,
        "verificacion_despues": verif,
        # Éxito: la copia restaurada es idéntica a la original (la restauración no altera nada).
        # Si la original ya tenía registros alterados, se reportan aparte: el respaldo los conserva tal cual.
        "exito": antes == despues and verif["sqlite"] == "ok"
                 and verif["auditoria"]["alterados"] == integridad_antes["auditoria"]["alterados"],
    }
    salida_json = RAIZ / "docs" / "evidencias" / f"respaldo-{datetime.now():%Y%m%d-%H%M}.json"
    salida_json.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print(f"\nGuardado en {salida_json.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
