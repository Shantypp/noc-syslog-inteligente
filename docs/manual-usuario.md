# Manual de usuario · NOC Syslog Inteligente v1.0.0

Este manual explica cómo usar el NOC en el día a día. No hace falta saber programar.

## 1. Entrar

1. Doble clic en **iniciar-sistema.bat** (o pida al administrador que abra el NOC).
2. Se abre el navegador en `http://127.0.0.1:8000`. Escriba su usuario y contraseña.
3. Después de 5 intentos fallidos la cuenta queda bloqueada 15 minutos.

Cada persona tiene un **rol**:

| Rol | Puede |
|---|---|
| Lector | Ver el panel, eventos, incidentes y la auditoría |
| Operador | Lo anterior, más abrir y gestionar incidentes, revisar detecciones y proponer cambios |
| Administrador | Todo, más aprobar cambios **de otras personas**, inventario, usuarios y configuración |

## 2. El panel general

Es la primera pantalla. Se actualiza sola cada 10 segundos.

- **Requiere su atención:** lo que hay que hacer ahora, en orden de prioridad. Haga clic en cada asunto para ir a resolverlo.
- **Tarjetas:** equipos activos, sin comunicación, eventos de 24 h, eventos graves, detecciones e incidentes.
- **Estado de los equipos:** verde = responde; rojo = no responde al ping ni envía eventos; "desconocido" = el NOC perdió la conexión con la red de los equipos (revise el cable del servidor).

Si aparece el aviso **"El NOC no está conectado a la red de gestión"**, el problema es del computador del NOC, no de los equipos.

## 3. Eventos

Lista de todo lo que enviaron los equipos. Puede filtrar por fecha, marca, equipo, severidad o texto,
y exportar a CSV. Severidad: 0 = emergencia ... 7 = depuración. Las de 0 a 2 se proponen como incidente.

## 4. Detecciones

El sistema revisa los eventos y avisa cuando ve un patrón:

| Detección | Qué significa | Qué hacer |
|---|---|---|
| Fuerza bruta | Muchos inicios de sesión fallidos | Revisar la IP de origen; bloquearla si no es conocida |
| Cambio fuera de horario | Alguien cambió un equipo fuera del horario laboral | Confirmar con el responsable |
| Cambio sin aprobación | El equipo cambió y en el NOC nadie aprobó ese cambio | Averiguar quién fue; revertir si no corresponde |
| Puerto inestable | Un puerto sube y baja muchas veces | Revisar cable, transceptor o energía |
| Tormenta de eventos | Un equipo envía demasiados mensajes | Revisar falla en cascada o ataque |
| Manipulación en un log | Un mensaje intenta dar órdenes | Nada se ejecutó; investigar el origen |
| Ráfaga de comandos | Un usuario envió demasiados comandos seguidos | Confirmar si es una persona o un programa |

Para cada detección: **Abrir incidente** o **Descartar** (con el motivo; queda registrado).

## 5. Incidentes

1. Abrir desde una propuesta, una detección o con el botón *Abrir incidente*.
2. Asignar responsable y registrar avances en el historial.
3. Si el componente vuelve a funcionar, el incidente muestra **Recuperado**.
4. Cerrar con causa y solución.

Cada severidad tiene un tiempo máximo de atención; si se vence, el incidente sube al primer lugar de *Requiere su atención*.

## 6. Consola de equipos

1. Elija el equipo y el perfil (Cisco, FortiGate, Huawei).
2. Escriba un comando o haga clic en uno de la lista *Comandos permitidos*. `help` muestra la lista.
3. La barra superior indica el modo:
   - **simulación · solo lectura**: la respuesta es de ejemplo;
   - **SSH REAL** (barra roja): la respuesta viene del equipo de verdad.

| Respuesta | Significado |
|---|---|
| PERMITIDO | Consulta autorizada: se muestra la salida |
| PROPUESTA | Es un cambio: no se ejecuta. Otro administrador debe aprobarlo en *Auditoría* |
| BLOQUEADO | Destructivo, encadenado o no permitido para su rol |
| NO VERIFICADO | El comando es de otra marca o de otro modo del equipo |

Si escribe más de 30 comandos en un minuto, la consola se pausa 5 minutos por seguridad.

## 7. Auditoría y aprobación de cambios (administrador)

- Toda acción en la consola queda registrada con fecha, usuario, decisión y una huella (hash).
- Arriba aparecen las propuestas pendientes. Puede **Aprobar** o **Rechazar** con motivo. No puede aprobar lo que usted mismo propuso.
- Si el equipo tiene "Gestión por SSH", al aprobar el cambio se aplica en el equipo y el resultado queda en la auditoría.
- Al abrir la pantalla se verifica la integridad: si alguien modificó un registro por fuera de la aplicación, aparece una alerta con su número.

## 8. Inventario (administrador)

Registre cada equipo con nombre (igual al hostname de sus logs), IP, marca y origen (Real o Simulado).
Solo los equipos del inventario pueden enviar eventos. "Gestión por SSH" = Sí permite la consola real.
Un equipo con registros de auditoría no se puede eliminar: márquelo como **Inactivo**.

## 9. Configuración (administrador)

- Estado del receptor Syslog y la IP que hay que poner en los equipos.
- **Alertas por Telegram:** estado y botón *Enviar mensaje de prueba*.
- Parámetros (umbrales, horario laboral, intervalo de ping, máximo de comandos por minuto...). Se aplican de inmediato.
- Mantenimiento: respaldo descargable, retención y datos de demostración.

## 10. Preguntas frecuentes

**Un equipo aparece sin comunicación.** Verifique que esté encendido y conectado; desde el NOC, el ping debe responder.

**No llegan eventos de un equipo nuevo.** Revise que esté en el inventario con la IP correcta, que el NOC esté en modo red y que el equipo tenga `logging host` hacia la IP del NOC, puerto 5514.

**¿Las alertas de Telegram muestran contraseñas?** No. Se envía solo el resumen del evento; el token del bot vive en el servidor.
