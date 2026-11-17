# Manual técnico · NOC Syslog Inteligente v1.0.0

Para quien instala, mantiene o modifica el sistema. El manual de uso diario está en
[manual-usuario.md](manual-usuario.md).

## 1. Qué es y cómo está hecho

Aplicación web que recibe Syslog de routers, switches y firewalls, lo guarda, detecta patrones,
propone incidentes y controla los cambios en los equipos con aprobación humana.

| Capa | Tecnología | Carpeta |
|---|---|---|
| Interfaz | HTML, CSS y JavaScript sin frameworks (módulos ES) | `app/web/` |
| API | Python 3.12+ con FastAPI y Uvicorn | `app/api/` |
| Recepción | Servidor UDP asíncrono (asyncio) | `app/collector/udp_server.py` |
| Análisis | Analizador RFC 3164 / RFC 5424 / Cisco real / FortiGate | `app/collector/parser.py` |
| Datos | SQLite en modo WAL | `app/database.py`, `data/noc.db` |
| Gestión de equipos | Netmiko (SSH) | `app/console/ssh.py` |
| Alertas | API de bots de Telegram (HTTPS) | `app/notificaciones/` |

### Flujo de un mensaje

```
Equipo ──UDP 5514──► udp_server ─► parser ─► controles (inventario, límite por equipo, repetidos, texto sospechoso)
                                                   │
                                                   ▼
                                      events (SQLite) ─► alerta Telegram si es grave
                                                   │
                         detecciones (fuerza bruta, fuera de horario, inestable, tormenta,
                         manipulación, cambio sin aprobación) ─► alerta Telegram si es nueva
                                                   │
                                      correlación con incidentes abiertos (recuperado)
```

Además, cada 10 s el monitoreo por ping (`collector/monitoreo.py`) revisa los equipos reales.

### Flujo de un comando en la consola

```
Usuario ─► /api/console/ejecutar ─► ¿ráfaga? (máx. 30/min) ─► simulator.evaluar (lista permitida por marca y rol)
     PERMITIDO ──► equipo con "Gestión por SSH" → ssh.consultar ; si no → salida simulada
     PROPUESTA ──► queda pendiente ─► otro administrador aprueba ─► ssh.aplicar_cambio (o simulado)
     BLOQUEADO / NO_VERIFICADO ──► no sale del NOC
     (todo queda en command_audit con hash SHA-256)
```

## 2. Instalación

Requisitos: Windows 10/11 o Linux, Python 3.12 o superior, Git. No requiere permisos de administrador.

```
git clone https://github.com/Shantypp/noc-syslog-inteligente.git
cd noc-syslog-inteligente
python iniciar.py          (o doble clic en iniciar-sistema.bat en Windows)
```

`iniciar.py` crea el entorno `.venv`, instala `requirements.txt` (solo si cambió), crea `.env`
a partir de `.env.example`, inicia el servidor y abre el navegador. La primera vez la aplicación
pide crear el usuario administrador.

| Modo | Comando | Recibe Syslog de |
|---|---|---|
| Laboratorio | `python iniciar.py` | Solo este computador (127.0.0.1) |
| Red | `python iniciar.py --red` | Los equipos de la red (0.0.0.0) |
| Automático | `iniciar-sistema.bat` (`--auto`) | Red si el computador está en la red de los equipos reales |

En modo red, Windows pregunta por el firewall la primera vez: hay que permitir **redes privadas**.

## 3. Configuración (`.env`)

El archivo `.env` **no se sube a GitHub** (`.gitignore`). Variables principales:

| Variable | Por defecto | Para qué |
|---|---|---|
| `NOC_DB_PATH` | `data/noc.db` | Archivo de la base de datos |
| `SYSLOG_UDP_HOST` / `SYSLOG_UDP_PORT` | `127.0.0.1` / `5514` | Dónde escucha el receptor |
| `SSH_USUARIO`, `SSH_CLAVE` | vacío | Credenciales SSH de los equipos con "Gestión por SSH". Vacío = consola simulada |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | vacío | Alertas por Telegram. Vacío = desactivadas |
| `NOC_COOKIE_SEGURA` | `0` | `1` cuando se publique con HTTPS |

Los umbrales (severidad de incidente, intervalo de ping, límite por minuto, detecciones,
máximo de comandos por minuto, alertas de Telegram) se cambian en la pantalla **Configuración**
sin reiniciar; cada cambio queda con usuario y fecha en la tabla `settings`.

### 3.1 Activar el gestor SSH

1. En el equipo: usuario local y SSH v2 (`username ... secret ...`, `ip ssh version 2`, `transport input ssh`).
2. En `.env`: `SSH_USUARIO=` y `SSH_CLAVE=` con ese usuario. Reiniciar el NOC.
3. En *Inventario*, editar el equipo: origen **Real** y "Gestión por SSH" = **Sí**.
4. En *Consola*, al elegir el equipo la barra se pone roja y dice **SSH REAL**.

