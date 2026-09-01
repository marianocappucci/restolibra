"""API JSON de Ventas (POS) para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Portado tal cual desde Contalibra (mismo `db_ventas.py`
compartido via `database.py`, sin diferencias de campos) -- ver
web/api/clientes.py para el patron general de esta etapa.

Nota de alcance (ver instrucciones de la migracion): este motor de Ventas
de mostrador es reusado tal cual por Salon/Pedidos en una etapa posterior
para el cobro de mesas/pedidos -- no se anticipa esa integracion aca.

El autocompletado de productos (`GET /productos/buscar`) y los PDFs
(`GET /ventas/{id}/ticket`, `GET /ventas/{id}/recibo`) siguen viviendo en
sus routers HTML tal cual (ya son JSON o descargas autenticadas por
cookie) -- la SPA los consume directo, sin reimplementarlos.

## El cobro por QR, que estuvo perdido

⚠️ Hasta el 2026-08-31 este docstring decia que `mp-qr`/`mp-status` "siguen
viviendo en sus routers HTML". **No era cierto**: se dieron de baja en el
corte a React porque no quedo ningun boton en la SPA que los invocara, y el
comentario de `web/routers/ventas.py` lo dice. O sea que el producto perdio
el cobro por QR y la unica senal era un docstring que afirmaba lo contrario.

Vuelven aca, como JSON, con el modelo de acreditacion de la familia: el pago
nace `pendiente` y la caja se escribe recien cuando MercadoPago dice que
entro. Ver `db_ventas.acreditar_pago_qr`.
"""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from libracore import medios_pago
from libracore import pagos as acreditacion

from app import config_manager, database as db, mp_api, venta_facturacion
from app.web.api_auth import get_current_user_json, require_role_json

router = APIRouter(prefix="/api/ventas", tags=["ventas"])

# 🔴 Del motor, no de una copia escrita aca. Este repo tenia la MISMA lista
# escrita TRES VECES --`api/ventas.py`, `api/cajas.py` y `api/pedidos.py`-- y
# otras 25 copias vivian en los demas productos, ya divergiendo entre si. Ver
# `libracore.medios_pago` y wiki/concepts/medios-de-pago-familia-libra.md.
MEDIOS_PAGO = medios_pago.para_selector()


class ItemPayload(BaseModel):
    nombre: str
    qty: float
    precio: float
    producto_id: int | None = None


#: El medio que el QR de MercadoPago cobra. Sale del vocabulario del motor y no
#: de un literal: la familia tuvo cuatro grafías distintas para esto.
MEDIO_DEL_QR = medios_pago.validar("mercadopago")


class PagoPayload(BaseModel):
    #: 🔴 **Se valida.** Hasta el 2026-08-24 era un `str` pelado, y
    #: `add_venta_pago()` tampoco miraba: la lista de medios solo existia para
    #: poblar el `<Select>`. Un medio inventado entraba, creaba su movimiento de
    #: caja y salia en el cierre como un bucket suelto con el nombre crudo -- la
    #: plata bien contada y **el reparto mal**. Nadie se enteraba.
    #:
    #: Las seis grafias de siempre siguen siendo validas, asi que un frontend
    #: viejo no se rompe; lo que rebota es lo que nunca debio entrar.
    medio: str
    monto: float
    referencia: str = ""
    #: 🔴 **"Le voy a cobrar recién ahora", no "ya me pagó".**
    #:
    #: Sin esta marca el backend no puede distinguir el cliente que ya
    #: transfirió del que todavía no escaneó nada, y la venta nace cobrada —con
    #: el movimiento de caja escrito— antes de que entre un peso. Es el defecto
    #: que el humano encontró probando el QR en Contalibra el 2026-08-31.
    cobrar_con_qr: bool = False

    @field_validator("medio")
    @classmethod
    def _medio_del_vocabulario(cls, v: str) -> str:
        return medios_pago.validar(v)

    @model_validator(mode="after")
    def _el_qr_solo_cobra_lo_suyo(self):
        """🔴 Un `cobrar_con_qr` en efectivo dejaría la venta pendiente **para
        siempre**: nada acredita un pago en efectivo. El síntoma sería una venta
        impaga que el cajero jura haber cobrado, y aparecería en el arqueo del
        día siguiente. Mejor rebotarlo acá.
        """
        if self.cobrar_con_qr and self.medio != MEDIO_DEL_QR:
            raise ValueError(
                f"«Cobrar con QR» sólo aplica al medio {MEDIO_DEL_QR}.")
        return self


