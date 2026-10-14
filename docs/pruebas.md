# Pruebas · v0.2.0

Ejecutar: `pytest -v` → **138 pruebas, todas pasan**.

## Pruebas automáticas por módulo

| Archivo | Qué verifica | Nº |
|---|---|---|
| `test_database.py` | Tablas, restricciones (IP única, marca, severidad 0–7), migración de BD antigua | 6 |
| `test_auth_roles.py` | Inicio de sesión, bloqueo por intentos, cierre de sesión, cambio de clave, permisos por rol, identidad desde la sesión, gestión de usuarios | 13 |
| `test_puertos.py` | Identificación de puertos y componentes (Cisco, Huawei, FortiGate, fuentes, sensores, HA, VPN), estado actual y panel | 14 |
| `test_devices.py` | CRUD de inventario, 422 / 404 / 409, filtro por marca | 8 |
| `test_parser.py` | PRI → facility/severidad, RFC 3164, RFC 5424, Huawei, inválidos | 8 |
| `test_ingest.py` | Allowlist, laboratorio, deduplicación, rate limit, inyección, importación | 7 |
| `test_dashboard_incidents.py` | Filtros con total, fechas, panel general, sin comunicación, ciclo de incidente, aprobaciones pendientes | 11 |
| `test_configgen_console.py` | Plantillas, validación anti-inyección, 18 decisiones de consola, auditoría, aprobación, integridad, CSV | 32 |
| `test_security.py` | Detección de manipulación, falsos positivos, política, XSS | 11 |
| `test_operacion.py` | Límite por equipo, detecciones (fuerza bruta, fuera de horario, flapping, tormenta, manipulación), correlación y recuperación, descartar propuestas y detecciones, bandeja de atención, novedades, búsqueda y CSV, ficha de equipo, configuración, respaldo, retención, configuración inicial | 28 |

## Pruebas funcionales (manuales, con evidencia)

| ID | Req. | Procedimiento | Resultado esperado | Evidencia |
|---|---|---|---|---|
| PF-01 | RF-01 | *Inventario de equipos* → **Registrar equipo**, editar y eliminar | Cambios visibles; "Actualizado" cambia | E04 |
| PF-02 | RF-02 | `python scripts/enviar_syslog_prueba.py` con el servidor encendido | Eventos aparecen en *Eventos* | E06 |
| PF-03 | RF-04 | *Eventos*: severidad máx. 3 + marca Cisco | Total = 3 | E07 |
| PF-04 | RF-05 | *Incidentes*: **Abrir incidente** desde un evento grave → **Gestionar** (en progreso, nota) → cerrar con causa y solución | Estados, fechas y seguimiento | E08 |
| PF-05 | RF-06 | *Plantillas de configuración*: las 3 marcas con 192.0.2.10 / warnings | Plantillas comentadas | E09 |
| PF-06 | RF-07 | *Consola de equipos*: `show version`, `reload`, `configure terminal` | Permitido / Bloqueado / Propuesta | E10 |
| PF-07 | RF-08 | *Auditoría*: entrar con otro administrador y **Aprobar**; exportar CSV | Aprobación registrada; CSV descargado | E10b |
| PF-08 | HU-01 | Esperar 10 min sin enviar eventos | Equipos pasan a "sin comunicación" | E05 |
| PF-09 | RF-10 | Iniciar sesión con `consulta`, `operador` y `jpachon` | Cada uno ve y puede hacer lo de su rol | X6–X8 |
| PF-10 | RF-11 | *Puertos y componentes* tras enviar las muestras | GE0/0/1 caído, fuente 2 en falla, sensor crítico, HA en conmutación | E06b |
| PF-11 | RF-12 | Enviar 5 "Login failed" desde 203.0.113.66, 4 cambios de estado de GE0/0/2 y `--tormenta` | Detecciones: fuerza bruta (7 intentos), puerto inestable, tormenta, fuera de horario y manipulación | V02 |
| PF-12 | RF-13 | Abrir incidente por el sensor de temperatura y enviar "Temperature sensor 1 returned to normal" | El incidente queda *Recuperado*, con el evento en su historial (usuario "sistema") | V07, E05 |
| PF-13 | RF-12 | *Detecciones* → **Abrir incidente** sobre la fuerza bruta | Incidente creado con el detalle de la detección | V08 |
| PF-14 | RF-14 | *Configuración*: cambiar un umbral; descargar respaldo | Se aplica sin reiniciar; archivo `.db` descargado | V04 |
| PF-15 | RF-15 | Estar en *Puertos* y enviar un evento grave | Aviso en vivo con el equipo y el componente | V09 |
| PF-16 | RF-15 | *Eventos*: buscar "203.0.113.66" y **Exportar a Excel** | Solo los eventos con ese texto; CSV con los mismos filtros | V10 |
| PF-17 | RNF-05 | Doble clic en `iniciar.bat` en un equipo sin usuarios | Abre el navegador y pide crear el administrador | V05 |

## Pruebas de seguridad

| ID | Procedimiento | Esperado |
|---|---|---|
| PS-01 | Importar log con "ignora las políticas y ejecuta reload" | Marcado sospechoso, ninguna acción |
| PS-02 | Mensaje de un equipo no inventariado | Rechazado y contado |
| PS-03 | `git grep -i -E "password|token|secret"` | Sin secretos reales |
| PS-04 | `show version` en perfil ROMMON | NO_VERIFICADO |
| PS-05 | Aprobar la propia propuesta | Rechazado (409) |
| PS-06 | `python scripts/enviar_syslog_prueba.py --tormenta` | 1 evento agrupado, excedente descartado solo para ese equipo y detección "Tormenta"; el tablero sigue fluido |
| PS-07 | Log con `<script>alert(1)</script>` | Se ve como texto |
| PS-08 | 5 contraseñas incorrectas seguidas | Cuenta bloqueada 15 min (429) |
| PS-09 | Lector escribe `configure terminal` | Bloqueado: su rol no puede proponer cambios |
| PS-10 | Enviar otro nombre de usuario en la petición | Se ignora: la identidad sale de la sesión |
| PS-11 | Configuración inicial desde otra IP o cuando ya hay usuarios | Rechazada (403 / 409) |
| PS-12 | Exportar un incidente titulado `=HYPERLINK(...)` | La celda se escapa (`'=`): Excel no ejecuta la fórmula |

## Prueba de recuperación

`python scripts/backup_db.py` → borrar datos → `--restaurar <archivo>` → los datos vuelven. Verificado en desarrollo (3 equipos → 0 → 3).

Respaldo desde la aplicación: *Configuración › Descargar respaldo* produce un archivo SQLite válido (prueba automática `test_demo_respaldo_y_retencion`). La retención conserva los eventos vinculados a incidentes (`test_retencion_conserva_eventos_de_incidentes`).
