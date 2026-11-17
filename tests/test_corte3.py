"""
Pruebas del Corte 3: gestor SSH por el backend, alertas por Telegram y red de gestión.

Nunca se conecta a un equipo real ni a Telegram: Netmiko y la llamada HTTP se reemplazan
por versiones simuladas (monkeypatch). Las credenciales son valores de PRUEBA inventados.
"""

import sys
import types

import pytest

from app.collector import monitoreo
from app.console import ssh
from app.database import get_connection, init_db
from app.notificaciones import alertas, telegram

TOKEN_PRUEBA = "999999:token-de-prueba-que-no-existe"
CHAT_PRUEBA = "-100123456"


# ---------------------------------------------------------------- SSH

class ConexionFalsa:
    """Imita a netmiko.ConnectHandler y anota lo que se le pidió."""
    pedidos: list = []

    def __init__(self, **kwargs):
        ConexionFalsa.pedidos.append(("conectar", kwargs["host"], kwargs["device_type"]))

    def send_command(self, comando, read_timeout=30):
        ConexionFalsa.pedidos.append(("consulta", comando))
        return f"salida real de {comando}\x07"

    def send_config_set(self, comandos, read_timeout=30):
        ConexionFalsa.pedidos.append(("config", comandos))
        return "R1-LAB(config)#" + comandos[0]

    def disconnect(self):
        ConexionFalsa.pedidos.append(("desconectar",))


@pytest.fixture
def netmiko_falso(monkeypatch):
    ConexionFalsa.pedidos = []
    modulo = types.ModuleType("netmiko")
    modulo.ConnectHandler = ConexionFalsa
    monkeypatch.setitem(sys.modules, "netmiko", modulo)
    monkeypatch.setenv("SSH_USUARIO", "usuario-prueba")
    monkeypatch.setenv("SSH_CLAVE", "clave-prueba-ssh")
    return ConexionFalsa


def _registrar_equipo(client, ssh_habilitado=True, origen="real", nombre="R1-LAB", ip="192.168.50.1"):
    r = client.post("/api/devices", json={"nombre": nombre, "ip": ip, "marca": "Cisco", "origen": origen,
                                          "ssh_habilitado": ssh_habilitado})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_consulta_permitida_viaja_por_ssh_y_queda_auditada(client, netmiko_falso):
    equipo = _registrar_equipo(client)
    r = client.post("/api/console/ejecutar", json={"perfil": "cisco_ios", "comando": "show version", "device_id": equipo}).json()
    assert r["modo"] == "ssh" and r["decision"] == "PERMITIDO"
    assert r["salida"] == "salida real de show version"  # sin caracteres de control
    assert ("consulta", "show version") in netmiko_falso.pedidos and ("desconectar",) in netmiko_falso.pedidos
    [fila] = client.get("/api/auditoria").json()
    assert fila["resultado"].startswith("Ejecutado por SSH en R1-LAB")


@pytest.mark.parametrize("comando", ["reload", "configure terminal", "show version ; reload", "write erase"])
def test_lo_que_no_esta_permitido_nunca_llega_al_equipo(client, netmiko_falso, comando):
    equipo = _registrar_equipo(client)
    r = client.post("/api/console/ejecutar", json={"perfil": "cisco_ios", "comando": comando, "device_id": equipo}).json()
    assert r["decision"] in ("BLOQUEADO", "PROPUESTA")
    assert netmiko_falso.pedidos == []


def test_sin_habilitar_o_simulado_la_consola_sigue_simulada(client, netmiko_falso):
    for i, (habilitado, origen) in enumerate([(False, "real"), (True, "simulado")]):
        equipo = _registrar_equipo(client, habilitado, origen, nombre=f"EQ{i}", ip=f"192.0.2.{i + 1}")
        r = client.post("/api/console/ejecutar", json={"perfil": "cisco_ios", "comando": "show version", "device_id": equipo}).json()
        assert r["modo"] == "simulado" and r["salida"].startswith("[SIMULADO]")
    assert netmiko_falso.pedidos == []


def test_sin_credenciales_en_env_no_hay_ssh(client, netmiko_falso, monkeypatch):
    monkeypatch.setenv("SSH_CLAVE", "")
    equipo = _registrar_equipo(client)
    r = client.post("/api/console/ejecutar", json={"perfil": "cisco_ios", "comando": "show version", "device_id": equipo}).json()
    assert r["modo"] == "simulado"
    assert client.get("/api/console/ssh").json() == {"configurado": False}