class VentaPayload(BaseModel):
    fecha: str
    items: list[ItemPayload]
    descuento: float = 0
    cliente_id: int | None = None
    cliente_nombre: str = ""
    observaciones: str = ""
    pagos: list[PagoPayload]


@router.get("/medios-pago")
def listar_medios_pago():
    # 🔴 Se llamaba `medios_pago` y TAPABA al modulo del motor dentro de este
    # archivo: `medios_pago.validar(...)` revienta con "'function' object has
    # no attribute 'validar'". La ruta no cambia -- el nombre de la funcion no
    # es parte del contrato HTTP.
    return MEDIOS_PAGO


@router.get("")
def listar(desde: str = "", hasta: str = "", q: str = "", tab: str = "todas"):
    if tab not in ("todas", "sin_facturar", "facturadas"):
        tab = "todas"
    return db.get_all_ventas(desde=desde, hasta=hasta, q=q, tab=tab)


@router.post("")
def crear(payload: VentaPayload, user: dict = Depends(get_current_user_json)):
    items = [
        {
            "nombre": i.nombre.strip(), "qty": i.qty, "precio": max(0.0, i.precio),
            "subtotal": round(i.qty * max(0.0, i.precio), 2), "producto_id": i.producto_id,
        }
        for i in payload.items if i.nombre.strip() and i.qty > 0
    ]
    if not items:
        raise HTTPException(422, "Debe agregar al menos un ítem.")

    subtotal = round(sum(i["subtotal"] for i in items), 2)
    descuento = min(max(0.0, payload.descuento), subtotal)
    total = round(subtotal - descuento, 2)

    # 🔑 Cada línea declara su estado. El QR que se va a cobrar recién ahora
    # nace `PENDIENTE`: queda registrado como pago y **no toca la caja** hasta
    # que MercadoPago diga que entró.
    pagos = [
        {
            "medio": p.medio, "monto": p.monto, "referencia": p.referencia,
            "estado": (acreditacion.EstadoAcreditacion.PENDIENTE
                       if p.cobrar_con_qr
                       else acreditacion.EstadoAcreditacion.APROBADO).value,
        }
        for p in payload.pagos if p.monto > 0
    ]
    if not pagos:
        raise HTTPException(422, "Debe registrar al menos un medio de pago.")
    # 🔴 Lo ACREDITADO, no la suma de las líneas: con la suma, una venta cuyo
    # único pago está pendiente nacería "cobrada" —que es exactamente el cartel
    # que el humano vio mal en Contalibra—.
    total_pagado = float(acreditacion.acreditado(pagos))

    cliente_nombre = payload.cliente_nombre.strip()
    if payload.cliente_id:
        c = db.get_client(payload.cliente_id)
        if c:
            cliente_nombre = c["name"]

    if total_pagado >= total:
        estado = "cobrada"
    elif total_pagado > 0:
        estado = "parcial"
    else:
        estado = "pendiente"

    mods = db.get_modulos()
    try:
        venta_id = db.crear_venta_directa(
            fecha=payload.fecha, items=items, subtotal=subtotal, descuento=descuento,
            total=total, cliente_id=payload.cliente_id, cliente_nombre=cliente_nombre,
            usuario_id=user["id"], observaciones=payload.observaciones.strip(), estado=estado,
            pagos=pagos, stock_habilitado=bool(mods.get("stock")),
        )
    except (sqlite3.IntegrityError, RuntimeError):
        raise HTTPException(409, "No se pudo registrar la venta (conflicto con otra venta simultánea). Reintentá.")

    return db.get_venta(venta_id)


@router.get("/{vid}")
def detalle(vid: int):
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")
    return venta


@router.post("/{vid}/anular", dependencies=[Depends(require_role_json("admin"))])
def anular(vid: int, user: dict = Depends(get_current_user_json)):
    if not db.get_venta(vid):
        raise HTTPException(404, "Venta no encontrada")
    db.anular_venta(vid, usuario_id=user["id"])
    return db.get_venta(vid)


# ── El cobro por QR ──────────────────────────────────────────────────────────

