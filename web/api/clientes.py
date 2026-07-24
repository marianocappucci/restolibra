"""API JSON de Clientes para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa la logica de negocio existente de `db_clients.py`
(via `database.py`) tal cual, sin duplicarla -- mismo patron que Contalibra
(web/api/clientes.py), portado con dos features de Contalibra deliberadamente
NO incluidas en esta etapa (quedan para una etapa posterior):

- Activar/reactivar cliente: Contalibra lista clientes activos e inactivos
  (`get_all_clients_including_inactive`) y expone `POST /{id}/activar` para
  revertir una baja. Restolibra, igual que su router Jinja2 viejo
  (web/routers/clientes.py -> `cliente_eliminar`), solo da de baja
  (`desactivar_cliente`, sin UI para deshacerlo) -- por eso el listado usa
  `get_all_clients()` (solo activos) y no hay endpoint de reactivacion aca.
- Alias de facturacion por Mercado Pago (excepciones payer CUIT/email ->
  cliente): feature nueva que Contalibra le agrego hoy
  (`crear_alias_facturacion`/`get_alias_facturacion_by_cliente`/
  `eliminar_alias_facturacion`), sin equivalente en el router Jinja2 viejo de
  Restolibra. No se porta.

El toggle de auto-factura MP (`auto_facturar`/`toggle_auto_facturar`) SI se
porta: a diferencia del alias, ya es baseline en Restolibra -- existe en su
propio router Jinja2 viejo (web/routers/clientes.py, web/templates/clientes/
detail.html y form.html), no es algo que Contalibra haya agregado hoy.

El detalle (`GET /{cliente_id}`) tambien devuelve facturas, presupuestos y
remitos del cliente, igual que el router Jinja2 viejo de Restolibra
(`cliente_detail` -> clientes/detail.html) -- `get_facturas_by_client`/
`get_presupuestos_by_client`/`get_remitos_by_client` ya existian en
`database.py`.

Auth y gating de modulo se aplican en el `app.include_router(...)` de
web/app.py, no aca.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import database as db

router = APIRouter(prefix="/api/clientes", tags=["clientes"])

IVA_CONDITIONS = [
    "Responsable Inscripto",
    "Monotributista",
    "IVA Exento",
    "Consumidor Final",
    "No Alcanzado",
    "IVA No Responsable",
]


class ClientePayload(BaseModel):
    name: str
    address: str = ""
    cuit_dni: str = ""
    email: str = ""
    phone: str = ""
    iva_condition: str = ""
    auto_facturar: bool = False


@router.get("")
def listar():
    return db.get_all_clients()


@router.post("")
def crear(payload: ClientePayload):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "El nombre es obligatorio.")
    try:
        cliente_id = db.create_client(
            name, payload.address.strip(), payload.cuit_dni.strip(),
            payload.email.strip(), payload.phone.strip(), payload.iva_condition.strip(),
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return db.get_client(cliente_id)


@router.get("/{cliente_id}")
def detalle(cliente_id: int):
    """Incluye facturas, presupuestos y remitos del cliente (igual que
    web/templates/clientes/detail.html del router Jinja2 viejo)."""
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    return {
        **cliente,
        "facturas": db.get_facturas_by_client(cliente.get("cuit_dni") or "", cliente.get("name") or ""),
        "presupuestos": db.get_presupuestos_by_client(cliente_id),
        "remitos": db.get_remitos_by_client(cliente_id),
    }


@router.put("/{cliente_id}")
def actualizar(cliente_id: int, payload: ClientePayload):
    if not db.get_client(cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "El nombre es obligatorio.")
    db.update_client(
        cliente_id, name=name, address=payload.address.strip(),
        cuit_dni=payload.cuit_dni.strip(), email=payload.email.strip(),
        phone=payload.phone.strip(), iva_condition=payload.iva_condition.strip(),
        auto_facturar=1 if payload.auto_facturar else 0,
    )
    return db.get_client(cliente_id)


@router.post("/{cliente_id}/toggle-auto-facturar")
def toggle_auto_facturar(cliente_id: int):
    if not db.get_client(cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    db.toggle_auto_facturar(cliente_id)
    return db.get_client(cliente_id)


@router.post("/{cliente_id}/desactivar")
def desactivar(cliente_id: int):
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    if db.tiene_presupuestos_aprobados(cliente_id):
        raise HTTPException(
            422,
            f"No se puede desactivar {cliente['name']} porque tiene presupuestos aprobados. "
            "Primero hay que cancelar o rechazar esos presupuestos.",
        )
    db.desactivar_cliente(cliente_id)
    return {"ok": True}
