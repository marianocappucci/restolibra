import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Annotated
from datetime import date
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse

import database as db
from web.auth import require_auth
from web.templates_config import templates
from web.routers.ventas import MEDIOS_PAGO

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]


def _usuario_id(username: str) -> int | None:
    u = db.get_usuario_by_username(username)
    return u["id"] if u else None


# ── Mapa de mesas ────────────────────────────────────────────────────────────

@router.get("/salon")
def salon_mapa(request: Request, user: Auth, salon_id: int = 0):
    salones = db.get_salones(solo_activos=True)
    sel = salon_id or (salones[0]["id"] if salones else 0)
    mesas = db.get_mesas(salon_id=sel) if sel else []
    return templates.TemplateResponse(request, "salon/mapa.html", {
        "active": "salon", "salones": salones, "salon_sel": sel, "mesas": mesas,
    })


@router.get("/salon/mesa/{mesa_id}")
def salon_mesa(request: Request, mesa_id: int, user: Auth):
    mesa = db.get_mesa(mesa_id)
    if not mesa:
        raise HTTPException(404)
    pedido = db.get_pedido_abierto_de_mesa(mesa_id)
    if pedido:
        return RedirectResponse(f"/salon/pedido/{pedido['id']}", status_code=303)
    return templates.TemplateResponse(request, "salon/abrir.html", {
        "active": "salon", "mesa": mesa,
    })


@router.post("/salon/mesa/{mesa_id}/abrir")
async def salon_mesa_abrir(request: Request, mesa_id: int, user: Auth):
    mesa = db.get_mesa(mesa_id)
    if not mesa:
        raise HTTPException(404)
    existente = db.get_pedido_abierto_de_mesa(mesa_id)
    if existente:
        return RedirectResponse(f"/salon/pedido/{existente['id']}", status_code=303)
    form = await request.form()
    try:
        comensales = max(1, int(form.get("comensales") or 1))
    except ValueError:
        comensales = 1
    pid = db.crear_pedido(
        canal="salon", mesa_id=mesa_id, comensales=comensales,
        usuario_id=_usuario_id(user),
    )
    return RedirectResponse(f"/salon/pedido/{pid}", status_code=303)


# ── Pedido abierto ───────────────────────────────────────────────────────────

@router.get("/salon/pedido/{pid}")
def salon_pedido(request: Request, pid: int, user: Auth, q: str = ""):
    pedido = db.get_pedido(pid)
    if not pedido:
        raise HTTPException(404)
    productos = db.get_all_productos(solo_activos=True, q=q)
    hay_nuevos = any(it["estado"] == "nuevo" for it in pedido["items"])
    return templates.TemplateResponse(request, "salon/pedido.html", {
        "active": "salon", "pedido": pedido, "productos": productos, "q": q,
        "hay_nuevos": hay_nuevos,
    })


@router.post("/salon/pedido/{pid}/item")
async def salon_pedido_add_item(request: Request, pid: int, user: Auth):
    pedido = db.get_pedido(pid)
    if not pedido or pedido["estado"] != "abierto":
        raise HTTPException(400, "Pedido no editable")
    form = await request.form()
    producto_id = form.get("producto_id")
    nota = str(form.get("nota", "")).strip()
    try:
        qty = float(str(form.get("qty") or 1).replace(",", "."))
    except ValueError:
        qty = 1.0
    if qty <= 0:
        qty = 1.0

    if producto_id:
        prod = db.get_producto(int(producto_id))
        if not prod:
            raise HTTPException(404, "Producto inexistente")
        db.add_pedido_item(
            pid, nombre=prod["nombre"], qty=qty, precio=float(prod["precio_venta"]),
            producto_id=prod["id"], estacion=prod.get("estacion") or "", nota=nota,
        )
    else:
        nombre = str(form.get("nombre", "")).strip()
        if nombre:
            try:
                precio = float(str(form.get("precio") or 0).replace(",", "."))
            except ValueError:
                precio = 0.0
            db.add_pedido_item(
                pid, nombre=nombre, qty=qty, precio=precio,
                estacion=str(form.get("estacion", "")).strip(), nota=nota,
            )
    return RedirectResponse(f"/salon/pedido/{pid}", status_code=303)


@router.post("/salon/pedido/{pid}/item/{item_id}/eliminar")
def salon_pedido_del_item(pid: int, item_id: int, user: Auth):
    db.delete_pedido_item(item_id)
    return RedirectResponse(f"/salon/pedido/{pid}", status_code=303)


@router.post("/salon/pedido/{pid}/enviar")
def salon_pedido_enviar(pid: int, user: Auth):
    db.enviar_a_estaciones(pid)
    return RedirectResponse(f"/salon/pedido/{pid}", status_code=303)


@router.post("/salon/pedido/{pid}/anular")
def salon_pedido_anular(pid: int, user: Auth):
    pedido = db.get_pedido(pid)
    destino = "/salon"
    if pedido and pedido["estado"] == "abierto":
        with db.get_connection() as conn:
            conn.execute("UPDATE pedidos SET estado='anulado' WHERE id=?", (pid,))
            if pedido.get("mesa_id"):
                conn.execute("UPDATE mesas SET estado='libre' WHERE id=?", (pedido["mesa_id"],))
        if not pedido.get("mesa_id"):
            destino = "/pedidos"
    return RedirectResponse(destino, status_code=303)