@router.post("/{vid}/mp-qr")
async def venta_mp_qr(vid: int, user: dict = Depends(get_current_user_json)):
    """Pone el monto de esta venta a cobrar en el QR de la caja.

    🔑 **No devuelve ninguna imagen, y no es un olvido.** Es el modelo de **QR
    fijo por punto de venta**: el cartel impreso del mostrador, que no cambia
    nunca. Lo que esta llamada cambia es *cuánto cobra* cuando alguien lo
    escanea. Para ver o imprimir ese cartel está el botón de Configuración →
    MercadoPago.
    """
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")

    cfg = config_manager.load()
    access_token = cfg.get("mp_access_token", "")
    pos_id = cfg.get("mp_pos_id", "")
    user_id = cfg.get("mp_user_id", "")
    if not access_token or not pos_id or not user_id:
        raise HTTPException(
            400,
            "Configurá el Access Token, el User ID y el POS ID de MercadoPago "
            "en Configuración → Integraciones.",
        )

    try:
        await mp_api.crear_orden_qr(
            user_id=user_id, pos_id=pos_id, access_token=access_token,
            external_reference=f"venta-{vid}",
            titulo=f"Venta {venta['numero']}",
            items=venta["items"], total=venta["total"],
        )
    except Exception as e:
        raise HTTPException(502, f"MercadoPago rechazó la orden: {e}") from None

    return {"ok": True, "total": venta["total"], "pos_id": pos_id}


@router.get("/{vid}/mp-status")
async def venta_mp_status(vid: int, user: dict = Depends(get_current_user_json)):
    """¿Ya entró la plata del QR de esta venta?

    Es un GET **con efectos**: cuando MercadoPago dice `approved`, acredita el
    pago —escribe el movimiento de caja y recalcula el estado de la venta—.

    🔑 Acreditar es idempotente (`acreditar_pago_qr` sólo toca lo que está
    `pendiente`), así que el poll pegándole cada pocos segundos no duplica la
    plata, y da igual si el webhook llegó primero. Lo mismo vale para la
    factura: `facturar_venta` devuelve la que ya exista.

    🔴 **Acá también se factura, y no es redundante con el webhook.** Son los
    DOS caminos por los que este producto se entera de que el QR se pagó, y en
    la instancia real de Contalibra el webhook **no llegó nunca** —cero POST en
    el log, contra cinco a `mp-qr`—. Si sólo facturara el webhook, la venta
    quedaría cobrada y "Sin facturar" sin que nada lo dijera.
    """
    venta = db.get_venta(vid)
    if not venta:
        raise HTTPException(404, "Venta no encontrada")

    if venta.get("mp_payment_id"):
        # Ya estaba acreditada. Se llama igual: cubre a las que se acreditaron
        # antes de que esto existiera, y no hace nada si no hay pendientes.
        db.acreditar_pago_qr(vid, venta["mp_payment_id"], usuario_id=user["id"])
        # Y se intenta facturar igual, por el mismo motivo: cubre a las que se
        # cobraron antes de que existiera la automática, y a las que fallaron el
        # CAE la primera vez.
        factura_id = (venta.get("factura_id")
                      or await venta_facturacion.facturar_si_esta_prendida(vid))
        return {"status": "approved", "payment_id": venta["mp_payment_id"],
                "factura_id": factura_id}

    access_token = config_manager.load().get("mp_access_token", "")
    if not access_token:
        raise HTTPException(400, "Access Token de MercadoPago no configurado.")

    try:
        pago = await mp_api.buscar_pago_por_referencia(f"venta-{vid}", access_token)
    except Exception as e:
        raise HTTPException(502, f"Sin respuesta de MercadoPago: {e}") from None

    if not pago:
        return {"status": "pending"}

    estado = acreditacion.estado_desde_mercadopago(pago.get("status"))
    if estado is not acreditacion.EstadoAcreditacion.APROBADO:
        # `authorized` y cualquier estado desconocido cuentan como pendiente:
        # lo decide el motor, no un `if` escrito acá.
        return {"status": pago.get("status") or "pending"}

    payment_id = str(pago["id"])
    db.set_venta_mp_payment(vid, payment_id)
    # 🔴 **Acá entra la plata a la caja, y no antes.** Si la venta se creó con
    # `cobrar_con_qr`, su pago quedó `pendiente` y sin movimiento de caja;
    # recién ahora se acredita.
    db.acreditar_pago_qr(vid, payment_id, usuario_id=user["id"])
    factura_id = await venta_facturacion.facturar_si_esta_prendida(vid)
    return {"status": "approved", "payment_id": payment_id, "factura_id": factura_id}
