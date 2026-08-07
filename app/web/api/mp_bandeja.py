"""API JSON de la Bandeja de MercadoPago para la SPA (ver
wiki/entities/restolibra.md, migracion a React). Portado desde Contalibra
(wiki/entities/contalibra.md) -- reusa `db_mp.py`, `mp_api.py` y
`mp_facturacion.py` tal cual, ver web/api/clientes.py para el patron
general de esta etapa.

Divergencia real encontrada al portar (no una simplificacion nuestra):
`mp_facturacion.generar_factura_mp()` en este repo NO acepta el parametro
`payer_cuit` que tiene la version de Contalibra, y resuelve el cliente via
`db.get_client_by_email()` en lugar de `db.resolver_cliente_pago()` (que
usa alias de facturacion por CUIT/email -- funcionalidad que Restolibra no
tiene cableada). Las llamadas de aca omiten `payer_cuit=` en consecuencia
-- ver web/routers/mp_bandeja.py (router Jinja2 viejo, mismo patron) para
confirmar que es el comportamiento real vigente, no un bug de este port.

Nota: el endpoint viejo de reenvio de email
(`POST /integraciones/mp/factura/{id}/reenviar` en
web/routers/mp_bandeja.py) referencia `os`/`email_sender`/`_TIPO_LABEL`
sin importarlos -- un bug latente preexistente (nunca se habia invocado
en produccion), igual que en Contalibra. El endpoint nuevo de aca los
importa correctamente en vez de replicar el bug.
"""
import datetime
import logging
import os

from app import database as db
from app import config_manager
from app import email_sender
from app import mp_api
from app import mp_facturacion
from app import pdf_generator as pdf_gen
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mp-bandeja", tags=["mp_bandeja"])


def _enrich_with_client(items: list) -> list:
    emails = {p["payer_email"] for p in items if p.get("payer_email")}
    cuits = {(p.get("payer_id_number") or "").replace("-", "").strip() for p in items if p.get("payer_id_number")}
    cuits.discard("")

    by_email: dict = {}
    by_cuit: dict = {}

    with db.get_connection() as conn:
        if emails:
            ph = ",".join("?" * len(emails))
            rows = conn.execute(f"SELECT * FROM clients WHERE email IN ({ph})", tuple(emails)).fetchall()
            by_email = {dict(r)["email"]: dict(r) for r in rows}
        if cuits:
            ph = ",".join("?" * len(cuits))
            rows = conn.execute(
                f"SELECT * FROM clients WHERE REPLACE(cuit_dni, '-', '') IN ({ph})", tuple(cuits),
            ).fetchall()
            for r in rows:
                d = dict(r)
                norm = (d.get("cuit_dni") or "").replace("-", "").strip()
                if norm:
                    by_cuit[norm] = d

    for p in items:
        email = p.get("payer_email") or ""
        cuit = (p.get("payer_id_number") or "").replace("-", "").strip()
        p["cliente"] = by_email.get(email) or (by_cuit.get(cuit) if cuit else None)
    return items


class SincronizarPayload(BaseModel):
    dias: int = 7


class CrearClientePayload(BaseModel):
    nombre: str
    email: str = ""
    cuit_dni: str = ""
    iva_condition: str = "Consumidor Final"
    address: str = ""


class GuardarDatosPayload(BaseModel):
    payer_email: str = ""
    payer_name: str = ""
    payer_id_type: str = ""
    payer_id_number: str = ""


class FacturarPayload(BaseModel):
    concepto: str = ""


@router.get("")
def bandeja():
    cfg = config_manager.load()
    return {
        "pendientes": _enrich_with_client(db.get_mp_pagos_by_estado("pendiente")),
        "historial": _enrich_with_client(db.get_mp_pagos_historial(limit=30)),
        "transferencias": _enrich_with_client(db.get_mp_movimientos_by_estado("pendiente")),
        "transferencias_hist": _enrich_with_client(db.get_mp_movimientos_historial(limit=30)),
        "mp_concepto_default": cfg.get("mp_concepto_descripcion", "") or "",
    }


