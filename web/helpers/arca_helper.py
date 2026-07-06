import os
import random
import datetime

import database as db
import config_manager
import arca_wsaa
import arca_wsfe


def _es_dev() -> bool:
    return os.environ.get("ENV", "") == "development"


def _mock_cae() -> dict:
    """Genera CAE y vencimiento falsos para entorno de desarrollo."""
    cae = str(random.randint(10_000_000_000_000, 99_999_999_999_999))
    vto = (datetime.date.today() + datetime.timedelta(days=10)).strftime("%Y%m%d")
    return {"cae": cae, "cae_vto": vto}


async def get_next_numero_with_arca(punto_venta: int, tipo: int):
    """
    Devuelve (numero, ta, arca).
    En dev: usa contador local y marca ta/arca como mock.
    En prod: intenta ARCA, cae a local si falla.
    """
    if _es_dev():
        numero = db.get_next_factura_numero(punto_venta, tipo)
        return numero, "_dev_mock_", "_dev_mock_"

    arca_cfg = db.obtener_todas_arca_configs()
    arca     = arca_cfg[0] if arca_cfg else None
    ta       = None

    if arca and arca.get("certificado_path") and arca.get("clave_path"):
        cert_path, clave_path = config_manager.resolve_cert_paths(
            arca["certificado_path"], arca["clave_path"]
        )
        try:
            ta = await arca_wsaa.autenticar(
                cert_path, clave_path, arca["ambiente"]
            )
            ultimo = await arca_wsfe.ultimo_numero_autorizado(
                punto_venta, tipo, arca["cuit"],
                ta["token"], ta["sign"], arca["ambiente"],
            )
            numero = ultimo + 1
        except Exception:
            ta     = None
            numero = db.get_next_factura_numero(punto_venta, tipo)
    else:
        numero = db.get_next_factura_numero(punto_venta, tipo)

    return numero, ta, arca


async def solicitar_cae(factura_id: int, factura: dict, ta, arca) -> dict:
    """
    Solicita el CAE real (prod) o genera uno simulado (dev).
    Devuelve la factura actualizada.
    """
    if ta == "_dev_mock_":
        mock = _mock_cae()
        db.update_factura_cae(factura_id, mock["cae"], mock["cae_vto"])
        return db.get_factura(factura_id)

    if not (ta and arca):
        return factura

    try:
        cae_data = await arca_wsfe.solicitar_cae(
            factura, arca["cuit"], ta["token"], ta["sign"], arca["ambiente"]
        )
        db.update_factura_cae(factura_id, cae_data["cae"], cae_data["cae_vto"])
        return db.get_factura(factura_id)
    except Exception:
        return factura
