"""Pruebas de inicio de sesión y permisos por rol (RBAC)."""

from tests.conftest import CLAVE_PRUEBA

EQUIPO = {"nombre": "R1-NOC", "ip": "192.0.2.1", "marca": "Cisco"}


def ejecutar(c, comando, perfil="cisco_ios"):
    return c.post("/api/console/ejecutar", json={"perfil": perfil, "comando": comando}).json()


# ---------- Inicio de sesión ----------

def test_sin_sesion_no_hay_acceso(sin_sesion):
    assert sin_sesion.get("/api/devices").status_code == 401
    assert sin_sesion.get("/api/dashboard").status_code == 401
    assert sin_sesion.get("/api/health").status_code == 200  # la salud del servicio es pública


def test_login_correcto_e_incorrecto(sin_sesion):
    r = sin_sesion.post("/api/auth/login", json={"usuario": "oper", "clave": CLAVE_PRUEBA})
    assert r.status_code == 200 and r.json()["rol"] == "operador"
    assert "httponly" in r.headers["set-cookie"].lower()          # JavaScript no puede leer la cookie
    assert sin_sesion.get("/api/auth/yo").json()["usuario"] == "oper"
    malo = sin_sesion.post("/api/auth/login", json={"usuario": "oper", "clave": "incorrecta"})
    assert malo.status_code == 401
    assert sin_sesion.post("/api/auth/login", json={"usuario": "noexiste", "clave": "x"}).json()["detail"] == malo.json()["detail"]


def test_bloqueo_tras_5_intentos_fallidos(sin_sesion):
    for _ in range(5):
        assert sin_sesion.post("/api/auth/login", json={"usuario": "lect", "clave": "mala"}).status_code == 401
    r = sin_sesion.post("/api/auth/login", json={"usuario": "lect", "clave": CLAVE_PRUEBA})
    assert r.status_code == 429  # bloqueada aunque ahora la contraseña sea correcta


def test_cerrar_sesion(como):
    c = como("oper")
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/devices").status_code == 401


def test_cambiar_mi_clave(como, sin_sesion):
    c = como("oper")
    assert c.post("/api/auth/cambiar-clave", json={"actual": "otra", "nueva": "nueva-clave-1"}).status_code == 400
    assert c.post("/api/auth/cambiar-clave", json={"actual": CLAVE_PRUEBA, "nueva": "corta"}).status_code == 422
    assert c.post("/api/auth/cambiar-clave", json={"actual": CLAVE_PRUEBA, "nueva": "nueva-clave-1"}).status_code == 200
    assert sin_sesion.post("/api/auth/login", json={"usuario": "oper", "clave": "nueva-clave-1"}).status_code == 200


# ---------- Permisos por rol ----------

def test_lector_solo_consulta(como):
    lect = como("lect")
    assert lect.get("/api/devices").status_code == 200
    assert lect.post("/api/devices", json=EQUIPO).status_code == 403
    assert lect.post("/api/incidents", json={"titulo": "x", "severidad": 1}).status_code == 403
    assert ejecutar(lect, "show version")["decision"] == "PERMITIDO"
    assert ejecutar(lect, "show logging")["decision"] == "BLOQUEADO"          # requiere operador
    assert ejecutar(lect, "configure terminal")["decision"] == "BLOQUEADO"    # no propone cambios


def test_operador_atiende_y_propone_pero_no_aprueba(como):
    oper = como("oper")
    assert oper.post("/api/devices", json=EQUIPO).status_code == 403
    assert oper.post("/api/incidents", json={"titulo": "Corte de fibra", "severidad": 1}).status_code == 201
    assert ejecutar(oper, "show logging")["decision"] == "PERMITIDO"
    propuesta = ejecutar(oper, "configure terminal")
    assert propuesta["decision"] == "PROPUESTA"
    assert oper.post(f"/api/auditoria/{propuesta['audit_id']}/aprobar", json={}).status_code == 403


def test_administrador_aplica_cambios_de_otro(como):
    propuesta = ejecutar(como("oper"), "configure terminal")
    admin = como("admin1")
    r = admin.post(f"/api/auditoria/{propuesta['audit_id']}/aprobar", json={})
    assert r.status_code == 200 and r.json()["aprobado_por"] == "admin1"


def test_la_identidad_sale_de_la_sesion_no_del_navegador(como):
    oper = como("oper")
    inc = oper.post("/api/incidents", json={"usuario": "otra-persona", "titulo": "x", "severidad": 2}).json()
    detalle = oper.get(f"/api/incidents/{inc['id']}").json()
    assert detalle["seguimiento"][0]["usuario"] == "oper"


def test_comandos_por_rol_en_los_perfiles(client):
    cisco = next(p for p in client.get("/api/console/perfiles").json() if p["id"] == "cisco_ios")
    niveles = {c["comando"]: c["rol_minimo"] for c in cisco["permitidos"]}
    assert niveles["show version"] == "lector" and niveles["show logging"] == "operador"


# ---------- Gestión de usuarios ----------

def test_solo_admin_gestiona_usuarios(como):
    assert como("oper").get("/api/usuarios").status_code == 403
    admin = como("admin1")
    nuevo = admin.post("/api/usuarios", json={"usuario": "nuevo.op", "nombre": "Nuevo", "rol": "operador", "clave": "clave-segura-9"})
    assert nuevo.status_code == 201
    assert admin.post("/api/usuarios", json={"usuario": "corto", "nombre": "X", "rol": "lector", "clave": "123"}).status_code == 422
    assert admin.post("/api/usuarios", json={"usuario": "x", "nombre": "X", "rol": "jefe", "clave": "clave-segura-9"}).status_code == 422


def test_cambiar_rol_aplica_de_inmediato(como):
    oper = como("oper")
    admin = como("admin1")
    uid = next(u["id"] for u in admin.get("/api/usuarios").json() if u["usuario"] == "oper")
    assert admin.patch(f"/api/usuarios/{uid}", json={"rol": "lector"}).status_code == 200
    assert oper.get("/api/devices").status_code == 401  # su sesión anterior se cerró


def test_siempre_queda_un_administrador(como):
    admin = como("admin1")
    ids = {u["usuario"]: u["id"] for u in admin.get("/api/usuarios").json()}
    assert admin.patch(f"/api/usuarios/{ids['admin2']}", json={"activo": False}).status_code == 200
    assert admin.patch(f"/api/usuarios/{ids['admin1']}", json={"rol": "lector"}).status_code == 409
