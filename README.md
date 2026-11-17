# NOC Syslog Inteligente · v1.0.0

> Proyecto académico · **Administración y Gestión de Redes** · Periodo 2026-2
> Docente: Ing. John Harold Pérez Calderón · **Trabajo realizado por Valentina Gutiérrez y Jhoan Santiago Pachón Perilla**
>
> **Datos:** los ejemplos y las pruebas automáticas del repositorio son **SIMULADOS** (IPs de documentación `192.0.2.0/24`, RFC 5737).
> La marcha blanca con equipos **reales** (4 Cisco del laboratorio, red 192.168.50.0/24) está en [docs/bitacora-marcha-blanca.md](docs/bitacora-marcha-blanca.md);
> cada entrada dice si fue real o simulada. La base de datos con los datos reales no se sube.

![Panel general con la bandeja "Requiere su atención"](docs/evidencias/E05-dashboard.png)

## Problema que resuelve

Una red con equipos de varios fabricantes (Cisco, Fortinet, Huawei) produce eventos en formatos distintos. Sin un punto central, el operador no ve el estado de la red, los eventos críticos se pierden, los incidentes no tienen responsable ni tiempos y cualquier cambio —incluido uno sugerido por una IA— queda sin trazabilidad.

**NOC Syslog Inteligente** recibe y clasifica eventos Syslog, muestra el estado de la red, gestiona incidentes, genera configuraciones Syslog comentadas y ofrece una consola controlada, aplicando una política explícita de defensa frente a acciones no autorizadas de agentes de IA.

## Funciones

| # | Función | Requisito | Dónde |
|---|---|---|---|
| 1 | Inventario editable de equipos (nombre, IP, marca, modelo, versión, ubicación, estado, fecha de actualización) | RF-01 | Inventario de equipos |
| 2 | Recepción Syslog por UDP e importación de archivos `.log` | RF-02 | Eventos |
| 3 | Clasificación por equipo, fabricante, fecha, facility y severidad 0–7 (RFC 3164 y RFC 5424) | RF-03 | Eventos |
| 4 | Panel general: flujo de trabajo guiado, estado de equipos, eventos recientes, críticos e incidentes | RF-04 | Panel general |
| 5 | Filtros por fecha, marca, equipo y severidad con total | RF-04 | Eventos |
| 6 | Incidentes: propuesta por política, creación, asignación, seguimiento, SLA y cierre | RF-05 | Incidentes |
| 7 | Generador de configuraciones Syslog comentadas para Cisco, Fortinet y Huawei | RF-06 | Plantillas de configuración |
| 8 | Consola tipo PuTTY con allowlist, bloqueos y modos (ROMMON): simulada por defecto y **SSH real por el backend** en los equipos habilitados | RF-07 | Consola de equipos |
| 9 | Auditoría con hash SHA-256, revisión humana de propuestas y exportación CSV | RF-08 | Auditoría |
| 10 | Política de defensa frente a agentes de IA con evidencia en vivo | RNF-09 | Política de seguridad |
| 11 | **Inicio de sesión por usuario** y **roles** (lector, operador, administrador) que definen qué puede ver, atender y qué comandos puede aplicar | RF-10 | Usuarios |
| 12 | **Puertos y componentes**: identifica qué parte del equipo genera el problema (puerto, fuente de poder, sensor, túnel VPN, clúster HA) | RF-11 | Puertos y componentes |
| 13 | **Detecciones automáticas** (correlación de eventos): fuerza bruta, cambios fuera de horario, puerto inestable (flapping), tormenta por equipo, manipulación en logs | RF-12 | Detecciones |
| 14 | **Correlación con incidentes**: un evento nuevo de la misma parte del equipo se suma al incidente abierto; si se recupera, el incidente se marca "Recuperado" | RF-13 | Incidentes |
| 15 | **"Requiere su atención"**: bandeja priorizada (SLA vencidos, detecciones, propuestas, aprobaciones, equipos caídos, recuperados) | RF-15 | Panel general |
| 16 | **Ficha de equipo**: estado, partes con problema, incidentes, detecciones, actividad 24 h y eventos de un equipo | RF-15 | Clic en cualquier equipo |
| 17 | **Configuración en la aplicación**: umbrales y horario laboral sin editar archivos; estado del colector; respaldo descargable; retención; datos de demostración | RF-14 | Configuración |
| 18 | Búsqueda de texto, "Cargar más" y **exportación a Excel (CSV)** de eventos e incidentes; descartar propuestas con motivo | RF-15 | Eventos · Incidentes |
| 19 | **Avisos en vivo** de eventos graves y detecciones nuevas (cada 15 s) y **Ayuda** integrada (por rol, conectar equipos, preguntas frecuentes) | RF-15, RNF-02 | Toda la interfaz · Ayuda |
| 20 | **Instalación en 1 paso** (`iniciar-sistema.bat`) y **configuración inicial** en la app (crear el primer administrador sin tocar archivos) | RNF-05 | `iniciar-sistema.bat` |
| 21 | **Monitoreo por ping** de los equipos reales cada 10 s: caída en ≤ 30 s y recuperación; un solo aviso si el NOC pierde la red de gestión | RF-16 | Panel general |
| 22 | **Gestor SSH** (Netmiko): lista de hosts permitidos, consultas de solo lectura y cambios aprobados por otro administrador, todo auditado | RF-17 | Consola · Inventario |
| 23 | **Alertas por Telegram** de caídas, detecciones nuevas y eventos graves, con anti-inundación y token fuera del código | RF-18 | Configuración |
| 24 | **Defensa frente a agentes automatizados o de IA**: pausa por ráfaga de comandos y detección de cambios hechos por fuera del NOC | RNF-09 | Detecciones · Configuración |

