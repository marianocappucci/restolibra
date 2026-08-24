"""La pantalla de ARCA, ahora del motor.

El mecanismo lo prueba `libracore`. Lo que se prueba acá es **el montaje**: que
las rutas nuevas existan y estén gateadas, que las viejas ya no, y —lo que este
producto no tenía— que subir un archivo equivocado se rechace **antes** de
tocar el disco.

> 🔴 Hasta el 2026-08-24 `POST /api/config/arca/certificados` escribía los bytes
> que llegaran. Subir el `.csr` —el pedido— en vez del `.crt` que ARCA devuelve
> se aceptaba en pantalla y fallaba recién al emitir el primer comprobante, con
> un error de ARCA que no habla de la causa.
"""

import datetime

import pytest
from conftest import ADMIN_PASS, ADMIN_USER
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

RUTA = "/api/config/arca"


def _par():
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    ahora = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nombre).issuer_name(nombre)
        .public_key(clave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(ahora - datetime.timedelta(days=1))
        .not_valid_after(ahora + datetime.timedelta(days=730))
        .sign(clave, hashes.SHA256())
    )
    return (
        cert.public_bytes(serialization.Encoding.PEM),
        clave.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.TraditionalOpenSSL,
                            serialization.NoEncryption()),
    )


def _csr():
    """El pedido, que es lo que se sube por error en vez del certificado."""
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "pedido")]))
        .sign(clave, hashes.SHA256())
    ).public_bytes(serialization.Encoding.PEM)


def _subir(cliente, que, contenido, nombre="archivo.pem"):
    return cliente.post(
        f"{RUTA}/{que}",
        files={"archivo": (nombre, contenido, "application/octet-stream")},
    )


# ── El montaje ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ruta", [RUTA, f"{RUTA}/estado"])
def test_las_rutas_nuevas_existen(admin_client, ruta):
    """No 404. El contenido lo prueban los tests de abajo; acá lo que se fija es
    que el router esté montado en el prefijo que la SPA consume.

    ⚠️ `certificado-info` no entra en esta lista: **devuelve 404 legítimo**
    cuando la instancia no tiene configuración, así que "no da 404" no
    distingue ahí una ruta que existe de una que no. Se prueba aparte, con
    configuración cargada.
    """
    assert admin_client.get(ruta).status_code != 404, f"{ruta} no existe"


def test_certificado_info_devuelve_los_datos_del_certificado(admin_client):
    certificado, clave = _par()
    _subir(admin_client, "certificado", certificado)
    _subir(admin_client, "clave", clave)
    info = admin_client.get(f"{RUTA}/certificado-info").json()
    assert "error" not in info, info
    assert info["vencido"] is False
    assert info["dias_restantes"] > 700


@pytest.mark.parametrize("ruta", [
    "/api/arca/estado",
    "/api/arca/probar",
    "/api/arca/certificado-info",
    f"{RUTA}/certificados",
])
def test_las_rutas_viejas_ya_no_estan(admin_client, ruta):
    """La otra mitad. Sin esto, "las nuevas existen" pasaría igual con las dos
    versiones montadas al mismo tiempo.

    🔴 **No se mide con el 404**, y la primera versión de este test sí lo hacía.
    Cuando `frontend/dist` existe —o sea después de cualquier build— el
    catch-all del SPA sirve el `index.html` para todo lo que no matcheó, así que
    una ruta borrada devuelve **200 con HTML**. El test pasaba corriéndolo solo
    y fallaba en la suite completa, que es cuando el build ya había corrido.

    Lo que sí distingue: una ruta de API viva contesta **JSON**. Si lo que
    vuelve es HTML, no matcheó ninguna ruta y cayó al SPA; si es 404, tampoco
    existe.
    """
    r = admin_client.get(ruta)
    tipo = r.headers.get("content-type", "")
    assert r.status_code == 404 or "text/html" in tipo, (
        f"{ruta} sigue viva: contestó {r.status_code} {tipo}"
    )


def test_el_control_positivo_de_lo_de_arriba(admin_client):
    """🔑 Sin esto, el test de las rutas viejas pasaría igual con la API entera
    caída: todo daría HTML del catch-all y se leería como "ninguna vieja quedó".

    Una ruta de API que SÍ existe tiene que contestar JSON.
    """
    r = admin_client.get(f"{RUTA}/estado")
    assert r.status_code == 200
    assert "application/json" in r.headers.get("content-type", "")


