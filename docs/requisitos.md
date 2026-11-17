# Requisitos · NOC Syslog Inteligente v1.0.0

Prioridad **MoSCoW**: M = debe · S = debería · C = podría · W = no en esta versión.
Estado: ✅ implementado y probado · 🟡 parcial · ⏳ Corte 3.

## Problema, objetivos y alcance

**Problema.** Una red multivendor (Cisco, Fortinet, Huawei) genera eventos en formatos distintos; sin un punto central el operador no ve el estado de la red, los eventos críticos se pierden, los incidentes no tienen responsable ni tiempos y los cambios —incluidos los sugeridos por una IA— no tienen trazabilidad.

**Objetivo general.** Desarrollar una aplicación web NOC que reciba, normalice y clasifique eventos Syslog multivendor, gestione incidentes y prepare configuraciones seguras, aplicando controles contra acciones no autorizadas de agentes de IA.

**Objetivos específicos.**
1. Mantener un inventario editable de dispositivos con fecha de actualización.
2. Recibir/importar Syslog y clasificarlo por equipo, marca, fecha, facility y severidad 0–7.
3. Visualizar estado, eventos e incidentes en un dashboard con filtros, priorizando lo que requiere atención.
4. Gestionar el ciclo de vida de incidentes.
5. Generar configuraciones Syslog comentadas para Cisco, Fortinet y Huawei.
6. Ofrecer una consola simulada de solo lectura con lista permitida y auditoría.
7. Implementar una política de defensa frente a agentes de IA.
8. Detectar automáticamente patrones entre eventos (ataques, cambios fuera de horario, inestabilidad) y relacionarlos con los incidentes.
9. Facilitar la instalación y la operación: arranque en un paso, configuración desde la aplicación y ayuda integrada.

**Alcance v0.2.0.** Las funciones anteriores con datos **simulados** (IPs 192.0.2.0/24) en laboratorio local.
**Fuera de alcance (Corte 3).** Telegram, SSH real vía backend, TLS, marcha blanca, despliegue.

## Requisitos funcionales