# ── Cobro ────────────────────────────────────────────────────────────────────

@router.get("/salon/pedido/{pid}/cobrar")
def salon_cobrar_get(request: Request, pid: int, user: Auth):
    pedido = db.get_pedido(pid)
    if not pedido:
        raise HTTPException(404)
    if pedido["estado"] != "abierto":
        return RedirectResponse(f"/salon/pedido/{pid}", status_code=303)
    return templates.TemplateResponse(request, "salon/cobrar.html", {
        "active": "salon", "pedido": pedido, "medios_pago": MEDIOS_PAGO, "error": None,
    })


@router.post("/salon/pedido/{pid}/cobrar")
async def salon_cobrar_post(request: Request, pid: int, user: Auth):
    pedido = db.get_pedido(pid)
    if not pedido or pedido["estado"] != "abierto":
        raise HTTPException(400, "Pedido no cobrable")
    form = await request.form()

    pagos = []
    for m in MEDIOS_PAGO:
        monto_s = str(form.get(f"pago_{m['id']}", "")).strip()
        if monto_s:
            try:
                monto = float(monto_s.replace(",", "."))
            except ValueError:
                continue
            if monto > 0:
                pagos.append({
                    "medio": m["id"], "monto": monto,
                    "referencia": str(form.get(f"ref_{m['id']}", "")).strip(),
                })
    if not pagos:
        return templates.TemplateResponse(request, "salon/cobrar.html", {
            "active": "salon", "pedido": pedido, "medios_pago": MEDIOS_PAGO,
            "error": "Registrá al menos un medio de pago.",
        }, status_code=422)

    try:
        descuento = float(str(form.get("descuento") or 0).replace(",", "."))
    except ValueError:
        descuento = 0.0

    venta_id = db.cobrar_pedido(
        pid, pagos=pagos, descuento=descuento,
        cliente_nombre=str(form.get("cliente_nombre", "")).strip(),
        usuario_id=_usuario_id(user),
    )
    return RedirectResponse(f"/ventas/{venta_id}", status_code=303)


# ── Configuración de salón (salones / mesas) ─────────────────────────────────

@router.get("/salon/config")
def salon_config(request: Request, user: Auth, msg: str = ""):
    salones = db.get_salones(solo_activos=False)
    mesas_por_salon = {s["id"]: db.get_mesas(salon_id=s["id"], solo_activas=False) for s in salones}
    return templates.TemplateResponse(request, "salon/config.html", {
        "active": "salon_config", "salones": salones, "mesas_por_salon": mesas_por_salon,
        "msg": msg,
    })


@router.post("/salon/config/salon")
async def salon_config_salon(request: Request, user: Auth):
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if nombre:
        try:
            orden = int(form.get("orden") or 0)
        except ValueError:
            orden = 0
        db.create_salon(nombre, orden)
    return RedirectResponse("/salon/config", status_code=303)


@router.post("/salon/config/mesa")
async def salon_config_mesa(request: Request, user: Auth):
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    salon_id = form.get("salon_id")
    if nombre and salon_id:
        try:
            capacidad = int(form.get("capacidad") or 4)
        except ValueError:
            capacidad = 4
        db.create_mesa(int(salon_id), nombre, capacidad)
    return RedirectResponse("/salon/config", status_code=303)


@router.post("/salon/config/salon/{sid}/editar")
async def salon_config_salon_editar(request: Request, sid: int, user: Auth):
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if nombre:
        try:
            orden = int(form.get("orden") or 0)
        except ValueError:
            orden = 0
        db.update_salon(sid, nombre, orden, 1 if form.get("activo") else 0)
    return RedirectResponse("/salon/config", status_code=303)


@router.post("/salon/config/salon/{sid}/eliminar")
def salon_config_salon_eliminar(sid: int, user: Auth):
    ok = db.delete_salon(sid)
    msg = "" if ok else "No se puede eliminar el salón: tiene una mesa con un pedido abierto."
    return RedirectResponse(f"/salon/config?msg={msg}", status_code=303)


@router.post("/salon/config/mesa/{mid}/editar")
async def salon_config_mesa_editar(request: Request, mid: int, user: Auth):
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if nombre:
        try:
            capacidad = int(form.get("capacidad") or 4)
        except ValueError:
            capacidad = 4
        db.update_mesa(mid, nombre, capacidad, 0, 1 if form.get("activo") else 0)
    return RedirectResponse("/salon/config", status_code=303)


@router.post("/salon/config/mesa/{mid}/eliminar")
def salon_config_mesa_eliminar(mid: int, user: Auth):
    ok = db.delete_mesa(mid)
    msg = "" if ok else "No se puede eliminar la mesa: tiene un pedido abierto."
    return RedirectResponse(f"/salon/config?msg={msg}", status_code=303)


# ── Reportes gastronómicos ───────────────────────────────────────────────────

@router.get("/salon/reportes")
def salon_reportes(request: Request, user: Auth, desde: str = "", hasta: str = ""):
    hoy = date.today()
    if not hasta:
        hasta = hoy.isoformat()
    if not desde:
        desde = hoy.replace(day=1).isoformat()
    rep = db.reporte_gastronomia(desde, hasta)
    return templates.TemplateResponse(request, "salon/reportes.html", {
        "active": "salon_reportes", "rep": rep,
    })
