"""La pantalla de ARCA, ahora del motor.

El mecanismo lo prueba `libracore` en `tests/test_arca_router.py`: que el `.csr`
y la clave en el campo del certificado se rechacen sin tocar el disco, que una
clave de otro par no pise la que estaba, el estado con el vencimiento, el
borrado de las credenciales y `probar` sin configuracion. Hasta el 2026-09-11
esos casos estaban escritos tambien aca, byte a byte en los dos productos
hermanos.

Lo que se prueba aca es **el montaje**: que las rutas nuevas existan en el
prefijo que consume la SPA y esten gateadas por el admin de ESTE producto, que
las viejas ya no, y que un par subido por la API de este producto quede donde
esta instancia lo lee (`certificado-info`, que el motor no cubre).

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
    ahora = datetime.datetime.now(datetime.UTC)
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


def _subir(cliente, que, contenido, nombre="archivo.pem"):
    return cliente.post(
        f"{RUTA}/{que}",
        files={"archivo": (nombre, contenido, "application/octet-stream")},
    )


# ── El montaje ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ruta", [RUTA, f"{RUTA}/estado"])
def test_las_rutas_nuevas_existen(admin_client, ruta):
    """No 404. El contenido lo prueba el motor; acá lo que se fija es que el
    router esté montado en el prefijo que la SPA consume.

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


# ── Alta y lectura, por la API de este producto ─────────────────────────────

def test_la_configuracion_de_arca_se_relee_por_su_propio_endpoint(admin_client):
    """Sacar el `PUT` de `/api/config` no puede haberse llevado la lectura.

    🔴 Hasta el 2026-08-30 esto se leia de `GET /api/config`, que devolvia
    `config_manager.load()` ENTERO --token de MercadoPago y contrasena de SMTP
    incluidos-- porque la pantalla vieja cargaba todo de una. Ese endpoint se
    fue con ella: cada seccion pide lo suyo.
    """
    admin_client.put(RUTA, json={"cuit": "20289933604", "punto_venta": 3})
    assert admin_client.get(RUTA).json()["cuit"] == "20289933604"


def test_el_par_bueno_entra(admin_client):
    """El camino feliz de la subida, contra el `DATA_DIR` de esta instancia: el
    rechazo de los archivos equivocados lo prueba el motor."""
    certificado, clave = _par()
    assert _subir(admin_client, "certificado", certificado).status_code == 200
    r = _subir(admin_client, "clave", clave)
    assert r.status_code == 200, r.text
    assert r.json()["tiene_certificado"] is True
    assert r.json()["tiene_clave"] is True
