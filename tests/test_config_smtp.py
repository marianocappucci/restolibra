"""Config SMTP por backoffice (libraauth v0.6.0), endpoints propios de este
producto bajo `/api/config/smtp`.

**Por que existe este archivo y no alcanza con la suite del motor**: el cableado
se hace a mano en cada producto (repositorio en `db_usuarios.py`, re-exports en
`database.py`, endpoints en `web/api/config.py`), y un olvido en cualquiera de
los tres pasos no lo ve nadie hasta que alguien abre la pantalla. Lo que se
prueba aca es **el cableado**, no la logica del motor.

Y hay una razon concreta para no haberlo verificado por inspeccion: mirar
`app.routes` **no sirve** en esta version de FastAPI —los routers incluidos
quedan como `_IncludedRouter` sin `.path`, asi que filtrar ahi da un falso "no
esta montado"—. Lo inequivoco es pedirle al endpoint.
"""
from app import db_usuarios


def test_sin_sesion_no_se_puede_leer(client):
    """404 seria "no esta montado"; 401/403 es "montado y protegido"."""
    assert client.get("/api/config/smtp").status_code in (401, 403)


def test_admin_lee_el_estado_inicial(admin_client):
    r = admin_client.get("/api/config/smtp")
    assert r.status_code == 200
    body = r.json()
    # Sin nada guardado, la config sale del entorno: es lo que hace que
    # adoptar la v0.6.0 no cambie el comportamiento de la instancia.
    assert body["origen"] == "entorno"
    assert body["password_definida"] is False


def test_guardar_y_leer_sin_que_la_contrasena_salga_nunca(admin_client):
    """El test central: la contrasena viaja hacia adentro y **no vuelve**."""
    r = admin_client.put("/api/config/smtp", json={
        "host": "smtp.empresa.test", "port": 2525, "user": "cuenta",
        "password": "hunter2", "from_email": "no-reply@empresa.test",
        "from_name": "Soporte",
    })
    assert r.status_code == 200, r.text
    assert "hunter2" not in r.text
    assert r.json()["password_definida"] is True

    lectura = admin_client.get("/api/config/smtp")
    assert "hunter2" not in lectura.text
    assert lectura.json()["origen"] == "base"
    assert lectura.json()["host"] == "smtp.empresa.test"


def test_en_la_base_queda_cifrada(admin_client):
    """La mitigacion que justifica guardar la credencial en la base del
    cliente: el archivo por si solo no alcanza para mandar correo."""
    admin_client.put("/api/config/smtp", json={
        "host": "smtp.empresa.test", "password": "hunter2",
        "from_email": "no-reply@empresa.test"})

    with db_usuarios._sessions() as s:
        from sqlalchemy import text
        crudo = s.execute(text("SELECT password_cifrada FROM smtp_settings")).scalar_one()
    assert crudo.startswith("v1:")
    assert "hunter2" not in crudo


def test_editar_sin_mandar_la_contrasena_la_conserva(admin_client):
    """Cambiar el remitente no tiene por que obligar a tipearla de nuevo."""
    admin_client.put("/api/config/smtp", json={
        "host": "smtp.empresa.test", "password": "hunter2",
        "from_email": "no-reply@empresa.test"})
    r = admin_client.put("/api/config/smtp", json={
        "host": "smtp-nuevo.test", "from_email": "no-reply@empresa.test"})

    assert r.json()["password_definida"] is True
    assert r.json()["host"] == "smtp-nuevo.test"


def test_borrar_vuelve_al_entorno(admin_client):
    admin_client.put("/api/config/smtp", json={
        "host": "smtp.empresa.test", "from_email": "no-reply@empresa.test"})
    r = admin_client.delete("/api/config/smtp")
    assert r.status_code == 200
    assert r.json()["origen"] == "entorno"


def test_host_vacio_da_422(admin_client):
    assert admin_client.put("/api/config/smtp", json={"host": "   "}).status_code == 422
