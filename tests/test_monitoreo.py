"""Pruebas del monitoreo por ping: saber si un equipo real está vivo aunque no envíe mensajes."""

import pytest

from app.api.dashboard import estado_equipos
from app.collector.monitoreo import COMPONENTE, interpretar_ping, registrar_resultado
from app.database import get_connection, init_db
from app.utils import a_texto, ahora_utc


@pytest.mark.parametrize("salida,codigo,esperado", [
    ("Respuesta desde 192.168.50.1: bytes=32 tiempo=2ms TTL=255", 0, (True, 2)),            # Windows en español
    ("Reply from 192.168.50.1: bytes=32 time<1ms TTL=255", 0, (True, 1)),                   # Windows en inglés
    ("64 bytes from 192.168.50.1: icmp_seq=1 ttl=255 time=0.512 ms", 0, (True, 1)),         # Linux
    ("Respuesta desde 192.168.50.10: Host de destino inaccesible.", 0, (False, None)),      # Windows: código 0 sin TTL
    ("Tiempo de espera agotado para esta solicitud.", 1, (False, None)),
])
def test_interpretar_la_salida_del_ping(salida, codigo, esperado):
    assert interpretar_ping(salida, codigo) == esperado


@pytest.fixture
def conn(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    c = get_connection(path)
    c.execute("INSERT INTO devices (nombre, ip, marca, origen) VALUES ('R2-LAB', '192.168.50.2', 'Cisco', 'real')")
    c.commit()
    yield c
    c.close()


def equipo(conn):
    return dict(conn.execute("SELECT * FROM devices WHERE id = 1").fetchone())


def test_un_ping_perdido_no_basta_para_declararlo_caido(conn):
    registrar_resultado(conn, equipo(conn), True, 2)
    assert registrar_resultado(conn, equipo(conn), False, None) is None
    assert registrar_resultado(conn, equipo(conn), False, None) is None
    assert equipo(conn)["alcanzable"] == 1  # 2 fallos: todavía se considera vivo
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0


def test_caida_y_recuperacion_quedan_registradas_y_el_incidente_se_recupera(conn):
    registrar_resultado(conn, equipo(conn), True, 2)
    for _ in range(3):
        caida = registrar_resultado(conn, equipo(conn), False, None)
    ev = dict(conn.execute("SELECT * FROM events WHERE id = ?", (caida,)).fetchone())
    assert ev["severidad"] == 2 and ev["componente"] == COMPONENTE and ev["estado_componente"] == "Caído"
    assert equipo(conn)["alcanzable"] == 0
    # Una persona abre el incidente por la caída
    conn.execute("INSERT INTO incidents (event_id, device_id, titulo, severidad) VALUES (?, 1, 'R2-LAB caído', 2)", (caida,))
    conn.commit()
    vuelta = registrar_resultado(conn, equipo(conn), True, 3)
    ev = dict(conn.execute("SELECT * FROM events WHERE id = ?", (vuelta,)).fetchone())
    assert ev["estado_componente"] == "Arriba" and "3 ms" in ev["mensaje"]
    assert conn.execute("SELECT recuperado_en FROM incidents WHERE id = 1").fetchone()[0] is not None


def test_un_equipo_que_responde_al_ping_esta_activo_aunque_no_envie_mensajes(conn):
    conn.execute("UPDATE devices SET alcanzable = 1, ultimo_ping = ?, latencia_ms = 2 WHERE id = 1", (a_texto(ahora_utc()),))
    conn.commit()
    [e] = estado_equipos(conn)
    assert e["estado_operativo"] == "activo" and e["conectividad"] == "Responde al ping · 2 ms"


def test_un_equipo_que_no_responde_al_ping_queda_sin_comunicacion(conn):
    conn.execute("UPDATE devices SET alcanzable = 0, ultimo_ping = ? WHERE id = 1", (a_texto(ahora_utc()),))
    conn.commit()
    [e] = estado_equipos(conn)
    assert e["estado_operativo"] == "sin_comunicacion" and e["conectividad"] == "No responde al ping"


def test_si_el_ping_esta_desactivado_se_usa_el_ultimo_evento(conn):
    from app import config
    config.guardar(conn, "intervalo_ping_s", 0, "prueba")
    conn.execute("UPDATE devices SET alcanzable = 1, ultimo_ping = ? WHERE id = 1", (a_texto(ahora_utc()),))
    conn.commit()
    [e] = estado_equipos(conn)
    assert e["estado_operativo"] == "sin_comunicacion" and e["conectividad"] is None  # sin eventos y sin ping
