# Historial de cambios

Formato basado en *Keep a Changelog*. Versiones según el plan del curso.

## [0.2.0] — MVP Corte 2

### Agregado
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
