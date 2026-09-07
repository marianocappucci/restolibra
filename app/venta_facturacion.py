"""Shim: la factura desde la venta vive en `libracore.venta_facturacion` desde
P9-M3 (2026-09-06), sobre el `PuertoDeVentas` de este producto. Las firmas se
conservan: las usan la API de integraciones, el webhook y los tests.

`get_next_numero_with_arca` se re-exporta **y se usa a través de este módulo**:
la suite fija el ambiente de la factura parcheándolo acá (con
`ENV=development` todo sale `produccion` y la marca es invisible), y el motor
lo recibe por el puerto para que ese parche siga interceptando.
"""
import dataclasses

from libracore import venta_facturacion as _vf
from libracore.arca_facturacion import get_next_numero_with_arca  # noqa: F401
from libracore.venta_facturacion import (  # noqa: F401
    CONSUMIDOR_FINAL,
    IVA_RATE_DEFAULT,
    VentaNoFacturable,
)

from app import db_ventas


async def _numerar(punto_venta: int, tipo: int):
    # Resuelve el nombre en cada llamada: es lo que hace que el `monkeypatch`
    # sobre este módulo llegue al motor.
    return await get_next_numero_with_arca(punto_venta, tipo)


#: El puerto completo de este producto: las ventas de `db_ventas` más el
#: numerador. Es el que montan el router del cobro y el webhook.
PUERTO = dataclasses.replace(db_ventas.PUERTO, numerar_comprobante=_numerar)


async def facturar_venta(venta_id: int, *, usuario_id: int | None = None) -> dict:
    return await _vf.facturar_venta(PUERTO, venta_id, usuario_id=usuario_id)


async def facturar_si_esta_prendida(venta_id: int, cfg: dict | None = None) -> int | None:
    return await _vf.facturar_si_esta_prendida(PUERTO, venta_id, cfg)
