"""El ambiente llega hasta donde se usa: el padrón y la factura emitida.

🔴 **Dos defectos, y el segundo es una regresión que trae el bump del pin.**

`GET /api/consultar-cuit` leía `arca["certificado_path"]` **directo**. Desde que
una instancia guarda dos pares de credenciales (LibraCore v1.71.0), esas
columnas —las que no llevan sufijo— son las de **producción**:

1. Autenticaba con el certificado **real** contra el WSAA de `arca["ambiente"]`.
   En una instancia de homologación, eso es firmar con la credencial del cliente
   creyendo que se prueba.
2. Tras la migración `0007`, una instancia en homologación —**las demos**— tiene
   esas columnas vacías, así que el endpoint contestaría **503 "Configurá los
   certificados"** sobre una instancia que los tiene cargados.

El barrido de accesos directos de LibraCore recorre el AST de `libracore/` y no
ve este archivo: vive en el producto.

> 🔑 **Se entra por el endpoint, no por la función del motor.** La primera
> versión de estos tests (en Contalibra) llamaba a `paths_en_disco()` directo y
> 3 de 4 mutaciones sobre `app/` sobrevivieron: medían el motor, no el producto.
"""

import asyncio
import datetime

import pytest
from libracore.config_manager import ARCHIVOS_POR_AMBIENTE

from app import database as db

CERT_HOMO, CLAVE_HOMO = ARCHIVOS_POR_AMBIENTE["homologacion"]
CERT_PROD, CLAVE_PROD = ARCHIVOS_POR_AMBIENTE["produccion"]

HOY = datetime.date.today().isoformat()


@pytest.fixture
def instancia_en_homologacion(tmp_path, monkeypatch):
    """Los **dos** pares cargados y el selector en homologación — el estado
    exacto en el que se acompaña al cliente.

    🔑 Los dos, no uno: con sólo el de homologación, "usó el correcto" y "usó el
    único que había" son indistinguibles.
    """
    from libracore import config_manager

    d = tmp_path / "arca_certs"
    d.mkdir()
    for nombre in (CERT_HOMO, CLAVE_HOMO, CERT_PROD, CLAVE_PROD):
        (d / nombre).write_text(nombre)
    monkeypatch.setattr(config_manager, "CERTS_DIR", str(d))

    db.crear_arca_config(
        empresa="default", cuit="20111111119", punto_venta=1,
        clave_path=str(d / CLAVE_PROD), certificado_path=str(d / CERT_PROD),
        ambiente="homologacion",
    )
    db.actualizar_arca_config(
        "default",
        certificado_path_homologacion=str(d / CERT_HOMO),
        clave_path_homologacion=str(d / CLAVE_HOMO),
    )
    return d


def _patchear_arca(monkeypatch, usados):
    from app import arca_wsaa, arca_wspadron

    async def _capturar(cert, clave, ambiente, servicio=""):
        usados.update(cert=cert, clave=clave, ambiente=ambiente)
        return {"token": "t", "sign": "s"}

    async def _padron(*a, **k):
        return {"razon_social": "Alguien SA"}

    monkeypatch.setattr(arca_wsaa, "autenticar", _capturar)
    monkeypatch.setattr(arca_wspadron, "consultar_persona", _padron)


# -- El padrón --------------------------------------------------------------

def test_el_padron_autentica_con_el_par_del_ambiente(
        admin_client, instancia_en_homologacion, monkeypatch):
    """🔴 El defecto: leyendo las columnas directo, este endpoint salía a
    autenticar con el certificado **de producción** —el real del cliente—."""
    usados = {}
    _patchear_arca(monkeypatch, usados)

    r = admin_client.get("/api/consultar-cuit/20111111119")
    assert r.status_code == 200, r.text

    assert usados["ambiente"] == "homologacion"
    assert usados["cert"].endswith(CERT_HOMO), (
        f"autenticó con {usados['cert']} — tiene que ser el par de homologación")
    assert usados["clave"].endswith(CLAVE_HOMO)


def test_el_padron_en_produccion_usa_el_par_real(
        admin_client, instancia_en_homologacion, monkeypatch):
    """El control: si el endpoint pidiera **siempre** el de homologación, el
    test de arriba pasaría igual."""
    db.actualizar_arca_config("default", ambiente="produccion")
    usados = {}
    _patchear_arca(monkeypatch, usados)

    r = admin_client.get("/api/consultar-cuit/20111111119")
    assert r.status_code == 200, r.text
    assert usados["ambiente"] == "produccion"
    assert usados["cert"].endswith(CERT_PROD)


