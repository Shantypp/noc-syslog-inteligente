# Historial de cambios

Formato basado en *Keep a Changelog*. Versiones según el plan del curso.

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
