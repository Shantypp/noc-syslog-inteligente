# Bitácora de marcha blanca · NOC Syslog Inteligente

Registro de lo que se hizo con el sistema funcionando. Cada entrada dice si los datos fueron
**REALES** (equipos físicos del laboratorio) o **SIMULADOS** (generados en el computador).
Las horas están en hora de Colombia (COT, UTC−5). Lo que todavía no se ha hecho aparece como
**PENDIENTE**: no se registra ningún resultado que no se haya observado.

## Entorno

| Elemento | Detalle |
|---|---|
| Servidor NOC | Portátil Windows 11, Python 3.14, IP 192.168.50.10 (reserva DHCP en R1-LAB) |
| Red de gestión | 192.168.50.0/24, cable directo PC → SW-CORE |
| Equipos reales | R1-LAB 192.168.50.1 (Cisco 1941, DHCP), R2-LAB .2 (Cisco 1941), SW-CORE .3 (Catalyst 3650-24), SW-ACCESO .4 (Catalyst de 48 puertos) |
| Acceso a los equipos | Consola (cable USB-serial) y SSH v2 con usuario local |

## Entradas

### MB-01 · 16-oct-2026 · REAL · Primer equipo real (Cisco 8200)
- **Qué se hizo:** se configuró un router Cisco 8200 para enviar Syslog al NOC y se entró al modo configuración.
- **Resultado:** 5 mensajes reales recibidos. El cambio de configuración (`%SYS-5-CONFIG_I`) se registró a las 19:55 y la regla *fuera de horario* lo marcó; a las 20:02 se abrió con él el incidente #1.
- **Hallazgo:** el formato real de Cisco trae número de secuencia y fecha propia, y los mensajes no se agrupaban bien → H-03 (corregido en el analizador).

### MB-02 · 21-oct-2026 · REAL · Laboratorio de 4 equipos Cisco
- **Qué se hizo:** se configuraron los 4 equipos con la política de `docs/politicas-syslog.md` (bloques 1 y 2) y se dejó el NOC en modo red.
- **Resultado:** 51 mensajes Syslog reales de los 4 equipos (SW-CORE 32, SW-ACCESO 17, R1-LAB 1, R2-LAB 1), todos reconocidos con su nombre y hora.
- **Hallazgo:** los equipos sanos casi no envían mensajes y el panel los mostraba "sin comunicación" → H-04: se agregó el monitoreo por ping (cada 10 s, caído tras 3 fallos).

### MB-03 · 21-oct-2026, 19:28–20:08 · REAL · Caídas y recuperaciones
- **Qué se hizo:** pruebas de desconexión del enlace de SW-ACCESO y luego de los routers.
- **Resultado:** SW-ACCESO cayó y volvió 5 veces: las 5 caídas y las 5 recuperaciones quedaron registradas. El tiempo medido entre la desconexión y la alerta fue de 19 a 24 s (promedio cercano a 20 s), dentro de los 30 s esperados (3 pings × 10 s). R1-LAB y R2-LAB cayeron a las 20:06 y volvieron a las 20:08 (1 ms de latencia).
- **Detecciones automáticas:** 4 de *puerto inestable* (2 en SW-CORE, 2 en SW-ACCESO) por los puertos que subían y bajaban durante las pruebas.

### MB-04 · 21-oct-2026, 20:09 · REAL · Falsa alarma al desconectar el portátil
- **Qué pasó:** al desconectar el portátil del laboratorio, los 4 equipos aparecieron caídos al mismo tiempo (20:09:18), aunque seguían encendidos.
- **Hallazgo:** H-07. El NOC no distinguía "los equipos se cayeron" de "yo perdí la red".
- **Corrección (v1.0.0):** si ninguna IP del NOC está en la red de los equipos y ninguno responde, se muestra un solo aviso "El NOC no está conectado a la red de gestión" y no se declaran caídas. Probado con `test_sin_red_de_gestion_un_solo_aviso_y_ningun_equipo_caido`. **Falta repetirlo en el laboratorio** (ver pendientes).

