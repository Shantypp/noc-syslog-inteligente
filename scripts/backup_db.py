"""
backup_db.py — Copia de seguridad y restauración de la base de datos (RNF-08 Recuperación).

Uso:
    python scripts/backup_db.py                         # crea data/backups/noc-AAAAMMDD-HHMMSS.db
    python scripts/backup_db.py --listar                # muestra los respaldos disponibles
    python scripts/backup_db.py --restaurar ARCHIVO     # restaura (apaga el servidor antes)

Usa la API de respaldo de SQLite: la copia es consistente aunque la BD esté en uso.
"""

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # permite importar "app"
from app.database import DB_PATH  # noqa: E402

CARPETA = Path(DB_PATH).parent / "backups"


def respaldar() -> Path:
    CARPETA.mkdir(parents=True, exist_ok=True)
    destino = CARPETA / f"noc-{datetime.now():%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(DB_PATH) as origen, sqlite3.connect(destino) as copia:
        origen.backup(copia)
    return destino


def restaurar(archivo: str) -> None:
    respaldo = Path(archivo)
    if not respaldo.exists():
        sys.exit(f"No existe {respaldo}")
    with sqlite3.connect(respaldo) as c:  # verifica que sea una BD válida antes de restaurar
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            sys.exit("El respaldo está dañado; no se restaura")
    previo = respaldar()  # rollback del rollback: se guarda el estado actual antes de reemplazarlo
    shutil.copyfile(respaldo, DB_PATH)
    print(f"Restaurado {respaldo} -> {DB_PATH} (estado anterior guardado en {previo})")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Respaldo de la BD del NOC")
    p.add_argument("--listar", action="store_true")
    p.add_argument("--restaurar", metavar="ARCHIVO")
    a = p.parse_args()
    if a.listar:
        for f in sorted(CARPETA.glob("*.db")):
            print(f"{f}  ({f.stat().st_size // 1024} KB)")
    elif a.restaurar:
        restaurar(a.restaurar)
    else:
        print(f"Respaldo creado: {respaldar()}")
