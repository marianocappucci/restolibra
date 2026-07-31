"""API JSON de Productos para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Etapa C: modulo con divergencia real respecto a
Contalibra (ver web/api/productos.py de ese repo, que es solo CRUD) --
Restolibra le suma ficha tecnica/receta (costeo, food cost %, produccion
por lotes) y los campos `estacion`/`vendible`, propios de la operacion
gastronomica. Reusa db_productos.py/db_recetas.py (shims de
libracore.db.productos y db_recetas.py propio de Restolibra) tal cual --
misma logica que los routers Jinja2 viejos (web/routers/productos.py),
sin renderizar template.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app.web.api_auth import get_current_user_json

router = APIRouter(prefix="/api/productos", tags=["productos"])

UNIDADES = ["u", "kg", "g", "lt", "ml", "m", "cm", "m²", "caja", "par", "docena", "pack"]
ESTACIONES = ["", "cocina", "barra"]


class ProductoPayload(BaseModel):
    nombre: str
    codigo: str = ""
    descripcion: str = ""
    precio_venta: float = 0
    precio_costo: float = 0
    unidad: str = "u"
    categoria: str = ""
    stock_minimo: float = 0
    estacion: str = ""
    vendible: bool = True
    activo: bool = True


class CategoriaPayload(BaseModel):
    nombre: str


class RecetaItemPayload(BaseModel):
    ingrediente_id: int
    cantidad: float


class RecetaPayload(BaseModel):
    items: list[RecetaItemPayload] = []
    notas: str = ""
    rinde: float = 1
    rinde_unidad: str = "u"
    rendimiento_pct: float = 100


class ProducirPayload(BaseModel):
    cantidad: float


# ── Productos (CRUD base) ────────────────────────────────────────────────────

@router.get("")
def listar(q: str = ""):
    return db.get_all_productos(q=q)


@router.get("/categorias")
def listar_categorias():
    return db.get_categorias_producto()


@router.post("/categorias")
def crear_categoria(payload: CategoriaPayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    db.create_categoria_producto(nombre)
    return db.get_categorias_producto()


@router.delete("/categorias/{cid}")
def eliminar_categoria(cid: int):
    db.delete_categoria_producto(cid)
    return db.get_categorias_producto()


@router.get("/reportes-costos")
def reportes_costos(desde: str = "", hasta: str = ""):
    """Food cost/margen por plato (productos vendibles con receta) + consumo
    real de insumos (ventas + mermas) en el rango. Equivalente JSON de
    web/templates/productos/reportes_costos.html."""
    return {
        "reporte": db.get_reporte_food_cost(),
        "consumo": db.get_consumo_insumos(desde=desde, hasta=hasta),
    }


@router.post("")
def crear(payload: ProductoPayload):
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    codigo = payload.codigo.strip()
    categoria = payload.categoria.strip()
    if not codigo:
        codigo = db.generar_codigo_producto(categoria)
    try:
        pid = db.create_producto(
            nombre=nombre, codigo=codigo,
            descripcion=payload.descripcion.strip(),
            precio_venta=payload.precio_venta, precio_costo=payload.precio_costo,
            unidad=payload.unidad, categoria=categoria,
            stock_minimo=payload.stock_minimo,
            estacion=payload.estacion.strip(),
            vendible=1 if payload.vendible else 0,
        )
    except Exception as e:
        raise HTTPException(422, str(e))
    return db.get_producto(pid)


@router.put("/{pid}")
def actualizar(pid: int, payload: ProductoPayload):
    if not db.get_producto(pid):
        raise HTTPException(404, "Producto no encontrado")
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(422, "El nombre es obligatorio.")
    try:
        db.update_producto(
            pid=pid, nombre=nombre, codigo=payload.codigo.strip(),
            descripcion=payload.descripcion.strip(),
            precio_venta=payload.precio_venta, precio_costo=payload.precio_costo,
            unidad=payload.unidad, categoria=payload.categoria.strip(),
            activo=1 if payload.activo else 0, stock_minimo=payload.stock_minimo,
            estacion=payload.estacion.strip(),
            vendible=1 if payload.vendible else 0,
        )
    except Exception as e:
        raise HTTPException(422, str(e))
    return db.get_producto(pid)


@router.delete("/{pid}")
def eliminar(pid: int):
    if not db.get_producto(pid):
        raise HTTPException(404, "Producto no encontrado")
    db.delete_producto(pid)
    return {"ok": True}


# ── Receta / ficha técnica ───────────────────────────────────────────────────

@router.get("/{pid}/receta")
def obtener_receta(pid: int):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    receta = db.get_receta(pid)
    costo = db.costo_receta(pid)
    return {
        "producto": producto,
        "receta": receta,
        # Candidatos para agregar como ingrediente: cualquier producto activo
        # salvo el propio (evita recetas auto-referenciadas), igual que el
        # router Jinja2 viejo -- incluye insumos (vendible=0) a propósito.
        "ingredientes": [p for p in db.get_all_productos(solo_activos=True) if p["id"] != pid],
        "costo": costo,
        "food_cost_pct": db.food_cost_pct(pid, producto["precio_venta"], costo),
        "stock_actual": db.get_stock_actual(pid),
    }


@router.put("/{pid}/receta")
def guardar_receta(pid: int, payload: RecetaPayload):
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    items = [
        {"ingrediente_id": it.ingrediente_id, "cantidad": it.cantidad}
        for it in payload.items if it.ingrediente_id and it.cantidad
    ]
    db.guardar_receta(
        pid, items, notas=payload.notas.strip(),
        rinde=payload.rinde or 1,
        rinde_unidad=payload.rinde_unidad.strip() or "u",
        rendimiento_pct=payload.rendimiento_pct or 100,
    )
    costo = db.costo_receta(pid)
    return {
        "producto": db.get_producto(pid),
        "receta": db.get_receta(pid),
        "costo": costo,
        "food_cost_pct": db.food_cost_pct(pid, producto["precio_venta"], costo),
        "stock_actual": db.get_stock_actual(pid),
    }


@router.delete("/{pid}/receta")
def eliminar_receta(pid: int):
    if not db.get_producto(pid):
        raise HTTPException(404, "Producto no encontrado")
    db.eliminar_receta(pid)
    return {"ok": True}


@router.post("/{pid}/receta/producir")
def producir_receta(pid: int, payload: ProducirPayload,
                    user: dict = Depends(get_current_user_json)):
    """`get_current_user_json` ya corre como dependency del router (ver
    web/app.py) -- se vuelve a declarar acá (FastAPI cachea el resultado
    por request) solo para poder leer `user["id"]` y armar el movimiento de
    stock con usuario, igual que web/routers/productos.py."""
    producto = db.get_producto(pid)
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    if payload.cantidad <= 0:
        raise HTTPException(422, "La cantidad a producir debe ser mayor a 0.")
    try:
        db.producir_receta(pid, payload.cantidad, usuario_id=user.get("id"))
    except ValueError as e:
        raise HTTPException(422, str(e))
    costo = db.costo_receta(pid)
    return {
        "producto": db.get_producto(pid),
        "receta": db.get_receta(pid),
        "costo": costo,
        "food_cost_pct": db.food_cost_pct(pid, producto["precio_venta"], costo),
        "stock_actual": db.get_stock_actual(pid),
    }