### MB-05 · 16-nov-2026 · SIMULADO · Prueba de carga
- **Qué se hizo:** `python scripts/prueba_carga.py` en un NOC aparte con 3 equipos simulados.
- **Resultado antes de la mejora:** 3.000 mensajes a 500 msg/s → 2.691 guardados (10,3 % perdidos en UDP). Panel con mediana de 96 ms.
- **Mejora:** una sola conexión a la base de datos para el receptor, registro por mensaje en nivel DEBUG y búfer UDP de 8 MB → H-08.
- **Resultado después:** 3.000/3.000 guardados, panel con mediana de 36 ms. A 1.500 msg/s: 6.000/6.000 guardados y unos 820 msg/s procesados de forma sostenida. Tormenta de 2.000 mensajes de un equipo: 300 aceptados, 1 detección de tormenta, y el otro equipo guardó sus 50 mensajes.

### MB-06 · 16-nov-2026 · REAL (copia de la base de trabajo) · Respaldo y recuperación
- **Qué se hizo:** `python scripts/prueba_respaldo.py` sobre una copia de `data/noc.db` (74 eventos): respaldo, borrado de eventos, daño del archivo y restauración.
- **Primera corrida: FALLÓ.** Se recuperaron 0 de 74 eventos → H-09 y H-10.
- **Segunda corrida (tras corregir):** 74/74 eventos, `integrity_check = ok`, auditoría igual que antes. Respaldo en 0,17 s y restauración en 0,18 s.
- **Hallazgo adicional:** la verificación de integridad marcó el registro de auditoría #1 como alterado. Causa: al limpiar los datos antes del laboratorio se borró el equipo de la prueba del 16-oct y la base puso su `device_id` en blanco → H-11 (ahora un equipo con auditoría no se puede borrar). El control funcionó: detectó un cambio real en la evidencia.

### MB-07 · 16-nov-2026 · SIMULADO · Ensayo de despliegue y rollback
- **Qué se hizo:** `python scripts/prueba_despliegue.py`: v0.2.0 recibiendo Syslog → respaldo → v1.0.0 → rollback a v0.2.0.
- **Resultado:** la versión nueva arrancó en 2,7 s con los 20 eventos intactos y la base actualizada; el rollback tardó 1,7 s y dejó los datos iguales a antes del despliegue.

### MB-08 · 16-nov-2026 · SIMULADO · Pruebas automáticas
- **Resultado:** 185 pruebas aprobadas (`python -m pytest`), 29 más que al empezar el Corte 3 (SSH, Telegram, red de gestión, defensa IA y analizador), con Netmiko y Telegram simulados.
- **Hallazgo:** al instalar Netmiko, su dependencia *textfsm* instala un paquete llamado `tests` que tapaba las pruebas del proyecto → H-12 (se agregó `tests/__init__.py`).

## Pendientes en el laboratorio (requieren los equipos físicos)

Estas pruebas no se han hecho todavía. Cuando se hagan, se agrega la entrada con su resultado real.

| # | Prueba | Cómo hacerla | Resultado esperado |
|---|---|---|---|
| P-01 | Consola por SSH real | Escribir `SSH_USUARIO` y `SSH_CLAVE` en `.env`, marcar R1-LAB con "Gestión por SSH", ejecutar `show clock` en la consola | La barra de la consola dice "SSH REAL" y la salida es la del equipo |
| P-02 | Cambio aprobado aplicado por SSH | Un administrador propone `logging trap warnings` en R2-LAB; otro lo aprueba | Auditoría "APROBADA · aplicada por SSH"; `show logging` en el equipo lo confirma; no aparece detección de cambio sin aprobación |
| P-03 | Cambio sin aprobación | Entrar por consola a SW-CORE y hacer cualquier cambio | Detección "Cambio sin aprobación" en menos de 5 s |
| P-04 | Alerta por Telegram | Crear el bot, escribir `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` en `.env`, botón "Enviar mensaje de prueba" y desconectar SW-ACCESO | Llega el mensaje de prueba y luego "[CAIDO] SW-ACCESO" y "[RECUPERADO] SW-ACCESO" |
| P-05 | Pérdida de la red de gestión | Desconectar el cable del portátil | Un solo aviso "El NOC no está conectado a la red de gestión"; ningún equipo marcado caído |