@router.post("/sincronizar")
async def sincronizar(payload: SincronizarPayload):
    cfg = config_manager.load()
    access_token = cfg.get("mp_access_token", "")
    if not access_token:
        raise HTTPException(400, "Configurá el Access Token de MercadoPago en Configuración.")

    hasta = datetime.date.today().isoformat()
    desde = (datetime.date.today() - datetime.timedelta(days=max(1, min(payload.dias, 90)))).isoformat()

    mi_user_id = None
    mi_email = ""
    try:
        info = await mp_api.obtener_usuario_info(access_token)
        mi_user_id = str(info.get("id", ""))
        mi_email = (info.get("email") or "").strip().lower()
    except Exception:
        pass

    try:
        movimientos = await mp_api.obtener_movimientos(access_token, desde, hasta)
    except Exception as e:
        logger.error("Error consultando movimientos MP: %s", e)
        raise HTTPException(502, "No se pudo sincronizar con MercadoPago.")

    nuevos = 0
    for pago in movimientos:
        payment_id = str(pago.get("id", "")).strip()
        if not payment_id:
            continue
        if mi_user_id and str(pago.get("collector_id", "")) != str(mi_user_id):
            continue
        ext_ref = (pago.get("external_reference") or "").strip()
        if ext_ref.startswith("venta-"):
            continue
        if db.get_mp_pago(payment_id) or db.get_mp_movimiento_by_mp_id(payment_id):
            continue

        monto = float(pago.get("transaction_amount") or 0)
        if monto <= 0:
            continue

        payer = pago.get("payer") or {}
        ident = payer.get("identification") or {}
        first = (payer.get("first_name") or "").strip()
        last = (payer.get("last_name") or "").strip()
        raw_email = (payer.get("email") or "").strip()
        payer_email_val = "" if raw_email.lower() == mi_email else raw_email
        origen_nombre = f"{first} {last}".strip() or (payer_email_val or "")
        fecha_mov = (pago.get("date_approved") or pago.get("date_created") or datetime.date.today().isoformat())[:10]

        db.create_mp_movimiento(
            mp_movement_id=payment_id, tipo=(pago.get("payment_type_id") or "").strip(), monto=monto,
            fecha=fecha_mov, descripcion=(pago.get("description") or "").strip(),
            origen_nombre=origen_nombre, origen_banco=(pago.get("payment_method_id") or "").strip(),
            origen_cbu="", payer_email=payer_email_val, payer_name=origen_nombre,
            payer_id_type=(ident.get("type") or "").strip(), payer_id_number=(ident.get("number") or "").strip(),
            estado_factura="pendiente",
        )
        nuevos += 1

    return {"nuevos": nuevos}


@router.post("/pagos/{mp_pago_id}/ignorar")
def ignorar_pago(mp_pago_id: int):
    db.update_mp_pago_estado(mp_pago_id, "ignorado")
    return {"ok": True}


@router.post("/pagos/{mp_pago_id}/crear-cliente")
def crear_cliente_pago(mp_pago_id: int, payload: CrearClientePayload):
    pago = db.get_mp_pago_by_id(mp_pago_id)
    if not pago:
        raise HTTPException(404, "Pago no encontrado")
    if not payload.nombre.strip():
        raise HTTPException(422, "El nombre es obligatorio.")
    if not (db.get_client_by_email(payload.email) if payload.email else None):
        db.create_client(name=payload.nombre, email=payload.email, cuit_dni=payload.cuit_dni,
                          iva_condition=payload.iva_condition, address=payload.address)
    return {"ok": True}


@router.post("/pagos/{mp_pago_id}/facturar")
async def facturar_pago(mp_pago_id: int, payload: FacturarPayload):
    pago = db.get_mp_pago_by_id(mp_pago_id)
    if not pago or pago.get("estado_factura") != "pendiente":
        raise HTTPException(404, "Pago no encontrado o ya procesado")

    cfg = config_manager.load()
    if payload.concepto.strip():
        cfg = {**cfg, "mp_concepto_descripcion": payload.concepto.strip()}

    factura_id, numero, tipo_label, email_sent = await mp_facturacion.generar_factura_mp(
        monto=float(pago["monto"]), payer_email=pago["payer_email"] or "", payer_name=pago["payer_name"] or "",
        referencia=f"MP#{pago['mp_payment_id']}", cfg=cfg,
        payment_type=pago.get("payment_type") or "",
    )
    db.update_mp_pago_estado(mp_pago_id, "facturado", factura_id=factura_id)
    return {"factura_id": factura_id, "numero": numero, "tipo_label": tipo_label, "email_sent": email_sent}