def test_cambio_aprobado_por_otro_admin_se_aplica_por_ssh(client, como, netmiko_falso):
    equipo = _registrar_equipo(client)
    r = client.post("/api/console/ejecutar", json={"perfil": "cisco_ios", "comando": "logging host 192.168.50.10",
                                                   "device_id": equipo}).json()
    assert r["decision"] == "PROPUESTA" and not any(p[0] == "config" for p in netmiko_falso.pedidos)
    aprobado = como("admin2").post(f"/api/auditoria/{r['audit_id']}/aprobar", json={}).json()
    assert ("config", ["logging host 192.168.50.10"]) in netmiko_falso.pedidos
    assert aprobado["resultado"].startswith("APROBADA · aplicada por SSH en R1-LAB")


def test_cambio_rechazado_nunca_se_aplica(client, como, netmiko_falso):
    equipo = _registrar_equipo(client)
    r = client.post("/api/console/ejecutar", json={"perfil": "cisco_ios", "comando": "logging host 192.168.50.10",
                                                   "device_id": equipo}).json()
    como("admin2").post(f"/api/auditoria/{r['audit_id']}/rechazar", json={"motivo": "no corresponde"})
    assert not any(p[0] == "config" for p in netmiko_falso.pedidos)


def test_error_de_conexion_no_revela_la_clave(client, monkeypatch):
    class Falla:
        def __init__(self, **kw):
            raise TimeoutError(f"no conecta con clave {kw['password']}")
    modulo = types.ModuleType("netmiko")
    modulo.ConnectHandler = Falla
    monkeypatch.setitem(sys.modules, "netmiko", modulo)
    monkeypatch.setenv("SSH_USUARIO", "usuario-prueba")
    monkeypatch.setenv("SSH_CLAVE", "clave-prueba-ssh")
    equipo = _registrar_equipo(client)
    r = client.post("/api/console/ejecutar", json={"perfil": "cisco_ios", "comando": "show clock", "device_id": equipo}).json()
    assert "No se pudo conectar por SSH" in r["salida"] and "clave-prueba-ssh" not in r["salida"]
    assert "clave-prueba-ssh" not in client.get("/api/auditoria/exportar").text


def test_solo_un_administrador_habilita_ssh(como):
    r = como("oper").post("/api/devices", json={"nombre": "X", "ip": "192.168.50.9", "marca": "Cisco",
                                                 "origen": "real", "ssh_habilitado": True})
    assert r.status_code == 403


def test_ssh_no_se_habilita_en_equipos_simulados(client):
    _registrar_equipo(client, True, "simulado", ip="192.0.2.50")
    [d] = client.get("/api/devices").json()
    assert d["ssh_habilitado"] == 0


# ---------------------------------------------------------------- Telegram

@pytest.fixture
def telegram_falso(monkeypatch):
    enviados = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN_PRUEBA)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT_PRUEBA)
    monkeypatch.setattr(telegram, "_enviar_http", lambda token, chat, texto: enviados.append((token, chat, texto)))
    # Se envía en el mismo hilo para poder revisar el resultado
    original = telegram.notificar
    monkeypatch.setattr(telegram, "notificar", lambda *a, **k: original(*a, **{**k, "en_segundo_plano": False}))
    telegram.reiniciar()
    yield enviados
    telegram.reiniciar()


@pytest.fixture
def conn(tmp_path):
    path = str(tmp_path / "t.db")
    init_db(path)
    c = get_connection(path)
    c.execute("INSERT INTO devices (nombre, ip, marca, origen) VALUES ('R2-LAB', '192.168.50.2', 'Cisco', 'real')")
    c.commit()
    yield c
    c.close()


def test_sin_token_no_se_envia_nada(conn, monkeypatch):
    llamadas = []
    monkeypatch.setattr(telegram, "_enviar_http", lambda *a: llamadas.append(a))
    equipo = dict(conn.execute("SELECT * FROM devices").fetchone())
    assert alertas.conectividad(conn, equipo, caido=True) is False
    assert llamadas == []


def test_caida_por_ping_genera_una_sola_alerta(conn, telegram_falso):
    equipo = lambda: dict(conn.execute("SELECT * FROM devices").fetchone())  # noqa: E731
    monitoreo.registrar_resultado(conn, equipo(), True, 2)
    for _ in range(6):
        monitoreo.registrar_resultado(conn, equipo(), False, None)
    monitoreo.registrar_resultado(conn, equipo(), True, 3)
    textos = [t for _, _, t in telegram_falso]
    assert len(textos) == 2
    assert "[CAIDO] R2-LAB" in textos[0] and "[RECUPERADO] R2-LAB" in textos[1]


