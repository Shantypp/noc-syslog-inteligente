"""Pruebas de la Fase 5: generador de configuraciones (HU-04), consola (RF-07) y auditoría (HU-05)."""

import pytest

from app.console.simulator import evaluar
from app.database import get_connection


# ---------- Generador de configuraciones (HU-04) ----------

@pytest.mark.parametrize("fabricante,esperado", [
    ("cisco", "logging host 192.0.2.10 transport udp port 514"),
    ("fortinet", 'set server "192.0.2.10"'),
    ("huawei", "info-center loghost 192.0.2.10 facility local7"),
])
def test_plantilla_usa_ip_y_trae_comentarios_y_advertencia(client, fabricante, esperado):
    r = client.get("/api/configgen", params={"fabricante": fabricante, "ip": "192.0.2.10", "umbral": "warnings"})
    assert r.status_code == 200
    d = r.json()
    assert esperado in d["plantilla"]
    assert "ADVERTENCIA" in d["plantilla"]
    assert d["verificacion"] and d["reversa"]


def test_umbral_se_traduce_a_la_sintaxis_de_cada_marca(client):
    nivel = lambda f: client.get("/api/configgen", params={"fabricante": f, "ip": "192.0.2.10", "umbral": "errors"}).json()["parametros"]["nivel"]
    assert (nivel("cisco"), nivel("fortinet"), nivel("huawei")) == ("errors", "error", "error")


@pytest.mark.parametrize("params", [
    {"ip": "192.0.2.10\nreload"},                           # intento de inyectar un comando
    {"ip": "no-es-ip"},
    {"ip": "192.0.2.10", "umbral": "todo"},
    {"ip": "192.0.2.10", "interfaz": "Gi0/0\nwrite erase"},
    {"ip": "192.0.2.10", "puerto": 70000},
])
def test_entradas_invalidas_son_rechazadas(client, params):
    assert client.get("/api/configgen", params={"fabricante": "cisco", **params}).status_code == 422


# ---------- Consola simulada (RF-07) ----------

@pytest.mark.parametrize("perfil,comando,decision", [
    ("cisco_ios", "show version", "PERMITIDO"),
    ("cisco_ios", "  SHOW   Version ", "PERMITIDO"),          # se normaliza
    ("cisco_ios", "configure terminal", "PROPUESTA"),
    ("cisco_ios", "write memory", "PROPUESTA"),
    ("cisco_ios", "reload", "BLOQUEADO"),
    ("cisco_ios", "write erase", "BLOQUEADO"),
    ("cisco_ios", "show version; reload", "BLOQUEADO"),       # encadenamiento
    ("cisco_ios", "show tech-support", "BLOQUEADO"),          # consulta fuera de la lista
    ("cisco_ios", "rm -rf /", "BLOQUEADO"),                   # desconocido: denegar por defecto
    ("cisco_ios", "display version", "NO_VERIFICADO"),        # comando Huawei en Cisco
    ("cisco_rommon", "show version", "NO_VERIFICADO"),        # IOS dentro de ROMMON
    ("cisco_rommon", "reset", "BLOQUEADO"),
    ("fortigate", "get system status", "PERMITIDO"),
    ("fortigate", "config log syslogd setting", "PROPUESTA"),
    ("fortigate", "execute factoryreset", "BLOQUEADO"),
    ("huawei_vrp", "display info-center", "PERMITIDO"),
    ("huawei_vrp", "system-view", "PROPUESTA"),
    ("huawei_vrp", "reset saved-configuration", "BLOQUEADO"),
])
def test_decisiones_de_la_consola(perfil, comando, decision):
    assert evaluar(perfil, comando)["decision"] == decision


def test_todo_comando_queda_auditado(client):
    for cmd in ["show version", "reload", "configure terminal"]:
        client.post("/api/console/ejecutar", json={"perfil": "cisco_ios", "comando": cmd, "usuario": "ana"})
    filas = client.get("/api/auditoria").json()
    assert [f["decision"] for f in filas] == ["PROPUESTA", "BLOQUEADO", "PERMITIDO"]
    assert all(f["usuario"] == "admin1" and f["fecha"] and f["hash_evidencia"] for f in filas)


# ---------- Revisión humana y auditoría (HU-05) ----------

def _proponer(client, usuario="ana") -> int:
    r = client.post("/api/console/ejecutar", json={"perfil": "cisco_ios", "comando": "configure terminal", "usuario": usuario})
    return r.json()["audit_id"]


def test_quien_propone_no_puede_aprobar(client):
    audit_id = _proponer(client, "ana")
    r = client.post(f"/api/auditoria/{audit_id}/aprobar", json={"usuario": "ana"})
    assert r.status_code == 409


def test_aprobacion_por_otro_usuario_queda_registrada(client, como):
    audit_id = _proponer(client)
    otro_admin = como("admin2")
    r = otro_admin.post(f"/api/auditoria/{audit_id}/aprobar", json={})
    assert r.status_code == 200
    assert r.json()["aprobado_por"] == "admin2"
    assert "SIMULADA" in r.json()["resultado"]
    # No se puede decidir dos veces
    assert otro_admin.post(f"/api/auditoria/{audit_id}/rechazar", json={}).status_code == 409


def test_alterar_un_registro_se_detecta(client, tmp_path):
    _proponer(client)
    assert client.get("/api/auditoria/integridad").json()["alterados"] == []
    # Alguien modifica la base de datos "por debajo"
    conn = get_connection(str(tmp_path / "test.db"))
    conn.execute("UPDATE command_audit SET comando = 'show version' WHERE id = 1")
    conn.commit()
    conn.close()
    assert client.get("/api/auditoria/integridad").json()["alterados"] == [1]


def test_exportar_csv_protege_contra_formulas(client):
    client.post("/api/console/ejecutar", json={"perfil": "cisco_ios", "comando": "=HYPERLINK(\"x\")", "usuario": "ana"})
    r = client.get("/api/auditoria/exportar")
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    assert "'=HYPERLINK" in r.text  # la fórmula quedó neutralizada
