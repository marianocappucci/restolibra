"""Shim de compatibilidad — la implementación real vive en libracore (paquete
interno, ver pyproject.toml y wiki/entities/libracore.md). No editar el
comportamiento acá; los cambios van en el repo libracore.

> 🔴 **La copia que había en este archivo NO era equivalente a la de Contalibra.**
> Resolvía el pagador con `get_client_by_email` en vez de
> `resolver_cliente_pago`, o sea sin mirar los alias de facturación, y su
> `generar_factura_mp` ni siquiera aceptaba `payer_cuit` — así que un alias por
> CUIT no podía resolver ni aunque alguien lo cargara.
>
> Es el mecanismo que en Contalibra emitió dos comprobantes al CUIT equivocado.
> Al pasar al motor, este producto gana la resolución por alias en los cuatro
> caminos que facturan un pago de MercadoPago.
"""
from libracore.mp_facturacion import (  # noqa: F401
    CONDICION_POR_PAYMENT_TYPE,
    IVA_CODES,
    TIPO_LABEL,
    TIPO_POR_CONDICION,
    generar_factura_mp,
    resolver_cliente,
)
