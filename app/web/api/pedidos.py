"""API JSON de Pedidos para la SPA -- Etapa D de la migración a React (ver
wiki/entities/restolibra.md, "3 módulos gastronómicos sin precedente").
Cubre dos cosas del dominio real (`web/routers/pedidos.py`, que queda
intacto):

1. El **board de canales sin mesa** (barra/takeaway/delivery) y el alta de
   un pedido nuevo por canal -- equivalente JSON de `/pedidos` y
   `/pedidos/nuevo`.
2. La pantalla **canónica de "pedido abierto"** (`GET /api/pedidos/{pid}` +
   ítems + enviar a cocina/barra + anular + cobrar) -- en el sistema real
   un pedido de mesa (`canal='salon'`) y uno de barra/takeaway/delivery
   comparten exactamente la misma tabla `pedidos` y el mismo flujo de cobro
   (`web/routers/salon.py: /salon/pedido/{pid}` y
   `web/routers/pedidos.py` navegan los dos a esa misma ruta Jinja2). Acá
   se expone ese detalle bajo un único prefijo `/api/pedidos/{pid}` sin
   importar si el pedido nació de una mesa o de un canal, para que el
   frontend (`PedidoDetalle.tsx`) sea un solo componente compartido -- ver
   reporte final de la Etapa D. `web/api/salon.py` sólo crea el pedido
   (`POST /api/salon/mesa/{id}/abrir`) y devuelve su id; todo lo demás pasa
   por acá.

`MEDIOS_PAGO` se duplica de `web/api/ventas.py` (mismos 6 medios) en vez de
importarse: ese router está gateado por `require_module("ventas")` en
`web/app.py`, y el cobro de un pedido de salón tiene que funcionar aunque
el módulo "ventas" (POS de mostrador clásico) esté apagado en el plan --
sólo depende de "restaurant". Motor de cobro real: `db.cobrar_pedido`
(`db_cobro_pedido.py`, reusa `db_ventas.py`), sin reescribir nada.
"""
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from libracore import medios_pago
from libracore import pagos as acreditacion
from pydantic import BaseModel, field_validator, model_validator

from app import database as db
from app.web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/pedidos", tags=["pedidos"])

CANALES_SIN_MESA = ["barra", "takeaway", "delivery"]

# 🔴 Del motor. Seguia duplicada de `api/ventas.py` --el docstring de arriba
# explica por que no se importaba de alli: este router funciona con el modulo
# "ventas" apagado-- pero esa razon nunca pidio COPIAR LA LISTA, solo no depender
# de aquel modulo. Salir del motor resuelve las dos cosas.
MEDIOS_PAGO = medios_pago.para_selector()


@router.get("/medios-pago")
def listar_medios_pago():
    # 🔴 Se llamaba `medios_pago` y TAPABA al modulo del motor dentro de este
    # archivo: `medios_pago.validar(...)` revienta con "'function' object has
    # no attribute 'validar'". La ruta no cambia -- el nombre de la funcion no
    # es parte del contrato HTTP.
    return MEDIOS_PAGO


# ── Board de canales sin mesa (barra/takeaway/delivery) ──────────────────────

@router.get("")
def board():
    activos = db.get_pedidos_activos(canales=CANALES_SIN_MESA)
    por_canal = {c: [p for p in activos if p["canal"] == c] for c in CANALES_SIN_MESA}
    return {"por_canal": por_canal}


class PedidoNuevoPayload(BaseModel):
    canal: str = "barra"
    cliente_nombre: str = ""
    telefono: str = ""
    direccion: str = ""
    repartidor: str = ""
    costo_envio: float = 0
    hora_retiro: str = ""
    observaciones: str = ""


@router.post("")
def crear(payload: PedidoNuevoPayload, user: dict = Depends(get_current_user_json)):
    canal = payload.canal.strip()
    if canal not in CANALES_SIN_MESA:
        raise HTTPException(400, "Canal inválido")
    pid = db.crear_pedido(
        canal=canal,
        usuario_id=user["id"],
        cliente_nombre=payload.cliente_nombre.strip(),
        telefono=payload.telefono.strip(),
        direccion=payload.direccion.strip(),
        repartidor=payload.repartidor.strip(),
        costo_envio=max(0.0, payload.costo_envio) if canal == "delivery" else 0.0,
        hora_retiro=payload.hora_retiro.strip(),
        observaciones=payload.observaciones.strip(),
    )
    return {"pedido_id": pid}


# ── Menú de productos (para agregar ítems, con recetas para modificadores) ──

@router.get("/menu")
def menu(q: str = ""):
    productos = db.get_all_productos(solo_activos=True, solo_vendibles=True, q=q)
    recetas_por_producto: dict[str, list[dict]] = {}
    for p in productos:
        receta = db.get_receta(p["id"])
        if receta and receta["ingredientes"]:
            recetas_por_producto[str(p["id"])] = receta["ingredientes"]
    return {"productos": productos, "recetas_por_producto": recetas_por_producto}


# ── Pedido abierto (canónico, compartido mesa / sin mesa) ────────────────────

@router.get("/{pid}")
def detalle(pid: int):
    pedido = db.get_pedido(pid)
    if not pedido:
        raise HTTPException(404, "Pedido no encontrado")
    return pedido


class ModificadorPayload(BaseModel):
    ingrediente_id: int
    ingrediente_nombre: str
    modo: str  # "quitar" | "doble"


class ItemPayload(BaseModel):
    producto_id: int | None = None
    nombre: str = ""
    precio: float = 0
    estacion: str = ""
    qty: float = 1
    nota: str = ""
    modificadores: list[ModificadorPayload] = []