@router.post("/movimientos/{mov_id}/guardar-datos")
def guardar_datos_movimiento(mov_id: int, payload: GuardarDatosPayload):
    db.update_mp_movimiento_datos(
        mov_id, payer_email=payload.payer_email.strip() or None, payer_name=payload.payer_name.strip() or None,
        payer_id_type=payload.payer_id_type.strip() or None, payer_id_number=payload.payer_id_number.strip() or None,
    )
    return {"ok": True}


@router.post("/movimientos/{mov_id}/crear-cliente")
def crear_cliente_movimiento(mov_id: int, payload: CrearClientePayload):
    mov = db.get_mp_movimiento_by_id(mov_id)
    if not mov:
        raise HTTPException(404, "Movimiento no encontrado")
    if not payload.nombre.strip():
        raise HTTPException(422, "El nombre es obligatorio.")
    if not (db.get_client_by_email(payload.email) if payload.email else None):
        db.create_client(name=payload.nombre, email=payload.email, cuit_dni=payload.cuit_dni,
                          iva_condition=payload.iva_condition, address=payload.address)
    db.update_mp_movimiento_datos(mov_id, payer_email=payload.email or None, payer_name=payload.nombre or None,
                                   payer_id_number=payload.cuit_dni or None)
    return {"ok": True}


@router.post("/movimientos/{mov_id}/ignorar")
def ignorar_movimiento(mov_id: int):
    db.update_mp_movimiento_estado(mov_id, "ignorado")
    return {"ok": True}


@router.post("/movimientos/{mov_id}/facturar")
async def facturar_movimiento(mov_id: int, payload: FacturarPayload):
    mov = db.get_mp_movimiento_by_id(mov_id)
    if not mov or mov.get("estado_factura") != "pendiente":
        raise HTTPException(404, "Movimiento no encontrado o ya procesado")

    cfg = config_manager.load()
    if payload.concepto.strip():
        cfg = {**cfg, "mp_concepto_descripcion": payload.concepto.strip()}

    payer_email = mov["payer_email"] or ""
    factura_id, numero, tipo_label, email_sent = await mp_facturacion.generar_factura_mp(
        monto=float(mov["monto"]), payer_email=payer_email, payer_name=mov["payer_name"] or mov["origen_nombre"] or "",
        referencia=f"Transferencia MP#{mov['mp_movement_id']}", cfg=cfg,
        payment_type=mov.get("tipo") or "",
    )
    db.update_mp_movimiento_estado(mov_id, "facturado", factura_id=factura_id)
    return {"factura_id": factura_id, "numero": numero, "tipo_label": tipo_label, "email_sent": email_sent}