## Arquitectura

```mermaid
flowchart LR
    subgraph F["Fuentes (SIMULADAS)"]
        C[Cisco IOS XE] & FG[FortiGate] & H[Huawei VRP] & A[Archivo .log]
    end
    R[collector<br/>UDP 5514 + importador] --> P[parser<br/>RFC 3164 / 5424]
    P --> V[security<br/>allowlist · dedup · rate limit · sospechosos]
    V --> DB[(SQLite)]
    V --> POL[policy<br/>sev 0-2 → propuesta]
    DB <--> API[FastAPI /api]
    API <--> UI[Web HTML/CSS/JS]
    UI --> CON[consola simulada] --> AUD[(auditoría + hash)]
    C & FG & H --> R
    A --> R
```

Más detalle en [docs/arquitectura.md](docs/arquitectura.md) y [docs/modelo-datos.md](docs/modelo-datos.md).

**Flujo seguro obligatorio:** evento detectado → validación → propuesta de acción → revisión humana → aprobación → ejecución autorizada → verificación → auditoría.

## Requisitos previos

- Windows 10/11, Linux o macOS
- **Python 3.12 o superior** (probado con 3.14)
- Git

## Instalación en 1 paso

1. Instale **Python 3.12 o superior** desde [python.org](https://www.python.org/downloads/) (marque *Add python.exe to PATH*).
2. Descargue el proyecto (`git clone https://github.com/Shantypp/noc-syslog-inteligente.git` o *Code › Download ZIP*).
3. **Windows:** doble clic en **`iniciar.bat`** · **Linux/macOS:** `python3 iniciar.py`

`iniciar.py` crea el entorno virtual, instala las dependencias (solo la primera vez o si cambian), crea `.env`, inicia el servidor y abre el navegador. La primera vez la aplicación pide **crear el usuario administrador** y ofrece cargar datos de demostración: no hay que editar ningún archivo.

| Para… | Use |
|---|---|
| Laboratorio (solo este computador) | `iniciar.bat` o `python iniciar.py` |
| Recibir Syslog de routers y firewalls de la red | `iniciar-red.bat` o `python iniciar.py --red` |
| Otro puerto web | `python iniciar.py --puerto 8080` |
| Desarrollo (recarga al editar) | `python iniciar.py --desarrollo` |

Para detener: **Ctrl+C** en la ventana del NOC. Si ya está abierto, `iniciar.bat` solo abre el navegador.

<details><summary>Instalación manual (alternativa)</summary>

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                # Linux/macOS: cp .env.example .env
uvicorn app.main:app --reload
```
Opcional: `python -m app.seed` carga equipos simulados y, si define `NOC_CLAVE_INICIAL` en `.env`, 4 usuarios de laboratorio.
</details>

## Configuración (`.env`)

| Variable | Por defecto | Significado |
|---|---|---|
| `NOC_DB_PATH` | `data/noc.db` | Archivo de base de datos |
| `SYSLOG_UDP_ENABLED` | `1` | Encender el receptor UDP |
| `SYSLOG_UDP_HOST` | `127.0.0.1` | Solo este equipo (laboratorio seguro) |
| `SYSLOG_UDP_PORT` | `5514` | Puerto alto: no requiere administrador |
| `DEDUP_WINDOW_SECONDS` | `60` | Ventana para agrupar repetidos |
| `RATE_LIMIT_PER_MINUTE` | `300` | Máximo de mensajes por minuto **por equipo** |
| `INCIDENT_MAX_SEVERITY` | `2` | Severidad que genera propuesta de incidente |
| `NO_COMM_MINUTES` | `10` | Minutos sin eventos para "sin comunicación" |
| `NOC_CLAVE_INICIAL` | *(vacío)* | Opcional: contraseña de los usuarios de laboratorio que crea `app.seed` |
| `NOC_COOKIE_SEGURA` | `0` | `1` si se publica con HTTPS (la cookie de sesión solo viaja cifrada) |
| `SSH_USUARIO` / `SSH_CLAVE` | *(vacío)* | Credenciales SSH de los equipos con "Gestión por SSH". Vacío = consola simulada |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | *(vacío)* | Alertas por Telegram. Vacío = desactivadas |

El archivo `.env` **nunca** se sube a GitHub (está en `.gitignore`). Los umbrales (severidad de incidente, minutos sin comunicación, ventana de repetidos, límite por equipo, fuerza bruta, puerto inestable, horario laboral, zona horaria y días de retención) se cambian desde **Configuración** en la aplicación; el `.env` solo define el valor por defecto.

## Ejecución

Con `iniciar.bat` / `python iniciar.py` (ver arriba) o manualmente con `uvicorn app.main:app --reload`.

- Interfaz web: **http://127.0.0.1:8000**
- Documentación de la API: **http://127.0.0.1:8000/docs**

En otra terminal, simula equipos enviando Syslog:

```powershell
python scripts/enviar_syslog_prueba.py              # envía data/muestras_simuladas.log
python scripts/enviar_syslog_prueba.py --tormenta   # 500 mensajes iguales (prueba de deduplicación)
python scripts/enviar_syslog_prueba.py --puerto 5599 # si el colector usa otro puerto UDP
```

La interfaz está organizada en el orden de trabajo del operador: **Operación** (panel general, detecciones, incidentes, eventos, puertos) → **Administración** (inventario, plantillas, usuarios, configuración) → **Control de cambios** (consola, auditoría) → **Cumplimiento** (política de seguridad) → **Ayuda**. El panel general empieza con **"Requiere su atención"**: lo que hay que hacer ahora, en orden de prioridad, con un enlace a la pantalla que lo resuelve.

## Usuarios y roles

Cada persona entra con su usuario. Lo que puede hacer depende de su **rol**, y el servidor lo verifica en cada acción (no solo la pantalla):

| Rol | Puede |
|---|---|
| **Lector** | Ver todo. Consola: solo consultas básicas (`show version`, `show ip interface brief`) |
| **Operador** | Lo anterior + abrir, gestionar y cerrar incidentes, importar eventos, consultas de configuración de logs y **proponer** cambios |
| **Administrador** | Todo + inventario, usuarios y **aprobar o rechazar** cambios propuestos por *otro* usuario |

El **primer administrador** se crea en la pantalla de configuración inicial (solo aparece cuando no hay usuarios y solo desde el mismo computador). Opcional: `python -m app.seed` crea usuarios de laboratorio (`jpachon`, `supervisor`, `operador`, `consulta`) con la contraseña de `NOC_CLAVE_INICIAL`.

- Cambiar la propia contraseña: botón **Cambiar contraseña** arriba a la derecha.
- Crear usuarios o cambiar roles: pantalla **Usuarios** (administrador).
- Desde la terminal: `python -m app.usuarios listar` · `python -m app.usuarios clave USUARIO` · `python -m app.usuarios crear USUARIO --nombre "..." --rol operador`
- Tras 5 intentos fallidos en 15 minutos, la cuenta se bloquea temporalmente.

## Pruebas

```powershell
python -m pytest -v
```

185 pruebas automáticas (en v0.2.0 eran 138): inicio de sesión y roles, parser (incluido el formato real de Cisco), inventario, ingreso y límite por equipo, monitoreo por ping, detecciones, correlación, panel, incidentes, configuración, respaldo, consola, gestor SSH y Telegram (simulados), red de gestión y defensa IA.

Pruebas que se ejecutan aparte (datos simulados, base temporal; no tocan `data/noc.db`):

```powershell
python scripts/prueba_carga.py        # carga: 3.000 mensajes a 500 msg/s, tormenta y panel bajo carga
python scripts/prueba_respaldo.py     # respaldo, daño de la base y restauración
python scripts/prueba_despliegue.py   # v0.2.0 -> versión nueva -> rollback
```

Resultados y evidencias en [docs/pruebas.md](docs/pruebas.md) y `docs/evidencias/`.

## Respaldo y recuperación

Desde la aplicación: **Configuración › Mantenimiento › Descargar respaldo** (copia consistente aunque el servidor esté recibiendo eventos). Desde la terminal:

```powershell
python scripts/backup_db.py                      # crea data/backups/noc-AAAAMMDD-HHMMSS.db
python scripts/backup_db.py --listar
python scripts/backup_db.py --restaurar data/backups/noc-....db   # con el servidor apagado
```

Despliegue y rollback paso a paso (ensayado): [docs/despliegue-rollback.md](docs/despliegue-rollback.md).

## Seguridad

- Secretos fuera del código (`.env`), nunca en GitHub.
- Inicio de sesión: contraseñas cifradas con PBKDF2-SHA256 y sal; sesión en cookie HttpOnly; bloqueo tras 5 intentos fallidos.
- Control de acceso por rol en el servidor; la identidad de quien actúa sale de la sesión, nunca de lo que envía el navegador.
- **Los logs son datos no confiables**: se guardan y muestran como texto (`textContent`), nunca se ejecutan ni se usan como instrucciones para una IA. Los intentos de inyección se marcan como *sospechosos*.
- Solo se aceptan eventos de equipos inventariados; deduplicación y límite por minuto **por equipo** contra tormentas (un equipo ruidoso no silencia a los demás).
- Detecciones automáticas de fuerza bruta, cambios fuera de horario y manipulación; el sistema propone y una persona decide.
- La configuración inicial solo se acepta una vez y desde el mismo computador.
- Consola: denegar por defecto; los cambios quedan como **propuesta** que otra persona debe aprobar. El SSH real lo hace solo el backend, en los equipos de la lista permitida, con credenciales que viven en `.env`.
- Telegram: token solo en `.env`, enmascarado en la API y borrado de los mensajes de error; anti-inundación.
- Defensa IA: pausa por ráfaga de comandos y detección de cambios en los equipos que nadie aprobó en el NOC.
- Auditoría con hash SHA-256 por registro y verificación de integridad.

Política completa: [docs/politica-ia.md](docs/politica-ia.md).

## Limitaciones conocidas (v1.0.0)

- UDP sin cifrado ni autenticación del origen; TLS (RFC 5425) no se probó porque los equipos del laboratorio no lo tienen.
- Los equipos del laboratorio no tienen NTP (hora puesta a mano).
- En laboratorio la aplicación usa HTTP; en producción debe publicarse con HTTPS (`NOC_COOKIE_SEGURA=1`).
- FortiGate y Huawei solo se probaron con datos simulados; Cisco se probó con equipos reales.
- El gestor SSH y las alertas de Telegram están probados con pruebas automáticas; la prueba con los equipos y el bot reales está pendiente (ver bitácora, P-01 a P-05).
- Las detecciones usan reglas de texto y umbrales; no hay aprendizaje automático.

Hallazgos y correcciones: [docs/hallazgos.md](docs/hallazgos.md).

## Estructura

```
app/
├── main.py            arranque de FastAPI + interfaz web
├── config.py          parámetros editables desde la aplicación
├── mantenimiento.py   retención y respaldo
├── database.py        SQLite y modelo de datos
├── models.py          validaciones (Pydantic)
├── api/               endpoints REST
├── collector/         parser, receptor UDP, ingreso, componentes y monitoreo por ping
├── security/          controles, inicio de sesión y roles, defensa IA
├── incidents/         política (propuestas, SLA), detecciones automáticas y correlación
├── configgen/         plantillas Cisco / Fortinet / Huawei
├── console/           lista permitida, gestor SSH y auditoría
├── notificaciones/    alertas por Telegram
└── web/               HTML, CSS y JavaScript
data/                  muestras SIMULADAS (la BD no se sube)
docs/                  manuales, políticas Syslog, despliegue, bitácora, hallazgos, pruebas y evidencias
scripts/               generador de Syslog, respaldo y pruebas de carga, respaldo y despliegue
tests/                 pruebas automáticas (pytest)
iniciar.py · iniciar-sistema.bat · iniciar.bat · iniciar-red.bat   arranque en 1 paso
```

## Autores, versión y licencia

Trabajo realizado por **Valentina Gutiérrez y Jhoan Santiago Pachón Perilla** · versión **1.0.0** · Uso académico (ver [LICENSE](LICENSE)).
Desarrollado con asistencia de IA como herramienta; el código fue ejecutado, probado y revisado por los autores. Historial de cambios en [CHANGELOG.md](CHANGELOG.md).

Documentación: [manual técnico](docs/manual-tecnico.md) · [manual de usuario](docs/manual-usuario.md) · [políticas Syslog](docs/politicas-syslog.md) · [política IA](docs/politica-ia.md) · [despliegue y rollback](docs/despliegue-rollback.md) · [bitácora](docs/bitacora-marcha-blanca.md) · [hallazgos](docs/hallazgos.md) · [pruebas](docs/pruebas.md).
