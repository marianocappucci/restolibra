"""API JSON de Clientes para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa la logica de negocio existente de `db_clients.py`
(via `database.py`) tal cual, sin duplicarla -- mismo patron que Contalibra
(web/api/clientes.py).

Etapa C (2026-07-24): se completan las dos features que la Etapa B habia
dejado deliberadamente afuera, portadas del estado actual de Contalibra:

- Activar/reactivar cliente: el listado ahora trae activos e inactivos
  (`get_all_clients_including_inactive`, igual que Contalibra) y se expone
  `POST /{id}/activar` para revertir una baja. `activar_cliente` ya existia
  en el paquete compartido `libracore.db.clients` (mismo pin v0.16.1 que
  Contalibra) y ya estaba re-exportada por el shim local `db_clients.py` --
  solo faltaba agregarla al import de `database.py`, sin logica nueva.
- Alias de facturacion por Mercado Pago (excepciones payer CUIT/email ->
  cliente): `crear_alias_facturacion`/`get_alias_facturacion_by_cliente`/
  `eliminar_alias_facturacion` ya existian en `libracore.db.mp` (mismo pin)
  y ya estaban re-exportadas por el shim local `db_mp.py` -- tampoco hizo
  falta portar logica local de Contalibra, solo agregarlas al import de
  `database.py` y exponerlas aca.

El toggle de auto-factura MP (`auto_facturar`/`toggle_auto_facturar`) ya
estaba portado desde la Etapa B: a diferencia del alias, ya es baseline en
Restolibra -- existe en su propio router Jinja2 viejo (web/routers/
clientes.py, web/templates/clientes/detail.html y form.html).

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


class AliasPayload(BaseModel):
    tipo: str
    valor: str


@router.get("")
def listar():
    return db.get_all_clients_including_inactive()


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
    """Incluye facturas, presupuestos, remitos y alias de facturacion del
    cliente (igual que web/templates/clientes/detail.html del router Jinja2
    viejo mas el alias de facturacion portado de Contalibra)."""
    cliente = db.get_client(cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    return {
        **cliente,
        "alias_facturacion": db.get_alias_facturacion_by_cliente(cliente_id),
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


@router.post("/{cliente_id}/alias-facturacion")
def crear_alias(cliente_id: int, payload: AliasPayload):
    if not db.get_client(cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    try:
        db.crear_alias_facturacion(payload.tipo.strip(), payload.valor.strip(), cliente_id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return db.get_alias_facturacion_by_cliente(cliente_id)


@router.delete("/{cliente_id}/alias-facturacion/{alias_id}")
def eliminar_alias(cliente_id: int, alias_id: int):
    if not db.get_client(cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    db.eliminar_alias_facturacion(alias_id)
    return db.get_alias_facturacion_by_cliente(cliente_id)


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
    return db.get_client(cliente_id)


@router.post("/{cliente_id}/activar")
def activar(cliente_id: int):
    if not db.get_client(cliente_id):
        raise HTTPException(404, "Cliente no encontrado")
    db.activar_cliente(cliente_id)
    return db.get_client(cliente_id)