def test_todo_el_router_es_de_admin(client):
    """Las dos mitades sobre el MISMO cliente.

    ⚠️ No se piden `client` y `admin_client` juntos: `admin_client` loguea
    **sobre** `client` y devuelve el mismo objeto, así que pedir los dos da dos
    nombres para un cliente ya autenticado --- y la mitad negativa pasaría por
    la razón equivocada.
    """
    assert client.get(RUTA).status_code in (401, 403)
    assert client.post("/api/login", json={
        "username": ADMIN_USER, "password": ADMIN_PASS,
    }).status_code == 200
    assert client.get(RUTA).status_code == 200


# ── Alta y lectura ──────────────────────────────────────────────────────────

def test_guardar_y_leer(admin_client):
    r = admin_client.put(RUTA, json={
        "empresa": "default", "cuit": "20289933604",
        "punto_venta": 5, "ambiente": "produccion",
    })
    assert r.status_code == 200, r.text
    leido = admin_client.get(RUTA).json()
    assert leido["cuit"] == "20289933604"
    assert leido["punto_venta"] == 5
    assert leido["ambiente"] == "produccion"
    assert leido["tiene_certificado"] is False


def test_el_get_de_config_sigue_trayendo_arca(admin_client):
    """La SPA carga toda la pantalla de una sola vez desde `/api/config`. Sacar
    el `PUT` de ahí no puede haberse llevado la lectura."""
    admin_client.put(RUTA, json={"cuit": "20289933604", "punto_venta": 3})
    datos = admin_client.get("/api/config").json()
    assert datos["arca"]["cuit"] == "20289933604"


# ── Lo que ahora se rechaza al subir ────────────────────────────────────────

def test_el_csr_se_rechaza_y_no_deja_nada_cargado(admin_client):
    """🔑 El error más común, y el que este producto aceptaba."""
    r = _subir(admin_client, "certificado", _csr(), "pedido.csr")
    assert r.status_code == 422, r.text
    assert ".csr" in r.json()["detail"]
    assert admin_client.get(RUTA).json() is None, "no puede haber quedado configuración"


def test_la_clave_en_el_campo_del_certificado_se_rechaza(admin_client):
    _, clave = _par()
    assert _subir(admin_client, "certificado", clave).status_code == 422


def test_el_par_bueno_entra(admin_client):
    certificado, clave = _par()
    assert _subir(admin_client, "certificado", certificado).status_code == 200
    r = _subir(admin_client, "clave", clave)
    assert r.status_code == 200, r.text
    assert r.json()["tiene_certificado"] is True
    assert r.json()["tiene_clave"] is True


def test_una_clave_de_otro_par_no_pisa_la_que_estaba(admin_client):
    """🔑 El chequeo que ningún nombre de archivo puede dar, y su contracara:
    que el rechazo no deje la instancia con la mitad cambiada."""
    certificado, clave = _par()
    _subir(admin_client, "certificado", certificado)
    _subir(admin_client, "clave", clave)

    _, clave_ajena = _par()
    r = _subir(admin_client, "clave", clave_ajena)
    assert r.status_code == 422
    assert "pareja" in r.json()["detail"]

    with open(admin_client.get(RUTA).json()["clave_path"], "rb") as f:
        assert f.read() == clave, "la clave buena tenía que seguir en el disco"


# ── Estado y borrado, que la pantalla no tenía ──────────────────────────────

def test_el_estado_dice_cuando_vence(admin_client):
    """🔑 Los certificados de ARCA duran dos años y el día que vencen la
    facturación deja de andar sin que nadie haya tocado nada. Antes la pantalla
    no lo mostraba."""
    certificado, clave = _par()
    _subir(admin_client, "certificado", certificado)
    _subir(admin_client, "clave", clave)

    estado = admin_client.get(f"{RUTA}/estado").json()
    assert estado["configurado"] is True
    assert estado["vencido"] is False
    assert 700 < estado["dias_para_vencer"] <= 730
    assert estado["vence"].count("-") == 2, "dd-mm-aaaa"


def test_se_pueden_sacar_las_credenciales(admin_client):
    """Antes no había forma de desconectar ARCA desde la pantalla."""
    certificado, clave = _par()
    _subir(admin_client, "certificado", certificado)
    _subir(admin_client, "clave", clave)

    r = admin_client.delete(f"{RUTA}/credenciales")
    assert r.status_code == 200, r.text
    assert r.json()["tiene_certificado"] is False
    assert admin_client.get(f"{RUTA}/estado").json()["configurado"] is False


def test_probar_sin_configuracion(admin_client):
    """`probar` pasó de `GET /api/arca/probar` a `POST` acá."""
    assert admin_client.post(f"{RUTA}/probar").status_code == 400