def test_una_demo_migrada_puede_consultar_el_padron(
        admin_client, tmp_path, monkeypatch):
    """🔴 La regresión que trae el bump: tras la `0007` una instancia en
    homologación tiene las columnas de producción **vacías**, que es lo que el
    endpoint miraba para decidir el 503."""
    from libracore import config_manager

    d = tmp_path / "arca_certs"
    d.mkdir()
    for nombre in (CERT_HOMO, CLAVE_HOMO):
        (d / nombre).write_text(nombre)
    monkeypatch.setattr(config_manager, "CERTS_DIR", str(d))

    db.crear_arca_config(
        empresa="default", cuit="20111111119", punto_venta=1,
        clave_path="", certificado_path="", ambiente="homologacion",
    )
    db.actualizar_arca_config(
        "default",
        certificado_path_homologacion=str(d / CERT_HOMO),
        clave_path_homologacion=str(d / CLAVE_HOMO),
    )
    _patchear_arca(monkeypatch, {})

    r = admin_client.get("/api/consultar-cuit/20111111119")
    assert r.status_code == 200, (
        "503 sobre una instancia que SÍ tiene su par cargado: " + r.text)


def test_sin_credenciales_sigue_dando_el_503(admin_client, tmp_path, monkeypatch):
    """Una instancia que de verdad no configuró ARCA sigue recibiendo el
    mensaje que la manda a Configuración."""
    from libracore import config_manager

    d = tmp_path / "arca_certs"
    d.mkdir()
    monkeypatch.setattr(config_manager, "CERTS_DIR", str(d))

    r = admin_client.get("/api/consultar-cuit/20111111119")
    assert r.status_code == 503
    assert "Configurá los certificados" in r.json()["error"]


# -- La factura de una venta ------------------------------------------------

def _venta_cobrada() -> int:
    return db.create_venta(
        numero="V-0001", fecha=HOY,
        items=[{"description": "Milanesa", "qty": 1, "unit_price": 8000.0,
                "subtotal": 8000.0}],
        subtotal=8000.0, descuento=0.0, total=8000.0,
        cliente_id=None, cliente_nombre="Mesa 4", usuario_id=None,
    )


def test_la_factura_de_una_venta_registra_el_ambiente_con_el_que_se_numero(
        client, monkeypatch):
    """🔴 Un comprobante emitido contra homologación trae CAE y numeración del
    WSFE de homologación. Sin marcarlo entra al Libro IVA del cliente.

    🔑 Se parchea el numerador **a propósito**: con `ENV=development` ese llamado
    devuelve `"_dev_mock_"` y **todo sale `produccion`**, así que marcar bien y
    marcar siempre `produccion` dan idéntico resultado y la mutación es
    invisible.
    """
    from app import venta_facturacion

    async def _numero_de_homologacion(punto_venta, tipo):
        return 501, None, {"ambiente": "homologacion", "cuit": "20111111119"}

    monkeypatch.setattr(venta_facturacion, "get_next_numero_with_arca",
                        _numero_de_homologacion)

    factura = asyncio.run(venta_facturacion.facturar_venta(_venta_cobrada()))
    guardada = db.get_factura(factura["id"])
    assert guardada["numero"] == 501, "no corrió el numerador parcheado"
    assert guardada["ambiente"] == "homologacion", (
        "la factura quedó marcada como real: entra al Libro IVA del cliente")


def test_y_en_produccion_la_marca_como_real(client, monkeypatch):
    """El control positivo: marcar **todo** como homologación pasaría el test de
    arriba — y sacaría del Libro IVA los comprobantes reales, que es peor."""
    from app import venta_facturacion

    async def _numero_real(punto_venta, tipo):
        return 84, None, {"ambiente": "produccion", "cuit": "20111111119"}

    monkeypatch.setattr(venta_facturacion, "get_next_numero_with_arca", _numero_real)

    factura = asyncio.run(venta_facturacion.facturar_venta(_venta_cobrada()))
    guardada = db.get_factura(factura["id"])
    assert guardada["numero"] == 84
    assert guardada["ambiente"] == "produccion"


def test_sin_arca_configurado_la_factura_es_real(client, monkeypatch):
    """Sin ARCA no hay CAE y el número es el de la propia instancia: ese
    comprobante **es** el real del cliente y tiene que entrar al Libro IVA."""
    from app import venta_facturacion

    async def _sin_arca(punto_venta, tipo):
        return 1, None, None

    monkeypatch.setattr(venta_facturacion, "get_next_numero_with_arca", _sin_arca)

    factura = asyncio.run(venta_facturacion.facturar_venta(_venta_cobrada()))
    assert db.get_factura(factura["id"])["ambiente"] == "produccion"
