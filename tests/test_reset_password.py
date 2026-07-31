"""Recuperacion de contrasena (libraauth v0.5.0 via endpoints propios).

Hasta hoy este flujo solo se habia verificado a mano dentro del
contenedor de dev (ver wiki/entities/restolibra.md) porque no habia
suite. El correo NO se manda: se inyecta un transporte falso por el seam
oficial del servicio (`_send_email`) y se captura el token del cuerpo,
que es exactamente lo que haria el SMTP real.
"""
import re

import pytest

from app import db_usuarios
from libraauth.email_sender import SmtpConfig
from tests.conftest import ADMIN_USER


@pytest.fixture()
def mail_capturado(monkeypatch):
    """SMTP 'configurado' + transporte falso que guarda los correos."""
    correos = []

    def _fake_send(*, to_email, asunto, cuerpo):
        correos.append({"to": to_email, "asunto": asunto, "cuerpo": cuerpo})

    monkeypatch.setattr(db_usuarios._password_reset, "smtp_config",
                        SmtpConfig(host="smtp.suite.test", from_email="noreply@suite.test"))
    monkeypatch.setattr(db_usuarios._password_reset, "_send_email", _fake_send)
    return correos


def _token_de(correo: dict) -> str:
    m = re.search(r"reset-password\?token=([A-Za-z0-9_\-]+)", correo["cuerpo"])
    assert m, f"el cuerpo no trae el enlace con token: {correo['cuerpo']!r}"
    return m.group(1)


def _dar_email_al_admin(client):
    login = client.post("/api/login", json={"username": ADMIN_USER, "password": "admin-suite-1234"})
    assert login.status_code == 200
    admin = client.get("/api/me").json()
    # ensure_admin_user crea al admin sin email; el flujo lo necesita.
    usuarios = client.get("/api/usuarios").json()
    uid = next(u["id"] for u in usuarios if u["username"] == ADMIN_USER)
    resp = client.put(f"/api/usuarios/{uid}", json={
        "nombre": admin["nombre"], "email": "admin@suite.test", "role": "admin",
    })
    assert resp.status_code == 200
    client.post("/api/logout")


def test_forgot_password_sin_smtp_503(client):
    resp = client.post("/api/forgot-password", json={"identificador": ADMIN_USER})
    assert resp.status_code == 503


def test_forgot_password_responde_igual_exista_o_no(client, mail_capturado):
    _dar_email_al_admin(client)
    existe = client.post("/api/forgot-password", json={"identificador": ADMIN_USER})
    no_existe = client.post("/api/forgot-password", json={"identificador": "fantasma"})
    # Misma respuesta (status y cuerpo): distinguirlas seria un buscador
    # de usuarios dados de alta.
    assert existe.status_code == no_existe.status_code == 200
    assert existe.json() == no_existe.json()
    # Pero el correo salio solo para el que existe.
    assert len(mail_capturado) == 1
    assert mail_capturado[0]["to"] == "admin@suite.test"


def test_reset_token_invalido_400(client):
    resp = client.post("/api/reset-password",
                       json={"token": "token-falso", "new_password": "nueva-123456"})
    assert resp.status_code == 400


def test_flujo_completo_de_reset(client, mail_capturado):
    _dar_email_al_admin(client)
    client.post("/api/forgot-password", json={"identificador": ADMIN_USER})
    token = _token_de(mail_capturado[0])

    resp = client.post("/api/reset-password",
                       json={"token": token, "new_password": "recuperada-99"})
    assert resp.status_code == 200

    # La vieja ya no sirve; la nueva si.
    assert client.post("/api/login", json={
        "username": ADMIN_USER, "password": "admin-suite-1234"}).status_code == 401
    assert client.post("/api/login", json={
        "username": ADMIN_USER, "password": "recuperada-99"}).status_code == 200


def test_reset_no_crea_sesion(client, mail_capturado):
    _dar_email_al_admin(client)
    client.post("/api/forgot-password", json={"identificador": ADMIN_USER})
    token = _token_de(mail_capturado[0])
    client.post("/api/reset-password", json={"token": token, "new_password": "recuperada-99"})
    assert client.get("/api/me").status_code == 401


def test_token_es_de_un_solo_uso(client, mail_capturado):
    _dar_email_al_admin(client)
    client.post("/api/forgot-password", json={"identificador": ADMIN_USER})
    token = _token_de(mail_capturado[0])
    assert client.post("/api/reset-password", json={
        "token": token, "new_password": "primera-vez-9"}).status_code == 200
    # Reusarlo tiene que fallar Y no cambiar la contrasena de nuevo.
    assert client.post("/api/reset-password", json={
        "token": token, "new_password": "segunda-vez-9"}).status_code == 400
    assert client.post("/api/login", json={
        "username": ADMIN_USER, "password": "primera-vez-9"}).status_code == 200