@router.post("/{pid}/items")
def agregar_item(pid: int, payload: ItemPayload):
    pedido = db.get_pedido(pid)
    if not pedido or pedido["estado"] != "abierto":
        raise HTTPException(400, "Pedido no editable")

    qty = payload.qty if payload.qty and payload.qty > 0 else 1.0
    nota = payload.nota.strip()
    modificadores = json.dumps([m.model_dump() for m in payload.modificadores]) if payload.modificadores else ""

    if payload.producto_id:
        prod = db.get_producto(payload.producto_id)
        if not prod:
            raise HTTPException(404, "Producto inexistente")
        db.add_pedido_item(
            pid, nombre=prod["nombre"], qty=qty, precio=float(prod["precio_venta"]),
            producto_id=prod["id"], estacion=prod.get("estacion") or "", nota=nota,
            modificadores=modificadores,
        )
    else:
        nombre = payload.nombre.strip()
        if not nombre:
            raise HTTPException(422, "Falta producto_id o nombre.")
        precio = max(0.0, payload.precio)
        db.add_pedido_item(pid, nombre=nombre, qty=qty, precio=precio, estacion=payload.estacion.strip(), nota=nota)

    return db.get_pedido(pid)


@router.delete("/{pid}/items/{item_id}")
def eliminar_item(pid: int, item_id: int):
    db.delete_pedido_item(item_id)
    return db.get_pedido(pid)


class NotaPayload(BaseModel):
    nota: str = ""


@router.put("/{pid}/items/{item_id}/nota")
def editar_nota(pid: int, item_id: int, payload: NotaPayload):
    db.set_pedido_item_nota(item_id, payload.nota)
    return db.get_pedido(pid)


@router.post("/{pid}/enviar")
def enviar(pid: int):
    comandas = db.enviar_a_estaciones(pid)
    return {"comandas_creadas": comandas, "pedido": db.get_pedido(pid)}


@router.post("/{pid}/anular")
def anular(pid: int):
    if not db.anular_pedido(pid):
        raise HTTPException(400, "El pedido no está abierto.")
    return {"ok": True}


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
    #: Sin esta marca el pedido se cierra como cobrado y el movimiento de caja
    #: se escribe antes de que nadie escanee nada. Con ella, el pago nace
    #: `pendiente`, el pedido queda `cobrando`, y la mesa muestra **"esperando
    #: pago"** en vez de "cobrada, liberar".
    cobrar_con_qr: bool = False

    @field_validator("medio")
    @classmethod
    def _medio_del_vocabulario(cls, v: str) -> str:
        return medios_pago.validar(v)

    @model_validator(mode="after")
    def _el_qr_solo_cobra_lo_suyo(self):
        """🔴 Un `cobrar_con_qr` en efectivo dejaría el pedido esperando **para
        siempre**: nada acredita un pago en efectivo, así que la mesa quedaría
        en "esperando pago" hasta que alguien la libere a mano, con la plata ya
        en el cajón."""
        if self.cobrar_con_qr and self.medio != MEDIO_DEL_QR:
            raise ValueError(
                f"«Cobrar con QR» sólo aplica al medio {MEDIO_DEL_QR}.")
        return self


class CobroPayload(BaseModel):
    pagos: list[PagoPayload]
    descuento: float = 0
    cliente_nombre: str = ""


@router.post("/{pid}/cobrar")
def cobrar(pid: int, payload: CobroPayload, user: dict = Depends(get_current_user_json)):
    pedido = db.get_pedido(pid)
    if not pedido:
        raise HTTPException(404, "Pedido no encontrado")

    # Cada línea declara su estado. El QR que se va a cobrar recién ahora nace
    # `PENDIENTE`: no toca la caja, y el pedido queda `cobrando` hasta que
    # MercadoPago diga que entró.
    pagos = [
        {
            "medio": p.medio, "monto": p.monto, "referencia": p.referencia.strip(),
            "estado": (acreditacion.EstadoAcreditacion.PENDIENTE
                       if p.cobrar_con_qr
                       else acreditacion.EstadoAcreditacion.APROBADO).value,
        }
        for p in payload.pagos if p.monto > 0
    ]
    if not pagos:
        raise HTTPException(422, "Registrá al menos un medio de pago.")

    try:
        venta_id = db.cobrar_pedido(
            pid, pagos=pagos, descuento=max(0.0, payload.descuento),
            cliente_nombre=payload.cliente_nombre.strip(), usuario_id=user["id"],
        )
    except ValueError:
        # Perdió la carrera contra otro cobro simultáneo del mismo pedido
        # (doble click, dos mozos) -- el UPDATE condicional de
        # `db.cobrar_pedido` ya "reclamó" el pedido para el otro cobro. En
        # vez de un 500/409 ciego, resolvemos: si ya está cobrado, devolvemos
        # esa venta (idempotente desde la perspectiva del segundo mozo).
        pedido_actual = db.get_pedido(pid)
        # ⚠️ `cobrando` cuenta TAMBIÉN. Antes esto miraba sólo `cobrado`, y con
        # el cobro por QR el pedido queda en `cobrando` hasta que entra la
        # plata: el segundo mozo recibía un 409 y volvía a cobrar una cuenta que
        # ya estaba puesta en el QR. Lo encontró un test.
        if (pedido_actual and pedido_actual["estado"] in ("cobrado", "cobrando")
                and pedido_actual.get("venta_id")):
            return {"venta_id": pedido_actual["venta_id"], "ya_cobrado": True}
        raise HTTPException(409, "Este pedido ya fue cobrado o modificado. Volvé al pedido y verificá.")
    except sqlite3.IntegrityError:
        raise HTTPException(409, "No se pudo registrar el cobro (conflicto con otra operación simultánea). Reintentá.")

    return {"venta_id": venta_id, "ya_cobrado": False}
