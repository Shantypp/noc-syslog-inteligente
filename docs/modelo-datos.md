# Modelo de datos (SQLite)

```mermaid
erDiagram
    DEVICES ||--o{ EVENTS : genera
    EVENTS ||--o| INCIDENTS : origina
    DEVICES ||--o{ INCIDENTS : afecta
    INCIDENTS ||--o{ INCIDENT_LOG : "seguimiento"
    DEVICES ||--o{ COMMAND_AUDIT : "se consulta en"
    USERS ||--o{ SESSIONS : abre
    DEVICES {
        int id PK
        text nombre
        text ip UK
        text marca "Cisco|Fortinet|Huawei"
        text modelo
        text version_so
        text ubicacion
        text estado "activo|inactivo|sin_comunicacion"
        text origen "simulado|real"
        text actualizado_en
    }
    EVENTS {
        int id PK
        int device_id FK
        text recibido_en "hora del colector UTC"
        text timestamp_equipo
        text ip_origen
        text hostname
        int facility "0-23"
        int severidad "0-7"
        text mensaje "limpio"
        text mensaje_crudo "evidencia"
        text hash_dedup
        int repeticiones
        int sospechoso "0|1"
        text origen
        text componente "puerto o parte afectada"
        text estado_componente
    }
    INCIDENTS {
        int id PK
        int event_id FK
        int device_id FK
        text titulo
        int severidad
        text estado "abierto|asignado|en_progreso|cerrado"
        text responsable
        text abierto_en
        text actualizado_en
        text cerrado_en
        text causa
        text solucion
    }
    INCIDENT_LOG {
        int id PK
        int incident_id FK
        text usuario
        text accion
        text detalle
        text fecha
    }
    COMMAND_AUDIT {
        int id PK
        text usuario
        int device_id FK
        text comando
        text decision "PERMITIDO|BLOQUEADO|PROPUESTA|NO_VERIFICADO"
        text aprobado_por
        text resultado
        text hash_evidencia "SHA-256"
        text fecha
    }
    USERS {
        int id PK
        text usuario UK
        text nombre
        text rol "lector|operador|administrador"
        text clave_hash "PBKDF2-SHA256"
        int activo
    }
    SESSIONS {
        text token_hash PK "SHA-256 del token"
        int user_id FK
        text expira_en
    }
    AUTH_LOG {
        int id PK
        text usuario
        int exito
        text detalle
        text fecha
    }
```

## Decisiones de diseño

- **`origen`** en equipos y eventos: los datos simulados quedan identificados (regla del curso).
- **`mensaje_crudo`** conserva el texto exacto recibido (evidencia); **`mensaje`** es la versión limpia que se muestra.
- **`hash_dedup`** = SHA-256(equipo + severidad + mensaje) → agrupa repetidos en una ventana de 60 s.
- **`sospechoso`** marca patrones de inyección; el evento se guarda igual (no se destruye evidencia).
- **`hash_evidencia`** = SHA-256(usuario, equipo, comando, decisión, aprobador, resultado, fecha) → detecta alteraciones.
- **Restricciones `CHECK`**: la base de datos rechaza marcas, estados y severidades inválidas aunque falle la validación de la API (defensa en profundidad).
- Índices en `events(severidad, recibido_en, device_id, hash_dedup)` y `events(device_id, componente)` para que los filtros no se bloqueen.
- **`componente` / `estado_componente`**: parte del equipo que generó el evento (ej. `GigabitEthernet0/1` · `Caído`); se extrae del texto con reglas por fabricante y se limita a caracteres seguros.
- **`users.clave_hash`**: nunca se guarda la contraseña, solo PBKDF2-SHA256 con sal. **`sessions.token_hash`**: solo la huella del token de la cookie.
- **`auth_log`** registra cada intento de inicio de sesión: permite bloquear la fuerza bruta y auditar accesos.
- **Migración**: al iniciar, `init_db()` agrega las columnas nuevas a una base de datos anterior sin borrar datos.