@router.post("/facturas/{factura_id}/reenviar")
def reenviar_email(factura_id: int):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404, "Factura no encontrada")

    cfg = config_manager.load()
    smtp_host = cfg.get("email_smtp_host", "")
    smtp_user = cfg.get("email_smtp_user", "")
    smtp_pass = cfg.get("email_smtp_password", "")
    from_email = cfg.get("email_from", "")
    if not (smtp_host and smtp_user and smtp_pass and from_email):
        raise HTTPException(400, "Configurá el servidor SMTP en Configuración → Email.")

    dest_email = factura.get("cliente_email", "") or ""
    if not dest_email:
        cliente = db.get_client_by_cuit(factura.get("cliente_cuit", ""))
        dest_email = (cliente or {}).get("email", "")
    if not dest_email:
        raise HTTPException(422, "El cliente no tiene email registrado.")

    pdf_path = factura.get("pdf_path", "")
    if not pdf_path or not os.path.exists(pdf_path):
        pdf_path = pdf_gen.generate_pdf_factura(factura)

    from app.pdf_generator import _TIPO_LABELS
    tipo_lb = _TIPO_LABELS.get(factura.get("tipo"), "Factura")
    pv_str = str(factura.get("punto_venta", 1)).zfill(4)
    num_str = str(factura.get("numero", 0)).zfill(8)

    try:
        email_sender.enviar_comprobante(
            to_email=dest_email, to_name=factura.get("cliente_razon", ""), pdf_path=pdf_path,
            empresa_nombre=cfg.get("empresa_nombre", ""), factura_label=f"{tipo_lb} {pv_str}-{num_str}",
            total=float(factura.get("total", 0)), smtp_host=smtp_host,
            smtp_port=int(cfg.get("email_smtp_port", "587") or "587"), smtp_user=smtp_user,
            smtp_password=smtp_pass, from_email=from_email, from_name=cfg.get("email_from_name", ""),
        )
    except Exception as e:
        logger.error("Error reenvío email factura %s: %s", factura_id, e)
        raise HTTPException(502, f"Error al enviar: {e}")
    return {"ok": True}


# ── Siembra de la bandeja, SÓLO en demos ──────────────────────────────────
#
# 🔴 La bandeja se llena sincronizando contra MercadoPago de verdad
# (`/sincronizar` exige el Access Token de la cuenta). Una demo pública no tiene
# cuenta de MP ni puede tenerla, así que esta pantalla —una de las que mejor
# muestran el producto: el cobro entra y se factura solo— se abría vacía.
#
# **La ruta no existe fuera de una demo**, y eso no se resuelve con un `if`
# adentro del endpoint: el router se arma al importar, mirando `DEMO_MODE`. En
# la instancia de un cliente la ruta da 404 y ni siquiera figura en el openapi.
# Misma garantía que `POST /auth/demo` de libraauth.

def _es_demo() -> bool:
    return os.environ.get("DEMO_MODE", "").strip() in ("1", "true", "True")


class PagoDeDemoPayload(BaseModel):
    """Un cobro como los que devolvería MercadoPago, escrito a mano."""

    mp_payment_id: str
    monto: float
    payer_name: str = ""
    payer_email: str = ""
    payer_id_number: str = ""
    payment_type: str = "account_money"
    payment_method: str = "account_money"
    descripcion: str = ""
    #: `pago` va a la lista de cobros; `transferencia` a la de movimientos
    #: bancarios entrantes. La pantalla tiene las dos solapas y con una sola
    #: llena queda a medias.
    clase: str = "pago"


if _es_demo():

    @router.post("/demo/sembrar")
    def sembrar_bandeja_de_demo(items: list[PagoDeDemoPayload]):
        """Carga cobros de ejemplo en la bandeja. Idempotente por
        `mp_payment_id`: correrla de nuevo no duplica nada, que es lo que
        necesita el reset diario."""
        creados = 0
        for it in items:
            pid = it.mp_payment_id.strip()
            if not pid:
                continue
            if db.get_mp_pago(pid) or db.get_mp_movimiento_by_mp_id(pid):
                continue

            if it.clase == "transferencia":
                db.create_mp_movimiento(
                    mp_movement_id=pid, tipo=it.payment_type, monto=it.monto,
                    fecha=datetime.date.today().isoformat(),
                    descripcion=it.descripcion, origen_nombre=it.payer_name,
                    origen_banco=it.payment_method, origen_cbu="",
                    payer_email=it.payer_email, payer_name=it.payer_name,
                    payer_id_type="CUIT" if it.payer_id_number else "",
                    payer_id_number=it.payer_id_number,
                    estado_factura="pendiente",
                )
            else:
                db.create_mp_pago(
                    mp_payment_id=pid, status="approved", monto=it.monto,
                    payer_email=it.payer_email, payer_name=it.payer_name,
                    estado_factura="pendiente", payment_type=it.payment_type,
                    payment_method=it.payment_method, descripcion_mp=it.descripcion,
                    payer_id_type="CUIT" if it.payer_id_number else "",
                    payer_id_number=it.payer_id_number,
                )
            creados += 1
        return {"creados": creados}
