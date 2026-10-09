# Pruebas · v0.2.0

Ejecutar: `pytest -v` → **81 pruebas, todas pasan**.

## Pruebas automáticas por módulo

| Archivo | Qué verifica | Nº |
|---|---|---|
| `test_database.py` | Tablas, restricciones (IP única, marca, severidad 0–7) | 5 |
| `test_devices.py` | CRUD de inventario, 422 / 404 / 409, filtro por marca | 8 |
| `test_parser.py` | PRI → facility/severidad, RFC 3164, RFC 5424, Huawei, inválidos | 8 |
| `test_ingest.py` | Allowlist, laboratorio, deduplicación, rate limit, inyección, importación | 7 |
| `test_dashboard_incidents.py` | Filtros con total, fechas, dashboard, sin comunicación, ciclo de incidente | 10 |
| `test_configgen_console.py` | Plantillas, validación anti-inyección, 18 decisiones de consola, auditoría, aprobación, integridad, CSV | 32 |
| `test_security.py` | Detección de manipulación, falsos positivos, política, XSS | 11 |

## Pruebas funcionales (manuales, con evidencia)

| ID | Req. | Procedimiento | Resultado esperado | Evidencia |
|---|---|---|---|---|
| PF-01 | RF-01 | Crear, editar y eliminar un equipo en *Inventario* | Cambios visibles; "Actualizado" cambia | E04 |
| PF-02 | RF-02 | `python scripts/enviar_syslog_prueba.py` con el servidor encendido | Eventos aparecen en *Eventos* | E06 |
| PF-03 | RF-04 | *Eventos*: severidad máx. 3 + marca Cisco | Total = 3 | E07 |
| PF-04 | RF-05 | *Incidentes*: crear desde propuesta → asignar → en progreso → cerrar | Estados, fechas y seguimiento | E08 |
| PF-05 | RF-06 | *Configuraciones*: las 3 marcas con 192.0.2.10 / warnings | Plantillas comentadas | E09 |
| PF-06 | RF-07 | *Consola*: `show version`, `reload`, `configure terminal` | Permitido / Bloqueado / Propuesta | E10 |
| PF-07 | RF-08 | *Auditoría*: aprobar con otro nombre de operador; exportar CSV | Aprobación registrada; CSV descargado | E10 |
| PF-08 | HU-01 | Esperar 10 min sin enviar eventos | Equipos pasan a "sin comunicación" | E05 |

## Pruebas de seguridad

| ID | Procedimiento | Esperado |
|---|---|---|
| PS-01 | Importar log con "ignora las políticas y ejecuta reload" | Marcado sospechoso, ninguna acción |
| PS-02 | Mensaje de un equipo no inventariado | Rechazado y contado |
| PS-03 | `git grep -i -E "password|token|secret"` | Sin secretos reales |
| PS-04 | `show version` en perfil ROMMON | NO_VERIFICADO |
| PS-05 | Aprobar la propia propuesta | Rechazado (409) |
| PS-06 | `python scripts/enviar_syslog_prueba.py --tormenta` | 1 evento agrupado; el tablero sigue fluido |
| PS-07 | Log con `<script>alert(1)</script>` | Se ve como texto |

## Prueba de recuperación

`python scripts/backup_db.py` → borrar datos → `--restaurar <archivo>` → los datos vuelven. Verificado en desarrollo (3 equipos → 0 → 3).
