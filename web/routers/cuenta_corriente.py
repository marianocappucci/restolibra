import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from typing import Annotated, Optional

import database as db
from web.auth import require_auth
from web.templates_config import templates

from fastapi import Depends

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

_MEDIOS_LABEL = {
    "efectivo":      "Efectivo",
    "transferencia": "Transferencia",
    "mercadopago":   "Mercado Pago",
    "cuenta_dni":    "Cuenta DNI",
    "billetera":     "Billetera",
    "cheque":        "Cheque",
}


def _uid(request: Request):
    u = request.state.current_user
    return u["id"] if u else None


@router.get("/cuenta-corriente")
def cc_list(request: Request, user: Auth):
    clientes = db.get_clientes_con_saldo_cc()
    total_deuda = sum(c["saldo"] for c in clientes if c["saldo"] > 0)
    return templates.TemplateResponse(request, "cuenta_corriente/list.html", {
        "active":      "cuenta_corriente",
        "clientes":    clientes,
        "total_deuda": total_deuda,
    })


@router.get("/cuenta-corriente/{cliente_id}")
def cc_detail(cliente_id: int, request: Request, user: Auth):
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404)
    movimientos = db.get_cc_movimientos(cliente_id)
    saldo       = db.get_cc_saldo(cliente_id)
    cajas       = db.get_all_cajas()
    return templates.TemplateResponse(request, "cuenta_corriente/detail.html", {
        "active":       "cuenta_corriente",
        "cliente":      cliente,
        "movimientos":  movimientos,
        "saldo":        saldo,
        "cajas":        cajas,
        "medios_label": _MEDIOS_LABEL,
    })


@router.post("/cuenta-corriente/{cliente_id}/pagar")
async def cc_pagar(
    cliente_id: int,
    request: Request,
    user: Auth,
    monto:      float           = Form(...),
    fecha:      str             = Form(...),
    concepto:   str             = Form("Pago a cuenta"),
    referencia: str             = Form(""),
    medio_pago: str             = Form("efectivo"),
    caja_id:    Optional[int]   = Form(None),
):
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404)

    uid = _uid(request)
    db.create_cc_pago(
        cliente_id=cliente_id, monto=monto, fecha=fecha,
        concepto=concepto, referencia=referencia,
        medio_pago=medio_pago, caja_id=caja_id, usuario_id=uid,
    )

    if caja_id:
        db.create_caja_movimiento(
            fecha=fecha, tipo="ingreso",
            concepto=f"Pago CC - {cliente['name']}",
            monto=monto, referencia=referencia,
            caja_id=caja_id, medio_pago=medio_pago, usuario_id=uid,
        )

    return RedirectResponse(f"/cuenta-corriente/{cliente_id}", status_code=303)


@router.post("/cuenta-corriente/pagos/{pago_id}/eliminar")
async def cc_eliminar_pago(
    pago_id:    int,
    request:    Request,
    user:       Auth,
    cliente_id: int = Form(...),
):
    db.delete_cc_pago(pago_id)
    return RedirectResponse(f"/cuenta-corriente/{cliente_id}", status_code=303)
