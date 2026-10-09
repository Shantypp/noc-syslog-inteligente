"""Pruebas de la Fase 2: CRUD del inventario (RF-01)."""

R1 = {"nombre": "R1-NOC", "ip": "192.0.2.1", "marca": "Cisco", "modelo": "Catalyst (simulado)"}


def test_crear_y_listar(client):
    r = client.post("/api/devices", json=R1)
    assert r.status_code == 201
    creado = r.json()
    assert creado["id"] > 0
    assert creado["origen"] == "simulado"  # por defecto todo queda rotulado como simulado
    assert [d["nombre"] for d in client.get("/api/devices").json()] == ["R1-NOC"]


def test_editar_cambia_datos(client):
    device_id = client.post("/api/devices", json=R1).json()["id"]
    r = client.put(f"/api/devices/{device_id}", json={**R1, "ubicacion": "Rack 3", "estado": "inactivo"})
    assert r.status_code == 200
    assert r.json()["ubicacion"] == "Rack 3"
    assert r.json()["estado"] == "inactivo"


def test_eliminar(client):
    device_id = client.post("/api/devices", json=R1).json()["id"]
    assert client.delete(f"/api/devices/{device_id}").status_code == 204
    assert client.get(f"/api/devices/{device_id}").status_code == 404


def test_ip_invalida_es_rechazada(client):
    r = client.post("/api/devices", json={**R1, "ip": "999.1.1.1"})
    assert r.status_code == 422


def test_marca_no_soportada_es_rechazada(client):
    r = client.post("/api/devices", json={**R1, "marca": "Juniper"})
    assert r.status_code == 422


def test_ip_duplicada_devuelve_409(client):
    client.post("/api/devices", json=R1)
    r = client.post("/api/devices", json={**R1, "nombre": "OTRO"})
    assert r.status_code == 409


def test_equipo_inexistente_devuelve_404(client):
    assert client.get("/api/devices/999").status_code == 404
    assert client.put("/api/devices/999", json=R1).status_code == 404
    assert client.delete("/api/devices/999").status_code == 404


def test_filtro_por_marca(client):
    client.post("/api/devices", json=R1)
    client.post("/api/devices", json={"nombre": "FW-EDGE", "ip": "192.0.2.2", "marca": "Fortinet"})
    r = client.get("/api/devices", params={"marca": "Fortinet"})
    assert [d["nombre"] for d in r.json()] == ["FW-EDGE"]
