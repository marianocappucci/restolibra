"""Shim: la lógica de cuenta corriente ahora vive en libracore.db.cuenta_corriente."""
from libracore.db.cuenta_corriente import (  # noqa: F401
    get_cc_saldo,
    get_cc_movimientos,
    get_clientes_con_saldo_cc,
    create_cc_pago,
    delete_cc_pago,
)
