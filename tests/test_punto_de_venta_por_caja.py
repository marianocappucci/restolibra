"""El punto de venta de ARCA por mostrador, desde la API del producto.

La logica vive en LibraCore y tiene sus propios tests; esto verifica que el
producto la EXPONGA -- sin esto, la columna existe y nadie puede cargarla, que
es lo mismo que no tenerla.
"""


def test_una_caja_se_crea_sin_punto_de_venta(admin_client):
    """🔴 El caso de toda instancia con un solo POS.

    El campo es opcional y su ausencia significa "usa el de la empresa". Si
    fuera obligatorio, la pantalla de cajas dejaría de funcionar en los clientes
    que hoy la usan.
    """
    resp = admin_client.post("/api/cajas", json={
        "nombre": "Mostrador", "descripcion": "", "medios_pago": ["efectivo"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["punto_venta"] is None


def test_una_caja_se_crea_con_su_punto_de_venta(admin_client):
    resp = admin_client.post("/api/cajas", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"],
        "punto_venta": 4})
    assert resp.status_code == 200, resp.text
    assert resp.json()["punto_venta"] == 4


def test_el_punto_de_venta_se_edita(admin_client):
    creada = admin_client.post("/api/cajas", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"]}).json()

    resp = admin_client.put(f"/api/cajas/{creada['id']}", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"],
        "activo": True, "punto_venta": 6})

    assert resp.status_code == 200, resp.text
    assert resp.json()["punto_venta"] == 6


def test_se_puede_volver_a_dejarlo_vacio(admin_client):
    """Sacarle el punto de venta a una caja la devuelve al de la empresa.

    Sin esto, poner un valor por error sería irreversible desde la pantalla.
    """
    creada = admin_client.post("/api/cajas", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"],
        "punto_venta": 8}).json()

    resp = admin_client.put(f"/api/cajas/{creada['id']}", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"],
        "activo": True, "punto_venta": None})

    assert resp.status_code == 200, resp.text
    assert resp.json()["punto_venta"] is None


def test_repetir_el_punto_de_venta_da_409_y_nombra_la_otra_caja(admin_client):
    """🔴 409 y no 500: no es un error del sistema, es un dato que ya está usado.

    Y el mensaje tiene que decir **cuál** caja lo tiene, porque quien lo está
    configurando no se acuerda de memoria qué punto de venta le puso a cada
    mostrador.
    """
    admin_client.post("/api/cajas", json={
        "nombre": "POS 1", "descripcion": "", "medios_pago": ["efectivo"],
        "punto_venta": 3})

    resp = admin_client.post("/api/cajas", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"],
        "punto_venta": 3})

    assert resp.status_code == 409, resp.text
    assert "POS 1" in resp.json()["detail"]


def test_editar_hacia_uno_ocupado_tambien_da_409(admin_client):
    admin_client.post("/api/cajas", json={
        "nombre": "POS 1", "descripcion": "", "medios_pago": ["efectivo"],
        "punto_venta": 3})
    otra = admin_client.post("/api/cajas", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"],
        "punto_venta": 4}).json()

    resp = admin_client.put(f"/api/cajas/{otra['id']}", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"],
        "activo": True, "punto_venta": 3})

    assert resp.status_code == 409, resp.text


def test_guardar_una_caja_con_el_punto_de_venta_que_ya_tenia_anda(admin_client):
    """Es lo que hace la pantalla cada vez que se toca cualquier otro campo.

    Si chocara consigo misma, editar el nombre de una caja con punto de venta
    sería imposible.
    """
    creada = admin_client.post("/api/cajas", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"],
        "punto_venta": 5}).json()

    resp = admin_client.put(f"/api/cajas/{creada['id']}", json={
        "nombre": "POS 2 renombrado", "descripcion": "",
        "medios_pago": ["efectivo"], "activo": True, "punto_venta": 5})

    assert resp.status_code == 200, resp.text
    assert resp.json()["nombre"] == "POS 2 renombrado"


def test_el_listado_devuelve_el_punto_de_venta(admin_client):
    """La pantalla lo lee de acá para precargar el formulario."""
    admin_client.post("/api/cajas", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"],
        "punto_venta": 7})

    cajas = admin_client.get("/api/cajas").json()
    assert any(c.get("punto_venta") == 7 for c in cajas), (
        "sin esto la pantalla no puede mostrar lo que ya está guardado"
    )


def test_el_formulario_de_facturacion_toma_el_del_pos(admin_client):
    """🔴 La cadena completa, que es lo que el pedido pedía.

    `/api/facturas/tipos` es lo que precarga el formulario. Con un turno abierto
    en una caja con punto de venta propio, tiene que devolver ese y no el de la
    empresa.
    """
    from libracore.db import caja as db_caja
    from libracore.db import turnos as db_turnos

    from app.db_core import get_connection

    de_la_empresa = admin_client.get("/api/facturas/tipos").json()["punto_venta"]

    creada = admin_client.post("/api/cajas", json={
        "nombre": "POS 2", "descripcion": "", "medios_pago": ["efectivo"],
        "punto_venta": de_la_empresa + 41}).json()

    with get_connection() as conn:
        usuario = conn.execute(
            "SELECT id FROM usuarios WHERE username = 'admin'").fetchone()[0]
    db_turnos.create_turno(usuario, 0, "", caja_id=creada["id"])

    del db_caja  # sólo se importa para dejar explícita la dependencia
    assert admin_client.get("/api/facturas/tipos").json()["punto_venta"] == (
        de_la_empresa + 41
    )