Solo viajan al equipo las consultas de la lista permitida y los cambios que otro administrador aprobó.
La clave nunca llega al navegador, no se guarda en la base de datos y no aparece en los errores.

### 3.2 Activar Telegram

1. En Telegram, hablar con `@BotFather`, enviar `/newbot` y copiar el token que entrega.
2. Escribirle cualquier mensaje al bot nuevo y abrir `https://api.telegram.org/bot<TOKEN>/getUpdates` para ver el `chat.id`.
3. Escribir `TELEGRAM_BOT_TOKEN=` y `TELEGRAM_CHAT_ID=` en `.env` y reiniciar.
4. *Configuración › Alertas por Telegram › Enviar mensaje de prueba*.

Anti-inundación: la misma alerta no se repite antes de 5 minutos (configurable) y nunca se envían
más de 20 mensajes por minuto. Si Telegram no responde, el NOC sigue funcionando y el error queda
en el panel (sin el token).

## 4. Base de datos

SQLite con estas tablas principales (detalle en [modelo-datos.md](modelo-datos.md)):
`devices`, `events`, `incidents`, `incident_log`, `detecciones`, `command_audit`, `users`,
`sessions`, `login_attempts`, `settings`, `ingest_stats`.

Las columnas nuevas se agregan solas al iniciar (`COLUMNAS_NUEVAS` en `database.py`), así que
actualizar de versión no requiere scripts de migración. En v1.0.0 se agregaron
`devices.ssh_habilitado` y `command_audit.decidido_en`.

## 5. Operación y mantenimiento

| Tarea | Cómo |
|---|---|
| Respaldo | *Configuración › Descargar respaldo* o `python scripts/backup_db.py` |
| Restaurar | `python scripts/backup_db.py --restaurar ARCHIVO` con el NOC detenido |
| Retención | Automática al iniciar (90 días por defecto); los eventos ligados a incidentes se conservan |
| Integridad de la auditoría | Se verifica al abrir *Auditoría*, o `GET /api/auditoria/integridad` |
| Despliegue y rollback | [despliegue-rollback.md](despliegue-rollback.md) |
| Generar Syslog de prueba | `python scripts/enviar_syslog_prueba.py` (modo laboratorio) |

## 6. Pruebas

| Tipo | Comando | Resultado en v1.0.0 |
|---|---|---|
| Automáticas (unitarias e integración) | `python -m pytest` | 185 aprobadas |
| Carga básica | `python scripts/prueba_carga.py` | 3.000/3.000 a 500 msg/s; ~820 msg/s sostenidos |
| Respaldo y recuperación | `python scripts/prueba_respaldo.py` | 74/74 eventos recuperados |
| Despliegue y rollback | `python scripts/prueba_despliegue.py` | Sin pérdida de datos; rollback en 1,7 s |

Detalle en [pruebas.md](pruebas.md). Las pruebas nunca se conectan a equipos reales ni a Telegram:
Netmiko y la API de Telegram se reemplazan por versiones simuladas.

## 7. Seguridad (resumen)

- Secretos solo en `.env`; contraseñas de usuarios con PBKDF2-SHA256 y sal; sesión en cookie HttpOnly.
- Roles: lector (consulta), operador (gestiona incidentes y propone), administrador (aprueba cambios de otros, configura).
- Solo se aceptan eventos de equipos inventariados; límite por equipo y agrupación de repetidos.
- Los logs son datos: se muestran con `textContent` y nunca se usan como instrucciones.
- Auditoría con hash SHA-256 por registro; un equipo con auditoría no se puede borrar.
- Defensa frente a agentes automatizados: pausa por ráfaga de comandos y detección de cambios sin aprobación ([politica-ia.md](politica-ia.md)).

## 8. Estructura del código

```
app/
├── main.py              arranque, tareas de fondo (receptor UDP, ping) e interfaz web
├── config.py            parámetros editables
├── database.py          esquema SQLite y columnas nuevas
├── api/                 endpoints REST (auth, devices, events, incidents, console, sistema...)
├── collector/           parser, receptor UDP, ingreso, componentes y monitoreo por ping
├── security/            controles, inicio de sesión y roles, defensa IA
├── incidents/           política, detecciones y correlación
├── console/             lista permitida, gestor SSH y auditoría
├── notificaciones/      Telegram y qué se avisa
├── configgen/           plantillas Cisco / Fortinet / Huawei
└── web/                 interfaz
scripts/                 respaldo, generador de Syslog, pruebas de carga, respaldo y despliegue
tests/                   pruebas automáticas
docs/                    documentación y evidencias
```
