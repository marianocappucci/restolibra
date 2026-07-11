import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from datetime import date
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, Response

import database as db
import config_manager
import mp_api
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

MEDIOS_PAGO = [
    {"id": "efectivo",         "label": "Efectivo",         "icon": "ti-cash",          "icon_material": "payments"},
    {"id": "transferencia",    "label": "Transferencia",    "icon": "ti-building-bank", "icon_material": "account_balance"},
    {"id": "mercadopago",      "label": "Mercado Pago",     "icon": "ti-phone",         "icon_material": "call"},
    {"id": "cuenta_dni",       "label": "Cuenta DNI",       "icon": "ti-id",            "icon_material": "perm_identity"},
    {"id": "billetera",        "label": "Otras billeteras", "icon": "ti-wallet",        "icon_material": "account_balance_wallet"},
    {"id": "cuenta_corriente", "label": "Cuenta corriente", "icon": "ti-notebook",      "icon_material": "menu_book"},
]

MEDIO_LABELS = {m["id"]: m["label"] for m in MEDIOS_PAGO}


@router.get("/ventas")
def ventas_list(request: Request, user: Auth,
                desde: str = "", hasta: str = "", q: str = "", tab: str = "todas"):
    if tab not in ("todas", "sin_facturar", "facturadas"):
        tab = "todas"
    ventas = db.get_all_ventas(desde=desde, hasta=hasta, q=q, tab=tab)
    return templates.TemplateResponse(request, "ventas/list.html", {
        "ventas": ventas, "desde": desde, "hasta": hasta, "q": q, "tab": tab,
        "active": "ventas", "medio_labels": MEDIO_LABELS,
    })


@router.get("/ventas/nueva")
def venta_nueva_get(request: Request, user: Auth):
    clientes = db.get_all_clients()
    listas   = db.get_all_listas_precio(solo_activas=True)
    return templates.TemplateResponse(request, "ventas/nueva.html", {
        "clientes": clientes, "medios_pago": MEDIOS_PAGO,
        "hoy": date.today().isoformat(), "active": "ventas",
        "listas_precio": listas,
        "error": None,
    })


@router.post("/ventas/nueva")
async def venta_nueva_post(request: Request, user: Auth):
    form = await request.form()

    # — items —
    nombres   = form.getlist("item_nombre")
    qtys      = form.getlist("item_qty")
    precios   = form.getlist("item_precio")
    prod_ids  = form.getlist("item_producto_id")

    items = []
    for nombre, qty_s, precio_s, pid_s in zip(nombres, qtys, precios, prod_ids):
        nombre = nombre.strip()
        if not nombre:
            continue
        try:
            qty    = float(qty_s.replace(",", "."))
            precio = float(precio_s.replace(",", "."))
        except ValueError:
            continue
        items.append({
            "nombre":      nombre,
            "qty":         qty,
            "precio":      precio,
            "subtotal":    round(qty * precio, 2),
            "producto_id": int(pid_s) if pid_s else None,
        })

    if not items:
        clientes = db.get_all_clients()
        return templates.TemplateResponse(request, "ventas/nueva.html", {
            "clientes": clientes, "medios_pago": MEDIOS_PAGO,
            "hoy": date.today().isoformat(), "active": "ventas",
            "error": "Debe agregar al menos un ítem.",
        }, status_code=422)

    subtotal  = round(sum(i["subtotal"] for i in items), 2)
    descuento = round(float(form.get("descuento") or 0), 2)
    total     = round(subtotal - descuento, 2)

    # — pagos —
    pagos = []
    for m in MEDIOS_PAGO:
        monto_s = str(form.get(f"pago_{m['id']}", "")).strip()
        ref     = str(form.get(f"ref_{m['id']}", "")).strip()
        if monto_s:
            try:
                monto = float(monto_s.replace(",", "."))
                if monto > 0:
                    pagos.append({"medio": m["id"], "monto": monto, "referencia": ref})
            except ValueError:
                pass

    total_pagado = round(sum(p["monto"] for p in pagos), 2)
    if not pagos:
        clientes = db.get_all_clients()
        return templates.TemplateResponse(request, "ventas/nueva.html", {
            "clientes": clientes, "medios_pago": MEDIOS_PAGO,
            "hoy": date.today().isoformat(), "active": "ventas",
            "error": "Debe registrar al menos un medio de pago.",
        }, status_code=422)

    # — cliente —
    cliente_id_s = str(form.get("cliente_id", "")).strip()
    cliente_id   = int(cliente_id_s) if cliente_id_s else None
    cliente_nombre = str(form.get("cliente_nombre", "")).strip()
    if cliente_id:
        c = db.get_client(cliente_id)
        if c:
            cliente_nombre = c["name"]

    fecha = str(form.get("fecha", date.today().isoformat()))
    obs   = str(form.get("observaciones", "")).strip()

    # — usuario actual —
    usuario = db.get_usuario_by_username(user)
    usuario_id = usuario["id"] if usuario else None

    numero = db.get_next_venta_numero()
    if total_pagado >= total:
        estado = "cobrada"
    elif total_pagado > 0:
        estado = "parcial"
    else:
        estado = "pendiente"

    # — guardar —
    venta_id = db.create_venta(
        numero=numero, fecha=fecha, items=items,
        subtotal=subtotal, descuento=descuento, total=total,
        cliente_id=cliente_id, cliente_nombre=cliente_nombre,
        usuario_id=usuario_id, observaciones=obs, estado=estado,
    )
    for p in pagos:
        db.add_venta_pago(venta_id, p["medio"], p["monto"], p.get("referencia", ""))

    # — movimiento de caja por cada medio —
    medio_map = {m["id"]: m["label"] for m in MEDIOS_PAGO}
    for p in pagos:
        label = medio_map.get(p["medio"], p["medio"].title())
        db.create_caja_movimiento(
            fecha=fecha,
            tipo="ingreso",
            concepto=f"Venta {numero} — {label}",
            monto=p["monto"],
            referencia=p.get("referencia", ""),
        )

    # — descuento de stock (si el módulo está activo) —
    mods = db.get_modulos()
    if mods.get("stock"):
        db.descontar_stock_venta(venta_id, items, fecha=fecha, usuario_id=usuario_id)

    # — vincular al turno activo del usuario —
    if usuario_id:
        turno = db.get_turno_activo(usuario_id)
        if turno:
            db.vincular_venta_turno(venta_id, turno["id"])

    return RedirectResponse(f"/ventas/{venta_id}", status_code=303)


