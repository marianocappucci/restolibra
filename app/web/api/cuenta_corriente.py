"""API JSON de Cuenta Corriente para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `db_cuenta_corriente.py` (via `database.py`) tal
cual -- mismo patron que Contalibra (web/api/cuenta_corriente.py), portado
1:1 -- ver web/api/dashboard.py para el patron general de auth/gating de
esta etapa."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app.web.api_auth import get_current_user_json, require_admin_json

router = APIRouter(prefix="/api/cuenta-corriente", tags=["cuenta_corriente"])


class PagoPayload(BaseModel):
    monto: float
    fecha: str
    concepto: str = "Pago a cuenta"
    referencia: str = ""
    medio_pago: str = "efectivo"
    caja_id: int | None = None


@router.get("")
def listar():
    clientes = db.get_clientes_con_saldo_cc()
    total_deuda = sum(c["saldo"] for c in clientes if c["saldo"] > 0)
    return {"clientes": clientes, "total_deuda": total_deuda}


@router.get("/cajas")
def listar_cajas():
    """Solo lectura, para el selector de caja del pago -- CRUD de cajas
    (modulo Caja/Cajas) es de otra etapa."""
    return db.get_all_cajas()


@router.get("/{cliente_id}")
def detalle(cliente_id: int):
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    return {
        "cliente": cliente,
        "movimientos": db.get_cc_movimientos(cliente_id),
        "saldo": db.get_cc_saldo(cliente_id),
    }


@router.post("/{cliente_id}/pagar")
def pagar(cliente_id: int, payload: PagoPayload, user: dict = Depends(get_current_user_json)):
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    db.create_cc_pago(
        cliente_id=cliente_id, monto=payload.monto, fecha=payload.fecha,
        concepto=payload.concepto, referencia=payload.referencia,
        medio_pago=payload.medio_pago, caja_id=payload.caja_id, usuario_id=user["id"],
    )

    if payload.caja_id:
        db.create_caja_movimiento(
            fecha=payload.fecha, tipo="ingreso", concepto=f"Pago CC - {cliente['name']}",
            monto=payload.monto, referencia=payload.referencia,
            caja_id=payload.caja_id, medio_pago=payload.medio_pago, usuario_id=user["id"],
        )

    return {
        "movimientos": db.get_cc_movimientos(cliente_id),
        "saldo": db.get_cc_saldo(cliente_id),
    }


@router.delete("/pagos/{pago_id}", dependencies=[Depends(require_admin_json)])
def eliminar_pago(pago_id: int):
    db.delete_cc_pago(pago_id)
    return {"ok": True}
