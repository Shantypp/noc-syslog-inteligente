# Arquitectura

## Componentes

```mermaid
flowchart LR
    subgraph Fuentes["Fuentes (SIMULADAS)"]
        C[Cisco IOS XE]
        F[FortiGate]
        H[Huawei VRP]
        A[Archivo .log]
    end
    subgraph App["Aplicación (Python + FastAPI)"]
        R["collector/udp_server<br/>UDP 127.0.0.1:5514"]
        I["collector/ingest<br/>importador"]
        P["collector/parser<br/>RFC 3164 / 5424"]
        V["security/controls<br/>allowlist · dedup · rate limit · sospechosos"]
        POL["incidents/policy<br/>sev 0–2 → propuesta · SLA"]
        API["api/* (REST)"]
        GEN["configgen/templates"]
        CON["console/simulator"]
        AUD["console/audit<br/>hash SHA-256"]
    end
    DB[(SQLite noc.db)]
    UI["web/ HTML + CSS + JS"]

    C & F & H -->|Syslog UDP| R
    A --> I
    R & I --> P --> V --> DB
    DB --> POL
    DB <--> API <--> UI
    UI --> GEN
    UI --> CON --> AUD --> DB
```

## Flujo lógico del curso

```mermaid
flowchart LR
    A[1. Ingreso<br/>UDP o archivo] --> B[2. Validación<br/>formato + fuente permitida<br/>+ dedup + rate limit]
    B --> C[3. Política<br/>severidad ≤ 2]
    C --> D[4. Incidente<br/>propuesta → humano crea]
    D --> E[5. Respuesta<br/>seguimiento + evidencia]
```

## Flujo seguro de acciones

```mermaid
sequenceDiagram
    actor Op as Operador (ana)
    participant UI as Consola web
    participant API as Backend
    participant AUD as Auditoría
    actor Sup as Supervisor
    Op->>UI: configure terminal
    UI->>API: POST /api/console/ejecutar
    API->>API: evaluar(): allowlist / destructivo / otra marca
    API->>AUD: registrar PROPUESTA (pendiente) + hash
    API-->>UI: "requiere aprobación, NO se ejecutó"
    Sup->>API: POST /api/auditoria/{id}/aprobar
    API->>API: ¿revisor ≠ quien propuso?
    API->>AUD: APROBADA · ejecución SIMULADA + nuevo hash
    Note over API: v1.0.0: aquí iría SSH (Netmiko) solo a hosts permitidos
```

## Decisiones (ADR)

| ADR | Decisión | Motivo |
|---|---|---|
| 001 | Python + FastAPI + SQLite + HTML/JS sin frameworks | Simple de instalar y explicar; `/docs` permite probar la API; Netmiko (SSH, Corte 3) es Python |
| 002 | Los logs son datos no confiables | Evita inyección de prompt indirecta y XSS |
| 003 | La política propone, el humano decide | Flujo seguro obligatorio; evita escalada autónoma |
| 004 | Receptor en 127.0.0.1:5514 por defecto | Laboratorio seguro sin permisos de administrador |
| 005 | Validación de comandos en el backend | En el navegador se puede saltar con F12 |
