# NOC Syslog Inteligente

> Proyecto académico individual · Administración y Gestión de Redes · Periodo 2026-2
> Docente: Ing. John Harold Pérez Calderón · Estudiante: Jhoan Santiago Pachón Perilla
> **Los dispositivos y eventos de este repositorio son SIMULADOS.**

Aplicación NOC que recibe eventos Syslog de equipos Cisco, Fortinet y Huawei, los clasifica por severidad (0–7), gestiona incidentes y prepara configuraciones seguras, con controles frente a acciones no autorizadas de agentes de IA.

## Estado
🚧 En desarrollo — versión alfa `v0.1.0` (estructura y modelo de datos).

## Instalación rápida (Windows / PowerShell)
```powershell
git clone https://github.com/TU-USUARIO/noc-syslog-inteligente.git
cd noc-syslog-inteligente
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m app.database
```

*(El README completo se termina en la Fase 6.)*
