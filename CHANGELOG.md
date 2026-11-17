# Historial de cambios

Formato basado en *Keep a Changelog*. Versiones según el plan del curso.

## [1.0.0] — Corte 3 · 16-nov-2026

### Agregado
- **Monitoreo por ping** de los equipos reales (cada 10 s, caído tras 3 fallos, recuperación automática del incidente). Probado con 4 equipos Cisco reales el 21-oct.
- **Analizador del formato real de Cisco** (número de secuencia, hora de encendido, hostname opcional) y FortiGate clave=valor.
- **Gestor SSH por el backend** (Netmiko): lista de hosts permitidos ("Gestión por SSH" en el inventario), solo consultas permitidas y cambios aprobados por otro administrador; credenciales en `.env`; indicador "SSH REAL" en la consola.
- **Alertas por Telegram**: caídas y recuperaciones, pérdida de la red de gestión, detecciones nuevas y eventos graves; anti-inundación; token enmascarado; botón de mensaje de prueba.
- **Defensa frente a agentes automatizados o de IA**: pausa de la consola por ráfaga de comandos y detección "cambio sin aprobación" cuando un equipo informa un cambio que nadie aprobó en el NOC.
- `iniciar-sistema.bat`: decide solo entre modo red y laboratorio.
- Scripts de prueba: `prueba_carga.py`, `prueba_respaldo.py`, `prueba_despliegue.py`, con resultados en `docs/evidencias/`.
- Documentación: manual técnico, manual de usuario, políticas Syslog verificadas, despliegue y rollback, bitácora de marcha blanca y hallazgos.

### Cambiado
- Un solo aviso "El NOC no está conectado a la red de gestión" en lugar de N equipos caídos (hallazgo H-07).
- Receptor UDP: una conexión de base de datos reutilizada, registro por mensaje en DEBUG y búfer de 8 MB (de 10,3 % a 0 % de pérdida a 500 msg/s).
- Un equipo con registros de auditoría no se puede eliminar (se marca Inactivo) para no alterar la evidencia.

### Corregido
- `backup_db.py`: nombres de respaldo repetidos en el mismo segundo, conexiones sin cerrar (archivo bloqueado en Windows) y archivos `-wal` viejos al restaurar.
- El nombre "R1:" con dos puntos después de la fecha RFC no coincidía con el inventario.
- Las pruebas no se encontraban al instalar Netmiko (paquete `tests` de textfsm).

## [0.2.0] — MVP Corte 2

### Agregado — operación y facilidad de uso
- **Instalación en 1 paso**: `iniciar.py` (multiplataforma) e `iniciar.bat` / `iniciar-red.bat` (doble clic en Windows). Crea el entorno, instala dependencias solo si cambiaron, crea `.env`, inicia y abre el navegador.
- **Configuración inicial** en la aplicación: si no hay usuarios, se crea el primer administrador desde el navegador (una sola vez y solo desde el mismo computador), con opción de cargar la demostración.
- **Detecciones automáticas** (tabla `detecciones`): fuerza bruta (por IP de origen, cuenta también los repetidos), cambio de configuración fuera de horario, puerto inestable (flapping), tormenta por equipo y manipulación en logs. Se revisan en la nueva pantalla *Detecciones*: abrir incidente o descartar con motivo.
- **Correlación con incidentes**: los eventos nuevos de la misma parte del equipo se agregan al historial del incidente abierto (usuario "sistema"); si el componente vuelve a "Arriba", el incidente se marca *Recuperado* y se sugiere cerrarlo.
- Bandeja **"Requiere su atención"** en el panel general, ordenada por prioridad y con enlace a la pantalla que resuelve cada asunto.
- **Ficha de equipo** (`#equipo/ID`) con estado, componentes, incidentes, detecciones, actividad de 24 h y últimos eventos; los nombres de equipo son enlaces a su ficha.
- Pantalla **Configuración** (administrador): parámetros editables sin reiniciar (tabla `settings`, con quién y cuándo), estado del colector UDP, respaldo descargable, retención y datos de demostración.
- **Avisos en vivo** cada 15 s de eventos graves y detecciones nuevas, y contadores del menú actualizados (`/api/novedades`).
- Eventos: búsqueda de texto, "Cargar más", filtros que se aplican solos y exportación CSV con los filtros actuales. Incidentes: exportación CSV y descarte de propuestas con motivo.
- Página de **Ayuda**: guía por rol, cómo conectar equipos reales (Cisco, FortiGate, Huawei con la IP de este computador), severidades y preguntas frecuentes.
- Contadores de ingreso persistentes por día (tabla `ingest_stats`) y retención automática al iniciar.
- Diseño adaptable a celular.

### Cambiado — operación y facilidad de uso
- El límite de mensajes por minuto ahora es **por equipo**: una tormenta de un router ya no silencia a los demás.
- La deduplicación ya no agrupa un puerto que cae, sube y vuelve a caer: cada cambio de estado se guarda.
- Las propuestas excluyen los eventos de una parte del equipo que ya tiene incidente abierto e indican si "ya se recuperó".
- Umbrales leídos de la configuración (antes constantes del `.env`).
- Estado de puertos y componentes calculado con una sola consulta agrupada; SQLite en modo WAL (lecturas y escrituras simultáneas).

### Agregado — funciones base del MVP
- Interfaz web administrativa (HTML/CSS/JS sin frameworks), con menú en el orden de trabajo: Operación (panel general, eventos, incidentes), Administración (inventario, plantillas), Control de cambios (consola, auditoría) y Cumplimiento (política de seguridad).
- Panel general con el flujo de trabajo del operador en 4 pasos y contadores de tareas pendientes en el menú.
- Formularios propios (registrar equipo, abrir/gestionar/cerrar incidente, aprobar/rechazar cambios) en lugar de las ventanas del navegador.
- Opción `--puerto` en el generador de Syslog de prueba.
- Inicio de sesión por usuario (contraseñas PBKDF2, cookie HttpOnly, bloqueo tras 5 intentos) y gestión de usuarios.
- Permisos por rol (lector, operador, administrador) en toda la API y en la consola: cada rol tiene sus comandos permitidos; el lector no propone cambios; solo un administrador distinto aprueba.
- Puertos y componentes: identifica qué parte del equipo genera el problema y lo muestra en eventos, incidentes y panel general.
- Filtros de eventos por fecha, marca, equipo y severidad con conteo total.
- Política de incidentes: eventos 0–2 generan propuesta; creación, asignación, seguimiento (incident_log), SLA y cierre con causa/solución.
- Estado "sin comunicación" por equipo según el último evento (HU-01).
- Generador de configuraciones Syslog comentadas para Cisco IOS/IOS XE, FortiOS y Huawei VRP, con verificación y reversa.
- Consola tipo PuTTY simulada: allowlist por perfil (incluye ROMMON), bloqueos, propuestas y comandos no verificados.
- Auditoría con hash SHA-256, revisión humana con separación de funciones, verificación de integridad y exportación CSV.
- Módulo de política de defensa frente a agentes de IA con evidencia en vivo.
- Script de respaldo/restauración de la base de datos.
- Documentación en `docs/`.

## [0.1.x] — Alfa
- Estructura del proyecto, modelo SQLite y primeras pruebas (v0.1.0).
- CRUD de inventario con validación de IP, marca e IP duplicada.
- Parser RFC 3164/5424, receptor UDP, importador, deduplicación, allowlist, rate limit y detección de mensajes sospechosos.
