"""API JSON de Salón (mesas/salones/reservas/cargos/reportes gastronómicos)
para la SPA -- Etapa D de la migración a React (ver wiki/entities/restolibra.md,
"3 módulos gastronómicos sin precedente"). A diferencia de las etapas
anteriores (reuso 1:1 de Contalibra o divergencia sobre un mismo dominio ya
migrado), Salón no tiene ningún equivalente Jinja2 del lado de Contalibra --
la única fuente de verdad es `web/routers/salon.py` (que queda intacto) y
`db_salones.py`/`db_mesas.py`/`db_reservas.py`/`db_reportes_gastronomicos.py`
(shims/módulos propios de Restolibra sobre `database.py`), reusados tal cual
sin reescribir lógica de negocio.

Convención de URLs (deliberada, ver reporte final de la Etapa D): los
endpoints *operativos* que un mozo necesita (mapa de mesas, abrir mesa,
reservas) viven bajo `/api/salon/mapa`, `/api/salon/mesa/...` y
`/api/salon/reservas...` -- mismo prefijo que usaba el router Jinja2 viejo
(`/salon/mesa/...`, `/salon/reservas...`), permitiendo el mismo esquema de
allowlist por prefijo de string que ya usa `CurrentUserMiddleware` en
`web/app.py`. Los endpoints *administrativos* (ABM de salones/mesas,
cargos automáticos, reportes) viven bajo `/api/salon/config/...` y
`/api/salon/reportes`, calcados del prefijo `/salon/config/...` que el
middleware viejo YA excluye para el rol mozo -- así el mismo patrón de
allowlist por prefijo sigue funcionando sin cambios estructurales cuando
se lo actualice para incluir estos paths nuevos.

El detalle de un pedido abierto (agregar ítems, enviar a cocina/barra,
cobrar, anular) -- tanto si nace de una mesa como de un canal sin mesa --
vive en `web/api/pedidos.py` (pantalla compartida `PedidoDetalle.tsx`), no
acá: `POST /api/salon/mesa/{id}/abrir` sólo crea el pedido y devuelve su id
para que el frontend navegue a esa pantalla común.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import config_manager
from app import database as db
from app.web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/salon", tags=["salon"])


# ── Mapa de mesas / mesa individual (mozo) ───────────────────────────────────

@router.get("/mapa")
def mapa(salon_id: int = 0):
    salones = db.get_salones(solo_activos=True)
    sel = salon_id or (salones[0]["id"] if salones else 0)
    mesas = db.get_mesas(salon_id=sel) if sel else []
    reservas_por_mesa = db.get_proximas_reservas_por_mesa(date.today().isoformat())
    return {
        "salones": salones, "salon_sel": sel, "mesas": mesas,
        "reservas_por_mesa": {str(k): v for k, v in reservas_por_mesa.items()},
    }


@router.get("/mesa/{mid}")
def mesa_detalle(mid: int):
    mesa = db.get_mesa(mid)
    if not mesa:
        raise HTTPException(404, "Mesa no encontrada")
    pedido_abierto = db.get_pedido_abierto_de_mesa(mid)
    reservas_hoy = [
        r for r in db.get_reservas(date.today().isoformat(), estado="pendiente")
        if r["mesa_id"] == mid
    ]
    return {
        "mesa": mesa,
        "pedido_abierto_id": pedido_abierto["id"] if pedido_abierto else None,
        "reservas_hoy": reservas_hoy,
    }


class AbrirMesaPayload(BaseModel):
    comensales: int = 1


def _aplicar_cargos_automaticos(pedido_id: int, comensales: int):
    """Idéntica a `_aplicar_cargos_automaticos` de web/routers/salon.py
    (cubierto por comensal + panera por mesa, sin estación -> no generan
    comanda). No se importa de ahí porque es una función privada del router
    Jinja2 (no forma parte de database.py); se duplica acá deliberadamente
    en vez de tocar ese router, que queda fuera de alcance de esta etapa."""
    cfg = config_manager.load()

    def _precio(key: str) -> float:
        try:
            return max(0.0, float(str(cfg.get(key) or 0).replace(",", ".")))
        except (ValueError, TypeError):
            return 0.0

    n = max(1, int(comensales or 1))
    if str(cfg.get("cubierto_activo", "0")).strip() in ("1", "true", "True"):
        p = _precio("cubierto_precio")
        if p > 0:
            db.add_pedido_item(pedido_id, "Cubierto", n, p, estacion="")
    if str(cfg.get("panera_activo", "0")).strip() in ("1", "true", "True"):
        p = _precio("panera_precio")
        if p > 0:
            db.add_pedido_item(pedido_id, "Panera", 1, p, estacion="")


@router.post("/mesa/{mid}/abrir")
def mesa_abrir(mid: int, payload: AbrirMesaPayload, user: dict = Depends(get_current_user_json)):
    mesa = db.get_mesa(mid)
    if not mesa:
        raise HTTPException(404, "Mesa no encontrada")
    existente = db.get_pedido_abierto_de_mesa(mid)
    if existente:
        return {"pedido_id": existente["id"]}
    comensales = max(1, int(payload.comensales or 1))
    pid = db.crear_pedido(canal="salon", mesa_id=mid, comensales=comensales, usuario_id=user["id"])
    _aplicar_cargos_automaticos(pid, comensales)
    return {"pedido_id": pid}


@router.post("/mesa/{mid}/liberar")
def mesa_liberar(mid: int, user: dict = Depends(get_current_user_json)):
    """Deja la mesa libre. Es la acción del mozo cuando los clientes se van.

    🔴 **No la hace el cobro.** Hasta el 2026-08-31 `cobrar_pedido` liberaba la
    mesa en la misma transacción que movía la caja: la plata y la ocupación
    estaban pegadas sin motivo. Los cuatro que terminan el café siguen sentados
    después de pagar, y con el cobro por QR el pago puede quedar **pendiente**,
    donde liberar la mesa sería regalarla antes de que entre la plata.
    """
    if not db.get_mesa(mid):
        raise HTTPException(404, "Mesa no encontrada")
    if not db.liberar_mesa(mid):
        # 409 y no 200: la mesa tiene un pedido abierto, así que sigue ocupada.
        # Contestar "ok" dejaría al mozo mirando una mesa que no se movió sin
        # saber por qué.
        raise HTTPException(
            409,
            "La mesa tiene un pedido abierto. Cobralo o anulalo antes de liberarla.",
        )
    return {"ok": True}


# ── Reservas (mozo) ──────────────────────────────────────────────────────────

@router.get("/reservas")
def reservas_listar(fecha: str = "", mesa_id: int = 0):
    f = fecha or date.today().isoformat()
    reservas = db.get_reservas(f)
    if mesa_id:
        reservas = [r for r in reservas if r["mesa_id"] == mesa_id]
    return {"reservas": reservas, "fecha": f}


class ReservaPayload(BaseModel):
    mesa_id: int
    fecha: str
    hora: str
    cliente_nombre: str
    telefono: str = ""
    comensales: int = 1
    notas: str = ""


@router.post("/reservas")
def reservas_crear(payload: ReservaPayload):
    try:
        rid = db.crear_reserva(
            payload.mesa_id, payload.fecha, payload.hora, payload.cliente_nombre.strip(),
            comensales=max(1, payload.comensales), telefono=payload.telefono.strip(),
            notas=payload.notas.strip(),
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return db.get_reserva(rid)


@router.post("/reservas/{rid}/cancelar")
def reservas_cancelar(rid: int):
    db.cancelar_reserva(rid)
    return {"ok": True}


@router.post("/reservas/{rid}/sentar")
def reservas_sentar(rid: int, user: dict = Depends(get_current_user_json)):
    reserva = db.get_reserva(rid)
    if not reserva or reserva["estado"] != "pendiente":
        raise HTTPException(400, "Reserva no disponible")
    mesa_id = reserva["mesa_id"]
    existente = db.get_pedido_abierto_de_mesa(mesa_id)
    if existente:
        db.cumplir_reserva(rid)
        return {"pedido_id": existente["id"]}
    pid = db.crear_pedido(
        canal="salon", mesa_id=mesa_id, comensales=reserva["comensales"], usuario_id=user["id"],
        cliente_nombre=reserva["cliente_nombre"], telefono=reserva.get("telefono", ""),
    )
    _aplicar_cargos_automaticos(pid, reserva["comensales"])
    db.cumplir_reserva(rid)
    return {"pedido_id": pid}


# ── Configuración de salón (admin/gerente -- no mozo) ────────────────────────

@router.get("/config")
def config_get():
    salones = db.get_salones(solo_activos=False)
    mesas_por_salon = {s["id"]: db.get_mesas(salon_id=s["id"], solo_activas=False) for s in salones}
    cfg = config_manager.load()
    return {
        "salones": salones,
        "mesas_por_salon": {str(k): v for k, v in mesas_por_salon.items()},
        "cfg": {
            "cubierto_activo": str(cfg.get("cubierto_activo", "0")) == "1",
            "cubierto_precio": float(str(cfg.get("cubierto_precio") or 0).replace(",", ".") or 0),
            "panera_activo": str(cfg.get("panera_activo", "0")) == "1",
            "panera_precio": float(str(cfg.get("panera_precio") or 0).replace(",", ".") or 0),
        },
    }


class CargosPayload(BaseModel):
    cubierto_activo: bool = False
    cubierto_precio: float = 0
    panera_activo: bool = False
    panera_precio: float = 0


@router.post("/config/cargos")
def config_cargos(payload: CargosPayload):
    cfg = config_manager.load()
    cfg["cubierto_activo"] = "1" if payload.cubierto_activo else "0"
    cfg["cubierto_precio"] = str(max(0.0, payload.cubierto_precio))
    cfg["panera_activo"] = "1" if payload.panera_activo else "0"
    cfg["panera_precio"] = str(max(0.0, payload.panera_precio))
    config_manager.save(cfg)
    return {"ok": True}


class SalonPayload(BaseModel):
    nombre: str
    orden: int = 0


@router.post("/config/salones")
def config_salon_crear(payload: SalonPayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    sid = db.create_salon(nombre, payload.orden)
    return db.get_salon(sid)


class SalonEditPayload(BaseModel):
    nombre: str
    orden: int = 0
    activo: bool = True


@router.put("/config/salones/{sid}")
def config_salon_editar(sid: int, payload: SalonEditPayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    db.update_salon(sid, nombre, payload.orden, 1 if payload.activo else 0)
    salon = db.get_salon(sid)
    if not salon:
        raise HTTPException(404, "Salón no encontrado")
    return salon


@router.delete("/config/salones/{sid}")
def config_salon_eliminar(sid: int):
    if not db.delete_salon(sid):
        raise HTTPException(409, "No se puede eliminar el salón: tiene una mesa con un pedido abierto.")
    return {"ok": True}


class MesaPayload(BaseModel):
    salon_id: int
    nombre: str
    capacidad: int = 4


@router.post("/config/mesas")
def config_mesa_crear(payload: MesaPayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    mid = db.create_mesa(payload.salon_id, nombre, max(1, payload.capacidad))
    return db.get_mesa(mid)


class MesaEditPayload(BaseModel):
    nombre: str
    capacidad: int = 4
    activo: bool = True


@router.put("/config/mesas/{mid}")
def config_mesa_editar(mid: int, payload: MesaEditPayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    # `orden` hardcodeado en 0: así se comporta hoy web/routers/salon.py
    # (salon_config_mesa_editar nunca preserva el orden existente al
    # editar) -- se preserva el comportamiento real, no se "corrige" acá.
    db.update_mesa(mid, nombre, max(1, payload.capacidad), 0, 1 if payload.activo else 0)
    mesa = db.get_mesa(mid)
    if not mesa:
        raise HTTPException(404, "Mesa no encontrada")
    return mesa


@router.delete("/config/mesas/{mid}")
def config_mesa_eliminar(mid: int):
    if not db.delete_mesa(mid):
        raise HTTPException(409, "No se puede eliminar la mesa: tiene un pedido abierto.")
    return {"ok": True}


# ── Reportes gastronómicos (admin/gerente -- no mozo) ────────────────────────

@router.get("/reportes")
def reportes(desde: str = "", hasta: str = ""):
    hoy = date.today()
    hasta = hasta or hoy.isoformat()
    desde = desde or hoy.replace(day=1).isoformat()
    return db.reporte_gastronomia(desde, hasta)