def test_anti_inundacion_misma_clave_y_tope_por_minuto(telegram_falso):
    assert telegram.permitido("a", 300, ahora=1000) is True
    assert telegram.permitido("a", 300, ahora=1100) is False      # misma alerta antes de 5 min
    assert telegram.permitido("a", 300, ahora=1301) is True       # pasados los 5 min
    telegram.reiniciar()
    resultados = [telegram.permitido(f"k{i}", 300, ahora=2000 + i) for i in range(25)]
    assert resultados.count(True) == telegram.MAX_POR_MINUTO      # tope global por minuto
    assert telegram.ESTADO["descartadas_por_inundacion"] == 5


def test_evento_grave_y_deteccion_nueva_se_avisan(conn, telegram_falso):
    from app.collector import ingest
    r = ingest.procesar_mensaje(conn, "<10>R2-LAB: %SYS-2-MALLOCFAIL: memoria agotada", "192.168.50.2")
    assert r["resultado"] == "guardado", r
    for i in range(6):
        ingest.procesar_mensaje(conn, f"<12>R2-LAB: %SEC_LOGIN-4-LOGIN_FAILED: Login failed [user: x{i}] "
                                      "[Source: 10.0.0.9]", "192.168.50.2")
    textos = " | ".join(t for _, _, t in telegram_falso)
    assert "[CRÍTICO] sev 2 en R2-LAB" in textos
    assert textos.count("[DETECCION]") == 1 and "fuerza bruta" in textos.lower()  # la detección se avisa una vez


def test_el_texto_del_log_se_envia_limpio_y_recortado(telegram_falso):
    telegram.notificar("x", "linea\x1b[31m roja\x00" + "A" * 5000)
    [(_, _, texto)] = telegram_falso
    assert "\x1b" not in texto and "\x00" not in texto and len(texto) <= telegram.LARGO_MAXIMO + 20


def test_la_api_nunca_muestra_el_token(client, telegram_falso):
    r = client.get("/api/sistema/telegram").json()
    assert r["configurado"] is True and r["token"] == TOKEN_PRUEBA[:4] + "…"
    assert TOKEN_PRUEBA not in str(r) and CHAT_PRUEBA not in str(r)


def test_error_de_telegram_no_filtra_el_token(client, monkeypatch, telegram_falso):
    def falla(token, chat, texto):
        raise OSError(f"no se pudo abrir https://api.telegram.org/bot{token}/sendMessage")
    monkeypatch.setattr(telegram, "_enviar_http", falla)
    r = client.post("/api/sistema/telegram/prueba")
    assert r.status_code == 502
    assert TOKEN_PRUEBA not in r.text and "***" in r.text


def test_mensaje_de_prueba_solo_administrador(como, telegram_falso):
    assert como("oper").post("/api/sistema/telegram/prueba").status_code == 403
    assert como("admin1").post("/api/sistema/telegram/prueba").status_code == 200
    assert len(telegram_falso) == 1


# ---------------------------------------------------------------- Red de gestión

EQUIPOS_LAB = [{"id": i, "ip": f"192.168.50.{i}"} for i in range(1, 5)]


def test_sin_ip_en_la_red_y_sin_respuestas_no_hay_red_de_gestion():
    caidos = [(False, None)] * 4
    assert monitoreo.hay_red_de_gestion(EQUIPOS_LAB, caidos, locales=["10.20.30.40"]) is False
    assert monitoreo.hay_red_de_gestion(EQUIPOS_LAB, caidos, locales=["192.168.50.10"]) is True
    assert monitoreo.hay_red_de_gestion(EQUIPOS_LAB, [(True, 2)] + caidos[1:], locales=[]) is True  # equipos tras un router


def test_sin_red_de_gestion_un_solo_aviso_y_ningun_equipo_caido(conn, client, telegram_falso, monkeypatch):
    monkeypatch.setitem(monitoreo.RED_GESTION, "conectado", None)
    equipos = [dict(conn.execute("SELECT * FROM devices").fetchone())]
    assert monitoreo.actualizar_red(conn, False, equipos) is True
    assert monitoreo.actualizar_red(conn, False, equipos) is False  # no se repite
    assert [t for _, _, t in telegram_falso][0].startswith("NOC Syslog · [SIN RED]")
    client.post("/api/devices", json={"nombre": "R1-LAB", "ip": "192.168.50.1", "marca": "Cisco", "origen": "real"})
    d = client.get("/api/dashboard").json()
    assert d["atencion"][0]["tipo"] == "red"
    assert d["equipos"][0]["estado_operativo"] == "desconocido"
    assert not any(a["tipo"] == "sin_comunicacion" for a in d["atencion"])
    monitoreo.actualizar_red(conn, True, equipos)
    assert "[RED OK]" in telegram_falso[-1][2]
