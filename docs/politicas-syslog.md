# Políticas Syslog documentadas y verificadas · v1.0.0

Este documento dice **qué se configura en cada equipo, por qué, y cómo se comprobó**. La columna
"Verificación" distingue lo que se probó en equipos reales de lo que solo se probó con datos simulados.

## 1. Política común (todas las marcas)

| # | Regla | Motivo | Cómo la aplica el NOC |
|---|---|---|---|
| P1 | Solo envían Syslog los equipos del inventario | Un mensaje de una IP desconocida puede ser falso | El colector descarta las fuentes no inventariadas y las cuenta como `fuente_no_autorizada` |
| P2 | Destino único: el servidor NOC, UDP 5514 | Centralizar el rastro en un solo lugar | Generador de plantillas (`configgen/`) con la IP del NOC |
| P3 | Nivel mínimo `informational` (6) en laboratorio, `warnings` (4) en producción | Ver accesos y cambios en el laboratorio; evitar ruido en producción | Plantillas por ambiente; el umbral de incidente es 0–2 |
| P4 | Marca de tiempo con milisegundos y zona horaria | Correlacionar eventos de varios equipos | El colector guarda además la hora de llegada en UTC |
| P5 | Registrar inicios de sesión correctos y fallidos | Detectar fuerza bruta y accesos indebidos | Regla `fuerza_bruta` (5 fallos en 5 min por IP) |
| P6 | Registrar cada cambio de configuración (sin mostrar claves) | Saber quién cambió qué | Reglas `fuera_de_horario` y `cambio_sin_aprobacion` |
| P7 | Interfaz de origen fija | Que la IP de origen coincida con el inventario | `logging source-interface` |
| P8 | Límite por equipo de 300 mensajes por minuto y agrupación de repetidos (60 s) | Una tormenta no debe tumbar el NOC ni silenciar a otros equipos | `security/controls.py`; probado con carga (ver pruebas) |
| P9 | Los logs son datos, nunca instrucciones | Un log puede traer texto para engañar a una IA | Texto limpio, mostrado con `textContent`, regla `manipulacion` |
| P10 | Acceso de gestión solo por SSH v2 con usuario local | Telnet viaja en texto plano | Bloque 2 de la configuración del laboratorio |

## 2. Cisco IOS / IOS XE — **verificada en equipos reales**

Configuración aplicada el 21-oct-2026 en R1-LAB y R2-LAB (Cisco 1941) y SW-CORE / SW-ACCESO (Catalyst),
red de laboratorio 192.168.50.0/24, servidor NOC en 192.168.50.10:

```
clock timezone COT -5 0
service timestamps log datetime msec localtime show-timezone      ! P4
logging buffered 64000 informational
logging trap informational                                         ! P3 (laboratorio)
logging source-interface GigabitEthernet0/0                        ! P7 (Vlan1 en los switches)
logging host 192.168.50.10 transport udp port 5514                 ! P2
login on-failure log                                               ! P5
login on-success log                                               ! P5
archive
 log config
  logging enable                                                   ! P6
  notify syslog contenttype plaintext
  hidekeys                                                         ! P6: no envía claves
ip ssh version 2                                                   ! P10
line vty 0 15
 login local
 transport input ssh
```

**Cómo se verificó (real):**

| Prueba | Resultado observado |
|---|---|
| `show logging` en cada equipo | Muestra `Logging to 192.168.50.10 (udp port 5514)` |
| Mensajes recibidos el 21-oct | 51 mensajes reales de los 4 equipos, todos con hostname y hora con milisegundos |
| Puertos que suben y bajan (`%LINK-3-UPDOWN`, `%LINEPROTO-5-UPDOWN`) | Se identificó la interfaz exacta y se generaron 4 detecciones de puerto inestable |
| Formato real de Cisco (`<189>45: R2-LAB: Oct 21 ...: %SYS-5-CONFIG_I`) | El analizador lo reconoce (pruebas `test_parser.py`) |
| Cambio de configuración (16-oct, Cisco 8200) | `%SYS-5-CONFIG_I` registrado y detectado como fuera de horario |

**Pendiente en el laboratorio:** NTP (los equipos usan la hora puesta a mano) y TLS (RFC 5425);
los equipos del laboratorio no tienen servidor NTP disponible.

## 3. FortiGate (FortiOS) — plantilla, **verificada solo con datos simulados**

Generada por *Plantillas* (`configgen/templates.py`) con la IP del NOC:

```
config log syslogd setting
    set status enable
    set server "IP_DEL_NOC"
    set mode udp
    set port 5514
    set facility local7
    set source-ip-interface "INTERFAZ_DE_GESTION"
end
config log syslogd filter
    set severity information
end
```

Verificación: el analizador reconoce el formato clave=valor de FortiGate (`test_parser.py`) y los
eventos de muestra simulados. **No se tuvo un FortiGate físico**: esta política no se probó en un equipo real.

## 4. Huawei VRP — plantilla, **verificada solo con datos simulados**

```
system-view
info-center enable
info-center loghost IP_DEL_NOC port 5514 facility local7
info-center loghost source INTERFAZ_DE_GESTION
info-center source default channel loghost log level informational
info-center timestamp log date
return
save
```

Verificación: formato Huawei con año reconocido por el analizador y eventos simulados.
**No se tuvo un equipo Huawei físico.**

## 5. Cómo verificar la política en un equipo nuevo (lista de chequeo)

1. Registrar el equipo en *Inventario* con su IP de gestión y origen **Real**.
2. Generar la plantilla en *Plantillas* (marca, IP del NOC, nivel) y aplicarla.
3. En el equipo: `show logging` (Cisco), `get log syslogd setting` (FortiGate), `display info-center` (Huawei).
4. Provocar un evento controlado (por ejemplo entrar y salir del modo configuración) y comprobar que aparece en *Eventos* en menos de 5 s con el nombre correcto del equipo.
5. Dejar constancia en la bitácora: fecha, equipo, comando, resultado y si fue real o simulado.