@router.get("/ventas/{vid}")
def venta_detail(request: Request, vid: int, user: Auth):
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "ventas/detail.html", {
        "venta": venta, "active": "ventas",
        "medio_labels": MEDIO_LABELS,
    })


@router.post("/ventas/{vid}/anular")
def venta_anular(request: Request, vid: int, user: Auth):
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404)
    db.anular_venta(vid)
    return RedirectResponse(f"/ventas/{vid}", status_code=303)


@router.post("/ventas/{vid}/mp-qr")
async def venta_mp_qr(vid: int, user: Auth):
    """Crea una orden QR Dinámico en MP para esta venta y devuelve el QR como data-URL."""
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404)

    cfg = config_manager.load()
    access_token = cfg.get("mp_access_token", "")
    pos_id       = cfg.get("mp_pos_id", "")

    if not access_token or not pos_id:
        raise HTTPException(400, detail="Configurá el Access Token y el POS ID de MercadoPago en Configuración → Integraciones.")

    external_ref = f"venta-{vid}"
    titulo = f"Venta {venta['numero']}"

    try:
        resultado = await mp_api.crear_orden_qr(
            user_id=cfg.get("mp_user_id", ""),
            pos_id=pos_id,
            access_token=access_token,
            external_reference=external_ref,
            titulo=titulo,
            items=venta["items"],
            total=venta["total"],
        )
    except RuntimeError as e:
        raise HTTPException(502, detail=str(e))

    order_id = resultado.get("in_store_order_id", external_ref)
    db.set_venta_mp_order(vid, order_id)

    # MP devuelve la URL del QR — la enviamos al frontend para mostrarla
    qr_data = resultado.get("qr_data", "")
    return JSONResponse({"ok": True, "qr_data": qr_data, "order_id": order_id})


@router.get("/ventas/{vid}/mp-status")
async def venta_mp_status(vid: int, user: Auth):
    """Consulta si el pago QR de esta venta ya fue aprobado."""
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404)

    # Si ya tiene payment_id registrado (confirmado por webhook), listo
    if venta.get("mp_payment_id"):
        return JSONResponse({"status": "approved", "payment_id": venta["mp_payment_id"]})

    cfg = config_manager.load()
    access_token = cfg.get("mp_access_token", "")
    if not access_token:
        raise HTTPException(400, detail="Access Token de MP no configurado.")

    try:
        pago = await mp_api.buscar_pago_por_referencia(f"venta-{vid}", access_token)
    except Exception as e:
        raise HTTPException(502, detail=str(e))

    if not pago:
        return JSONResponse({"status": "pending"})

    status = pago.get("status", "pending")
    if status == "approved":
        payment_id = str(pago["id"])
        db.set_venta_mp_payment(vid, payment_id)
        # Actualizar referencia en el registro de pago de la venta
        db.add_venta_pago_referencia_mp(vid, payment_id)
        return JSONResponse({"status": "approved", "payment_id": payment_id})

    return JSONResponse({"status": status})


@router.get("/ventas/{vid}/ticket")
def venta_ticket(vid: int, user: Auth):
    import ticket_generator
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404)
    pdf_bytes = ticket_generator.generar_ticket_venta(venta)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="ticket_venta_{vid}.pdf"'},
    )


@router.get("/ventas/{vid}/recibo")
def venta_recibo(vid: int, user: Auth):
    import pdf_generator as pg
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404)
    # Adaptar venta al formato que espera generate_pdf_recibo
    factura_like = {
        "tipo":            None,
        "punto_venta":     0,
        "numero":          venta["id"],
        "fecha":           venta.get("fecha", ""),
        "cliente_razon":   venta.get("cliente_nombre") or "Consumidor Final",
        "cliente_cuit":    venta.get("cliente_cuit", ""),
        "cliente_domicilio": "",
        "total":           venta.get("total", 0),
        "_es_venta":       True,
        "_venta_numero":   venta.get("numero", venta["id"]),
    }
    cobros = [
        {
            "fecha":      venta.get("fecha", ""),
            "medio_pago": p.get("medio", ""),
            "referencia": p.get("referencia", ""),
            "monto":      float(p.get("monto", 0)),
        }
        for p in venta.get("pagos", [])
    ]
    pdf_bytes = pg.generate_pdf_recibo(factura_like, cobros)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="recibo_venta_{vid}.pdf"'},
    )