| ID | Requisito | Prior. | Criterio de aceptación | Historia | Prueba | Estado |
|---|---|---|---|---|---|---|
| RF-01 | Registrar y editar inventario (nombre, IP, marca, modelo, versión, ubicación, estado, fecha de actualización) | M | CRUD completo; IP inválida → 422; IP duplicada → 409; `actualizado_en` cambia al editar | HU-01 | `test_devices.py` | ✅ |
| RF-02 | Recibir (UDP) o importar (archivo) mensajes Syslog | M | Importar `muestras_simuladas.log` → 14 guardados, 1 duplicado, 1 fuente no autorizada, 1 inválido | HU-02 | `test_ingest.py` | ✅ |
| RF-03 | Normalizar fecha, IP, marca, facility, severidad y mensaje | M | `<187>` → facility 23 (local7), severidad 3 | HU-02 | `test_parser.py` | ✅ |
| RF-04 | Dashboard con estado, eventos recientes, críticos e incidentes; filtros por fecha, marca, equipo y severidad | M | Severidad 0–3 + Cisco sobre el dataset → total = 3 | HU-01, HU-02 | `test_dashboard_incidents.py` | ✅ |
| RF-05 | Abrir, asignar, actualizar y cerrar incidentes | M | ID, estado, responsable, tiempos, SLA, vínculo al evento y seguimiento; cierre exige causa y solución | HU-03 | `test_dashboard_incidents.py` | ✅ |
| RF-06 | Generar configuraciones Syslog comentadas por fabricante | M | Usa IP y umbral elegidos, comentarios, advertencia de versión, verificación y reversa | HU-04 | `test_configgen_console.py` | ✅ |
| RF-07 | Terminal segura simulada | M | `show version` permitido; `reload` bloqueado; `configure terminal` = propuesta; IOS en ROMMON = no verificado | HU-05 | `test_configgen_console.py` | ✅ |
| RF-08 | Auditoría y exportación de evidencia | M | Todo comando con usuario, fecha, equipo, decisión, hash; CSV exportable; integridad verificable | HU-05 | `test_configgen_console.py` | ✅ |
| RF-10 | Inicio de sesión por usuario y permisos por rol (lector, operador, administrador), incluidos los comandos que cada rol puede aplicar | M | Sin sesión → 401; acción de rol insuficiente → 403; lector no propone cambios; solo un administrador aprueba, y no lo suyo | HU-09, HU-10 | `test_auth_roles.py` | ✅ |
| RF-11 | Identificar qué parte del equipo genera el problema (puerto, fuente, sensor, túnel, clúster) | M | `Interface Gi0/2 ... down` → GigabitEthernet0/2 · Caído; el panel muestra "dónde está el problema" | HU-11 | `test_puertos.py` | ✅ |
| RF-12 | Detectar patrones entre eventos: fuerza bruta, cambio de configuración fuera de horario, puerto inestable, tormenta por equipo y manipulación | M | 5 inicios fallidos desde la misma IP en 5 min → detección (aunque sean repetidos); cada detección se convierte en incidente o se descarta con motivo | HU-12, HU-13, HU-14 | `test_operacion.py` | ✅ |
| RF-13 | Relacionar los eventos con el incidente abierto de la misma parte del equipo y detectar su recuperación | M | Un "up" del componente agrega el evento al historial (usuario "sistema") y marca el incidente *Recuperado*; no se repite la propuesta | HU-15 | `test_operacion.py` | ✅ |
| RF-14 | Configurar el sistema desde la aplicación: umbrales, horario laboral, respaldo, retención y datos de demostración | M | Cambio válido se aplica sin reiniciar y registra quién lo hizo; valores fuera de rango → 422; solo administrador | HU-16 | `test_operacion.py` | ✅ |
| RF-15 | Priorizar el trabajo: bandeja "Requiere su atención", ficha por equipo, búsqueda de texto, exportación CSV y avisos en vivo | S | La bandeja ordena SLA vencidos, detecciones, propuestas, aprobaciones y equipos sin comunicación; `%` y `_` se buscan literalmente; CSV protegido contra fórmulas | HU-01, HU-02 | `test_operacion.py` | ✅ |
| RF-16 | Saber si cada equipo real está vivo aunque no envíe mensajes, y no dar falsas alarmas si el NOC pierde la red | M | Ping cada 10 s; caído tras 3 fallos (≤ 30 s); sin red de gestión → un solo aviso y ningún equipo caído | HU-01 | `test_monitoreo.py`, `test_corte3.py` | ✅ (real: 5/5 caídas, 19–24 s) |
| RF-17 | Gestionar equipos reales por SSH desde el backend con lista de hosts permitidos, roles, comandos permitidos y aprobación humana | M | Solo equipos reales con "Gestión por SSH"; consultas de la lista permitida; cambios solo tras aprobación de otro administrador; credenciales en `.env`; todo auditado | HU-05 | `test_corte3.py` | 🟡 (probado con Netmiko simulado; falta laboratorio) |
| RF-18 | Avisar por Telegram las caídas, detecciones nuevas y eventos graves sin exponer el token | S | Token solo en `.env` y enmascarado; misma alerta no se repite en 5 min; máx. 20 por minuto | HU-01 | `test_corte3.py` | 🟡 (probado con Telegram simulado; falta bot real) |
| RF-09 | Notificación por Telegram | W | Una alerta por incidente, token enmascarado, sin inundar | — | — | ⏳ |

## Requisitos no funcionales

| ID | Atributo | Requisito | Cómo se cumple | Estado |
|---|---|---|---|---|
| RNF-01 | Seguridad | Secretos fuera del código | `.env` + `.gitignore`; `.env.example` sin valores; contraseñas cifradas (PBKDF2) | ✅ |
| RNF-02 | Usabilidad | Navegación comprensible | Menú lateral, bandeja priorizada, colores por severidad, textos en español, ayuda integrada por rol, diseño adaptable a celular | ✅ |
| RNF-03 | Trazabilidad | Cada evento/acción con fecha y actor | `recibido_en`, `incident_log`, `command_audit` con usuario y fecha | ✅ |
| RNF-04 | Confiabilidad | Errores controlados y bitácora | Validaciones (422/404/409), el receptor UDP no cae ante mensajes malos, `logging` | ✅ |
| RNF-05 | Portabilidad | Instalación desde cero | `iniciar-sistema.bat` / `iniciar.py` (un paso), configuración inicial en la aplicación, README | ✅ |
| RNF-06 | Mantenibilidad | Módulos y nombres claros | Paquetes `collector`, `security`, `incidents`, `configgen`, `console`, `api`, `notificaciones`, `web`; 185 pruebas | ✅ |
| RNF-07 | Rendimiento | El tablero no se bloquea con el volumen de prueba | Índices, paginación, límite por equipo, WAL; prueba de carga: 3.000/3.000 a 500 msg/s, ~820 msg/s sostenidos, panel con mediana de 36 ms | ✅ |
| RNF-08 | Recuperación | Copia y rollback | Respaldo y restauración probados (74/74 eventos); despliegue y rollback ensayados ([despliegue-rollback.md](despliegue-rollback.md)) | ✅ |
| RNF-09 | Seguridad IA | Logs nunca como instrucciones; contener y detectar acciones de agentes | Ver [politica-ia.md](politica-ia.md): ráfaga de comandos, cambio sin aprobación | ✅ |
