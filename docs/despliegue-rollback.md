# Procedimiento de despliegue y rollback · v1.0.0

El NOC corre en un solo computador (Windows o Linux) con Python 3.12 o superior. No necesita
servidor de base de datos: los datos están en `data/noc.db` (SQLite). Este procedimiento se
ensayó completo el 16-nov-2026 con `scripts/prueba_despliegue.py` (resultado en
`docs/evidencias/despliegue-20261116-2219.json`).

## 1. Antes de desplegar

| Paso | Comando o acción | Cómo saber que salió bien |
|---|---|---|
| 1.1 | Avisar a los usuarios: el NOC estará detenido unos minutos | — |
| 1.2 | Anotar la versión actual: abrir *Configuración* o `http://127.0.0.1:8000/api/health` | Muestra `"version": "0.2.0"` |
| 1.3 | Respaldar la base de datos: `python scripts/backup_db.py` | Imprime `Respaldo creado: data/backups/noc-AAAAMMDD-HHMMSS.db` |
| 1.4 | Copiar el archivo `.env` a un lugar seguro (no se sube a GitHub) | El archivo existe fuera de la carpeta del proyecto |

## 2. Despliegue de la versión nueva

| Paso | Comando o acción | Cómo saber que salió bien |
|---|---|---|
| 2.1 | Detener el NOC: `Ctrl+C` en la ventana del iniciador | Muestra `NOC detenido.` |
| 2.2 | Traer la versión: `git fetch --tags` y `git checkout v1.0.0` | `git describe --tags` muestra `v1.0.0` |
| 2.3 | Agregar al `.env` las variables nuevas de `.env.example` (SSH y Telegram), si se van a usar | — |
| 2.4 | Iniciar: doble clic en `iniciar-sistema.bat` (instala solo lo que cambió, por ejemplo Netmiko) | Abre el navegador; `/api/health` muestra `1.0.0` |
| 2.5 | La base de datos se actualiza sola al iniciar (columnas nuevas: `ssh_habilitado`, `decidido_en`) | Los equipos, eventos e incidentes de antes siguen ahí |
| 2.6 | Prueba de humo: iniciar sesión, ver el panel, enviar `python scripts/enviar_syslog_prueba.py` en modo laboratorio | El evento aparece en *Eventos* |

**Tiempo medido en el ensayo:** 2,7 s desde el cambio de versión hasta que el servidor respondió
(sin contar la descarga de dependencias nuevas, que la primera vez tarda 1–2 minutos).

## 3. Criterios para hacer rollback

Se vuelve a la versión anterior si, después de desplegar, ocurre cualquiera de estos casos:

- el servidor no inicia o `/api/health` no responde en 1 minuto;
- no llegan eventos de equipos que antes sí enviaban (más de 5 minutos);
- faltan datos (equipos, incidentes o auditoría) o la verificación de integridad de la auditoría muestra registros alterados que antes no estaban;
- un error impide trabajar a los operadores.

## 4. Rollback

| Paso | Comando o acción | Cómo saber que salió bien |
|---|---|---|
| 4.1 | Detener el NOC (`Ctrl+C`) | `NOC detenido.` |
| 4.2 | Restaurar el respaldo del paso 1.3: `python scripts/backup_db.py --restaurar data/backups/noc-AAAAMMDD-HHMMSS.db` | Imprime `Restaurado ...` y guarda el estado actual como `antes-de-restaurar-*.db` |
| 4.3 | Volver al código anterior: `git checkout v0.2.0` | `git describe --tags` muestra `v0.2.0` |
| 4.4 | Iniciar de nuevo | `/api/health` muestra `0.2.0` y los datos son los del paso 1 |
| 4.5 | Registrar en la bitácora qué falló y por qué se hizo rollback | — |

**Tiempo medido en el ensayo:** 1,7 s (restaurar + cambiar versión + iniciar).

## 5. Resultado del ensayo (16-nov-2026, datos simulados)

| Etapa | Versión reportada | Equipos | Eventos | Columna nueva | Resultado |
|---|---|---|---|---|---|
| v0.2.0 recibiendo Syslog | 0.2.0 | 1 | 20 | No | Arranque en 1,4 s |
| Respaldo | — | — | — | — | `noc-20261116-221929.db` |
| Despliegue de la versión nueva | 1.0.0 | 1 | 20 | Sí | Sin pérdida de datos |
| Rollback a v0.2.0 | 0.2.0 | 1 | 20 | No | Datos iguales a antes del despliegue |

## 6. Lo que se aprendió al ensayar

La primera prueba de recuperación (`respaldo-20261116-2215-antes.json`) **falló**: se restauraron 0 de 74 eventos.
Había dos respaldos con el mismo nombre (se creaban en el mismo segundo) y el respaldo "previo a restaurar"
borraba el bueno. Además, el script dejaba la base abierta y Windows bloqueaba el archivo. Las dos cosas se
corrigieron antes de escribir este procedimiento (ver `docs/hallazgos.md`, H-09 y H-10).
