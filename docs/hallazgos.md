# Hallazgos y correcciones · de v0.2.0 a v1.0.0

Lista de problemas encontrados después de la entrega del Corte 2, de dónde salieron y qué se hizo.
"Origen" dice si el hallazgo apareció con equipos reales, en una prueba automática o en una revisión propia.
Como no se recibió retroalimentación escrita del Corte 2, los hallazgos H-01 a H-02 salen de las
limitaciones que el propio informe del Corte 2 reconocía.

| ID | Hallazgo | Origen | Corrección | Evidencia | Estado |
|---|---|---|---|---|---|
| H-01 | La consola era solo una simulación; no se podía gestionar un equipo real | Limitación declarada en el Corte 2 | Gestor SSH por el backend (Netmiko) solo para equipos reales con "Gestión por SSH"; consultas de la lista permitida y cambios aprobados por otro administrador | `app/console/ssh.py`, 9 pruebas en `test_corte3.py` | Corregido. Falta prueba en el laboratorio (P-01, P-02) |
| H-02 | No había notificaciones fuera del navegador | Limitación declarada en el Corte 2 | Alertas por Telegram con token en `.env`, enmascarado y con anti-inundación | `app/notificaciones/`, 8 pruebas | Corregido. Falta prueba con bot real (P-04) |
| H-03 | Los mensajes reales de Cisco traen número de secuencia y fecha propia; no se agrupaban ni se leía bien el nombre del equipo | Equipo real, 16-oct (MB-01) | Analizador con el formato real de Cisco | `test_parser.py` (formato real) | Corregido |
| H-04 | Un equipo sano que no envía mensajes aparecía "sin comunicación" | Equipos reales, 21-oct (MB-02) | Monitoreo por ping cada 10 s; caído tras 3 fallos | `test_monitoreo.py`, 5/5 caídas reales detectadas | Corregido |
| H-05 | El intervalo de ping de 30 s hacía que una caída tardara hasta 90 s en verse | Equipos reales, 21-oct | Intervalo de 10 s (configurable) | 19–24 s medidos en el laboratorio | Corregido |
| H-06 | El iniciador no sabía si abrir el NOC en modo red o laboratorio | Uso real | `iniciar-sistema.bat` decide solo según la red conectada | — | Corregido |
| H-07 | Al desconectar el portátil, los 4 equipos aparecían caídos a la vez (falsa alarma) | Equipos reales, 21-oct (MB-04) | Un solo aviso "NOC sin conexión a la red de gestión"; no se declaran caídas | `test_sin_red_de_gestion_un_solo_aviso...` | Corregido. Falta repetirlo en el laboratorio (P-05) |
| H-08 | A 500 mensajes por segundo se perdía el 10,3 % por UDP y el panel tardaba ~100 ms | Prueba de carga (MB-05) | Una conexión de base de datos para el receptor, registro por mensaje en DEBUG, búfer UDP de 8 MB | `docs/evidencias/carga-*-antes.json` y `-despues.json` | Corregido: 0 % de pérdida |
| H-09 | Dos respaldos en el mismo segundo tenían el mismo nombre: el respaldo "previo a restaurar" sobrescribía el bueno | Prueba de recuperación (MB-06) | Nombres únicos y prefijo `antes-de-restaurar` | `respaldo-*-antes.json` (falló) y `respaldo-*.json` (éxito) | Corregido |
| H-10 | `backup_db.py` no cerraba la base; en Windows el archivo quedaba bloqueado | Prueba de recuperación | `closing()` y limpieza de archivos `-wal`/`-shm` | idem | Corregido |
| H-11 | Borrar un equipo dejaba en blanco el equipo de su auditoría y rompía el hash | Prueba de recuperación: la verificación marcó el registro #1 de la base de trabajo | Un equipo con auditoría no se borra (se marca Inactivo) | `test_equipo_con_auditoria_no_se_elimina...` | Corregido (el registro #1 queda marcado: es evidencia real) |
| H-12 | La dependencia *textfsm* de Netmiko instala un paquete `tests` que tapaba las pruebas | Pruebas automáticas | `tests/__init__.py` | `pytest`: 185 aprobadas | Corregido |
| H-13 | El nombre "R1:" (con dos puntos tras la fecha) no coincidía con el inventario | Prueba de carga | Se quitan los dos puntos del nombre | `test_hostname_con_dos_puntos_tras_fecha_rfc` | Corregido |
| H-14 | Un agente automatizado podía probar comandos en ráfaga y cambiar un equipo por fuera del NOC sin que nadie se enterara | Revisión de la pregunta de investigación | Defensa IA: pausa por ráfaga de comandos y detección de cambio sin aprobación | 5 pruebas de defensa en `test_corte3.py` | Corregido. Falta P-03 en el laboratorio |

## Limitaciones que siguen abiertas

- UDP sin cifrado ni autenticación del origen. TLS (RFC 5425) no se probó: los equipos del laboratorio no lo tienen configurado.
- Los equipos del laboratorio no tienen NTP; la hora es la puesta a mano.
- La aplicación se publica por HTTP en el laboratorio; en producción debe ir detrás de HTTPS (`NOC_COOKIE_SEGURA=1`).
- FortiGate y Huawei solo se probaron con datos simulados.
- La sesión SSH se abre y se cierra en cada comando; todavía no se ha medido cuánto tarda una consulta en los equipos reales.
