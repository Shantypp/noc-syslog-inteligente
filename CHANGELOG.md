# Historial de cambios

Formato basado en *Keep a Changelog*. Versiones según el plan del curso.

## [0.2.0] — MVP Corte 2

### Agregado
- Interfaz web (HTML/CSS/JS sin frameworks): dashboard, eventos, incidentes, inventario, configuraciones, consola, auditoría y seguridad IA.
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
