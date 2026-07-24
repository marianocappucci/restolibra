"""API JSON de Facturas (ARCA) para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `db_facturas.py`, `web/helpers/form_helper.py::
calculate_totals` y `web/helpers/arca_helper.py` (numeracion + CAE) tal cual
-- mismo patron confirmado hoy en Contalibra (ver web/api/facturas.py de ese
repo, mismo motor `libracore.db.facturas`). Auditado contra
`web/routers/facturas.py` (router Jinja2 viejo) antes de portar: el flujo
ARCA/CAE/NC/ND es identico, sin divergencias.

El PDF (`GET /facturas/{id}/pdf`), el ticket (`GET /facturas/{id}/ticket`)
y el recibo (`GET /facturas/{id}/recibo`) siguen viviendo en
`web/routers/facturas.py` sin tocar (descargas autenticadas por cookie,
la SPA los linkea directo). `POST /api/facturas/borrador-pdf` reimplementa
en JSON la logica de `POST /facturas/borrador-pdf` del router viejo
(genera un PDF sin guardar ni llamar a ARCA, para previsualizar antes de
emitir).

Divergencia real vs Contalibra (unica de este modulo, ver instrucciones de
la Etapa C): Restolibra necesita poder prefillear una factura desde una
Venta de POS ya cobrada (`?from_venta=<id>` en FacturaNueva.tsx). El
prefill en si (cliente + items) es trivial del lado del cliente -- el
frontend llama `GET /api/ventas/{id}` y mapea los campos, no hace falta un
endpoint nuevo para eso. Lo que SI requiere logica de servidor es vincular
la factura resultante a la venta de origen: `ventas.factura_id` existe en
el schema y `get_all_ventas`/`get_venta` ya devuelven `factura_display`
para pintar el link en Ventas.tsx/VentaDetalle.tsx (tabs "Sin facturar" /
"Facturadas", ya construidas en la Etapa B) -- pero el router Jinja2 viejo
(`factura_nueva_get`/`factura_nueva_post` en `web/routers/facturas.py`)
NUNCA llama a `db.vincular_venta_factura`, a pesar de que la funcion existe
en `libracore.db.ventas` y esta importada en `database.py`. Es un gap real
del flujo viejo (el prefill funciona, pero la venta nunca queda marcada
como facturada). Se resuelve aca: `POST /api/facturas` acepta `venta_id`
opcional y, si la venta existe, vincula despues de crear+autorizar la
factura -- ver `crear()`.
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

import config_manager
import database as db
import pdf_generator as pdf_gen
from web.api_auth import get_current_user_json, require_role_json
from web.helpers.arca_helper import get_next_numero_with_arca, solicitar_cae as _solicitar_cae
from web.helpers.email_helper import send_comprobante, smtp_configurado
from web.helpers.form_helper import calculate_totals

router = APIRouter(prefix="/api/facturas", tags=["facturas"])

_TIPOS_POR_CONDICION = {
    "Responsable Inscripto": [{"value": 1, "label": "Factura A"}, {"value": 6, "label": "Factura B"}],
    "IVA Exento": [{"value": 6, "label": "Factura B"}],
    "Monotributista": [{"value": 11, "label": "Factura C"}],
}
_TIPOS_DEFAULT = _TIPOS_POR_CONDICION["Monotributista"]

_TIPO_NC = {1: 3, 6: 8, 11: 13}
_TIPO_ND = {1: 2, 6: 7, 11: 12}
_TIPO_LABEL = {
    1: "Factura A", 6: "Factura B", 11: "Factura C",
    3: "Nota de Crédito A", 8: "Nota de Crédito B", 13: "Nota de Crédito C",
    2: "Nota de Débito A", 7: "Nota de Débito B", 12: "Nota de Débito C",
}

CONCEPTOS = [{"value": 1, "label": "Productos"}, {"value": 2, "label": "Servicios"}, {"value": 3, "label": "Productos y Servicios"}]

CONDICIONES_VENTA = [
    "Contado", "Tarjeta de Débito", "Tarjeta de Crédito", "Cuenta Corriente",
    "Cheque", "Transferencia Bancaria", "Otros medios de pago electrónico", "Otra",
]

IVA_CODES = {
    "Responsable Inscripto": 1, "IVA Responsable Inscripto": 1,
    "Monotributista": 6, "Responsable Monotributo": 6,
    "IVA Exento": 4, "Consumidor Final": 5, "No Alcanzado": 3, "IVA No Responsable": 3,
}

_PAGE_SIZE = 50


def _tipos_emisor():
    cfg = config_manager.load()
    cond = cfg.get("empresa_iva_condition", "Monotributista")
    return _TIPOS_POR_CONDICION.get(cond, _TIPOS_DEFAULT)


def _arca_punto_venta():
    configs = db.obtener_todas_arca_configs()
    return configs[0].get("punto_venta", 1) if configs else 1


class ItemPayload(BaseModel):
    description: str
    qty: float
    unit_price: float


class FacturaPayload(BaseModel):
    tipo: int
    punto_venta: int = 1
    concepto: int = 1
    condicion_venta: str = ""
    fecha: str
    observations: str = ""
    fch_serv_desde: str = ""
    fch_serv_hasta: str = ""
    fch_vto_pago: str = ""
    tax_rate: float = 0.21
    client_id: int | None = None
    client_name: str = ""
    client_cuit: str = ""
    client_address: str = ""
    client_iva: str = ""
    items: list[ItemPayload]
    # Solo Restolibra: id de la Venta (POS) de origen cuando la factura se
    # emite via "Generar factura" desde una mesa/pedido ya cobrado -- ver
    # nota de modulo mas arriba y `crear()`.
    venta_id: int | None = None


class CobroPayload(BaseModel):
    fecha: str = ""
    caja_id: int | None = None
    pagos: list[dict]  # [{medio_id, monto, referencia}]


class EmailPayload(BaseModel):
    email: str


def _resolve_cliente(payload: FacturaPayload) -> dict:
    if payload.client_id:
        c = db.get_client(payload.client_id)
        if c:
            return {
                "client_name": c["name"], "client_cuit": c.get("cuit_dni", ""),
                "client_address": c.get("address", ""), "client_iva": c.get("iva_condition", ""),
            }
    return {
        "client_name": payload.client_name.strip(), "client_cuit": payload.client_cuit.strip(),
        "client_address": payload.client_address.strip(), "client_iva": payload.client_iva,
    }


def _detalle(factura: dict) -> dict:
    from pdf_generator import _CONCEPTO_LABELS, _IVA_LABELS, _TIPO_LABELS

    es_factura = factura["tipo"] in (1, 6, 11)
    ncs = db.get_nc_de_factura(factura["tipo"], factura["punto_venta"], factura["numero"]) if es_factura else []
    nds = db.get_nd_de_factura(factura["tipo"], factura["punto_venta"], factura["numero"]) if es_factura else []

    factura_original = None
    if factura.get("cbte_asoc_tipo") and factura.get("cbte_asoc_nro"):
        factura_original = db.get_factura_por_tipo_pv_nro(
            factura["cbte_asoc_tipo"], factura["cbte_asoc_pv"], factura["cbte_asoc_nro"],
        )

    cobros = db.get_cobros_factura(factura["id"]) if es_factura else []
    total_cobrado = sum(c["monto"] for c in cobros)
    pendiente = max(0.0, round(factura["total"] - total_cobrado, 2)) if es_factura else 0.0

    cliente_email = ""
    cliente = db.get_client_by_cuit(factura.get("cliente_cuit", ""))
    if cliente:
        cliente_email = cliente.get("email", "")

    return {
        "factura": factura,
        "tipo_label": _TIPO_LABELS.get(factura["tipo"], "Documento"),
        "concepto_label": _CONCEPTO_LABELS.get(factura.get("concepto", 1), "Productos"),
        "iva_label": _IVA_LABELS.get(factura.get("cliente_iva_cond") or 0, ""),
        "notas_credito": ncs,
        "notas_debito": nds,
        "factura_original": factura_original,
        "cobros": cobros,
        "total_cobrado": total_cobrado,
        "pendiente": pendiente,
        "cliente_email": cliente_email,
    }


@router.get("/tipos")
def tipos():
    tipos_emisor = _tipos_emisor()
    return {
        "tipos": tipos_emisor,
        "conceptos": CONCEPTOS,
        "condiciones_venta": CONDICIONES_VENTA,
        "punto_venta": _arca_punto_venta(),
        "es_monotributista": len(tipos_emisor) == 1 and tipos_emisor[0]["value"] == 11,
    }


@router.get("")
def listar(q: str = "", vista: str = "facturas", desde: str = "", hasta: str = "", page: int = 1):
    offset = (page - 1) * _PAGE_SIZE
    result = db.get_facturas_filtradas(desde, hasta, q, vista, _PAGE_SIZE, offset)
    return {
        "items": result["items"],
        "total": result["total"],
        "total_pages": max(1, (result["total"] + _PAGE_SIZE - 1) // _PAGE_SIZE),
        "page": page,
    }


@router.post("/borrador-pdf")
async def borrador_pdf(payload: FacturaPayload):
    """Genera un PDF de borrador con los datos del formulario, sin guardar ni
    llamar a ARCA (paridad con POST /facturas/borrador-pdf del router viejo,
    ver web/routers/facturas.py -- misma logica, en JSON en vez de form-data)."""
    import os as _os
    import tempfile

    cliente = _resolve_cliente(payload)
    items = [
        {"description": i.description.strip(), "qty": i.qty, "unit_price": i.unit_price, "subtotal": round(i.qty * i.unit_price, 2)}
        for i in payload.items if i.description.strip()
    ]
    if not items:
        items = [{"description": "Ejemplo de servicio", "qty": 1, "unit_price": 1000.0, "subtotal": 1000.0}]

    tax_rate = 0.0 if payload.tipo == 11 else payload.tax_rate
    totals = calculate_totals(items, tax_rate)
    iva_code = IVA_CODES.get(cliente["client_iva"], 0)

    factura_draft = {
        "id": 0, "tipo": payload.tipo, "punto_venta": payload.punto_venta, "numero": 0,
        "fecha": payload.fecha, "cliente_cuit": cliente["client_cuit"],
        "cliente_razon": cliente["client_name"] or "BORRADOR",
        "cliente_iva_cond": iva_code, "cliente_domicilio": cliente["client_address"],
        "items": items, "subtotal": totals["subtotal"], "iva_amount": totals["iva_amount"],
        "total": totals["total"], "concepto": payload.concepto,
        "observaciones": payload.observations.strip(), "condicion_venta": payload.condicion_venta,
        "fch_serv_desde": payload.fch_serv_desde, "fch_serv_hasta": payload.fch_serv_hasta,
        "fch_vto_pago": payload.fch_vto_pago, "cae": "", "cae_vto": "",
    }

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    try:
        pdf_gen.generate_pdf_factura(factura_draft, output_dir=_os.path.dirname(tmp.name))
        pv = str(payload.punto_venta).zfill(4)
        pdf_path = _os.path.join(_os.path.dirname(tmp.name), f"factura_{pv}_00000000.pdf")
        if not _os.path.exists(pdf_path):
            pdf_path = tmp.name
        with open(pdf_path, "rb") as f:
            content = f.read()
        if pdf_path != tmp.name and _os.path.exists(pdf_path):
            _os.unlink(pdf_path)
    except Exception as e:
        raise HTTPException(500, f"Error generando borrador: {e}")
    finally:
        if _os.path.exists(tmp.name):
            _os.unlink(tmp.name)

    return Response(content, media_type="application/pdf",
                     headers={"Content-Disposition": 'inline; filename="borrador.pdf"'})


@router.post("")
async def crear(payload: FacturaPayload, user: dict = Depends(get_current_user_json)):
    cliente = _resolve_cliente(payload)
    if not cliente["client_name"]:
        raise HTTPException(422, "El nombre/razón social del cliente es requerido.")

    items = [
        {"description": i.description.strip(), "qty": i.qty, "unit_price": i.unit_price, "subtotal": round(i.qty * i.unit_price, 2)}
        for i in payload.items if i.description.strip()
    ]
    if not items:
        raise HTTPException(422, "Debe agregar al menos un ítem válido.")

    tax_rate = 0.0 if payload.tipo == 11 else payload.tax_rate
    totals = calculate_totals(items, tax_rate)
    iva_code = IVA_CODES.get(cliente["client_iva"], 0)

    numero, ta, arca = await get_next_numero_with_arca(payload.punto_venta, payload.tipo)

    factura_id = db.create_factura(
        tipo=payload.tipo, punto_venta=payload.punto_venta, numero=numero,
        fecha=payload.fecha, cliente_cuit=cliente["client_cuit"], cliente_razon=cliente["client_name"],
        cliente_iva_cond=iva_code, items=items, subtotal=totals["subtotal"],
        iva_amount=totals["iva_amount"], total=totals["total"], concepto=payload.concepto,
        observaciones=payload.observations.strip(), cliente_domicilio=cliente["client_address"],
        fch_serv_desde=payload.fch_serv_desde, fch_serv_hasta=payload.fch_serv_hasta,
        fch_vto_pago=payload.fch_vto_pago, condicion_venta=payload.condicion_venta, usuario_id=user["id"],
    )
    factura = db.get_factura(factura_id)
    factura = await _solicitar_cae(factura_id, factura, ta, arca)

    pdf_path = pdf_gen.generate_pdf_factura(factura)
    db.update_factura_pdf_path(factura_id, pdf_path)

    if payload.condicion_venta == "Cuenta Corriente":
        pv_str = str(payload.punto_venta).zfill(4)
        num_str = str(numero).zfill(8)
        tipo_label = {1: "Factura A", 6: "Factura B", 11: "Factura C"}.get(payload.tipo, "Factura")
        db.create_caja_movimiento(
            fecha=payload.fecha, tipo="ingreso",
            concepto=f"Factura {tipo_label} {pv_str}-{num_str} — {cliente['client_name']}",
            monto=totals["total"], referencia="", factura_id=factura_id,
            medio_pago="Cuenta Corriente", usuario_id=user["id"],
        )

    # Factura emitida desde una Venta de POS (?from_venta= en FacturaNueva.tsx)
    # -- vincula para que Ventas.tsx/VentaDetalle.tsx dejen de mostrarla como
    # "Sin facturar" (ver nota de modulo). Si la venta no existe (id invalido
    # o ya se borró), no rompe la emisión ya confirmada por ARCA -- se ignora.
    if payload.venta_id and db.get_venta(payload.venta_id):
        db.vincular_venta_factura(payload.venta_id, factura_id)

    return db.get_factura(factura_id)


@router.get("/{factura_id}")
def detalle(factura_id: int):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404, "Factura no encontrada")
    return _detalle(factura)


@router.post("/{factura_id}/autorizar")
async def autorizar(factura_id: int):
    """Reintenta obtener CAE para una factura pendiente."""
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404, "Factura no encontrada")
    if factura.get("cae"):
        return _detalle(factura)

    arca_cfg = db.obtener_todas_arca_configs()
    arca = arca_cfg[0] if arca_cfg else None
    if not arca or not arca.get("certificado_path") or not arca.get("clave_path"):
        raise HTTPException(400, "ARCA no está configurado. Cargá los certificados en Configuración.")

    import arca_wsaa
    import arca_wsfe
    cert_path, clave_path = config_manager.resolve_cert_paths(arca["certificado_path"], arca["clave_path"])
    try:
        ta = await arca_wsaa.autenticar(cert_path, clave_path, arca["ambiente"])
        cae_data = await arca_wsfe.solicitar_cae(factura, arca["cuit"], ta["token"], ta["sign"], arca["ambiente"])
        db.update_factura_cae(factura_id, cae_data["cae"], cae_data["cae_vto"])
        factura = db.get_factura(factura_id)
        pdf_path = pdf_gen.generate_pdf_factura(factura)
        db.update_factura_pdf_path(factura_id, pdf_path)
        return _detalle(factura)
    except Exception as e:
        raise HTTPException(502, str(e))


@router.post("/{factura_id}/cobrar")
def cobrar(factura_id: int, payload: CobroPayload, user: dict = Depends(get_current_user_json)):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404, "Factura no encontrada")

    fecha = payload.fecha or datetime.date.today().isoformat()
    from pdf_generator import _TIPO_LABELS
    tipo_label = _TIPO_LABELS.get(factura["tipo"], "Factura")
    pv = str(factura["punto_venta"]).zfill(4)
    num = str(factura["numero"]).zfill(8)
    concepto = f"Cobro {tipo_label} {pv}-{num} — {factura['cliente_razon']}"

    total_cobrado_ahora = 0.0
    for pago in payload.pagos:
        monto = float(pago.get("monto") or 0)
        if monto <= 0:
            continue
        db.create_caja_movimiento(
            fecha=fecha, tipo="ingreso", concepto=concepto, monto=monto,
            referencia=str(pago.get("referencia", "")).strip(), factura_id=factura_id,
            caja_id=payload.caja_id, medio_pago=pago.get("medio_id", ""), usuario_id=user["id"],
        )
        total_cobrado_ahora += monto

    if total_cobrado_ahora > 0 and factura.get("condicion_venta") == "Cuenta Corriente":
        cliente_cc = db.get_client_by_cuit(factura.get("cliente_cuit"))
        if cliente_cc:
            db.create_cc_pago(
                cliente_id=cliente_cc["id"], monto=total_cobrado_ahora, fecha=fecha,
                concepto=f"Cobro {tipo_label} {pv}-{num}", referencia="", medio_pago="",
                caja_id=payload.caja_id, usuario_id=user["id"],
            )

    return _detalle(db.get_factura(factura_id))


@router.post("/{factura_id}/enviar-email")
def enviar_email(factura_id: int, payload: EmailPayload):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404, "Factura no encontrada")
    if not smtp_configurado():
        raise HTTPException(400, "Configurá el servidor SMTP en Configuración → Integraciones.")
    if not payload.email.strip():
        raise HTTPException(422, "Ingresá una dirección de email.")

    import os
    from pdf_generator import _TIPO_LABELS
    pdf_path = factura.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        pdf_path = pdf_gen.generate_pdf_factura(factura)
    tipo_label = _TIPO_LABELS.get(factura["tipo"], "Comprobante")
    pv = str(factura["punto_venta"]).zfill(4)
    num = str(factura["numero"]).zfill(8)
    doc_label = f"{tipo_label} {pv}-{num}"

    try:
        send_comprobante(
            to_email=payload.email.strip(), to_name=factura["cliente_razon"],
            pdf_path=pdf_path, factura_label=doc_label, total=factura["total"],
        )
    except Exception as e:
        raise HTTPException(502, f"Error al enviar: {e}")
    return {"ok": True}


@router.delete("/{factura_id}", dependencies=[Depends(require_role_json("admin"))])
def eliminar(factura_id: int):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404, "Factura no encontrada")
    if factura.get("cae") and factura["cae"] != "PENDIENTE":
        raise HTTPException(400, "No se puede eliminar una factura con CAE ya emitido por ARCA — use nota de crédito/débito.")
    db.delete_factura(factura_id)
    return {"ok": True}


@router.post("/{factura_id}/nota-credito", dependencies=[Depends(require_role_json("admin"))])
async def nota_credito(factura_id: int, user: dict = Depends(get_current_user_json)):
    orig = db.get_factura(factura_id)
    if not orig:
        raise HTTPException(404, "Factura no encontrada")
    nc_tipo = _TIPO_NC.get(orig["tipo"])
    if not nc_tipo:
        raise HTTPException(400, "Tipo de comprobante no admite nota de crédito")
    nota_id = await _crear_nota(orig, nc_tipo, "Anula", user["id"])
    if orig.get("condicion_venta") == "Cuenta Corriente":
        cliente = db.get_client_by_cuit(orig.get("cliente_cuit", ""))
        if cliente:
            db.create_cc_pago(
                cliente_id=cliente["id"], monto=orig["total"], fecha=datetime.date.today().isoformat(),
                concepto=f"NC {str(orig['punto_venta']).zfill(4)}-{str(orig['numero']).zfill(8)} "
                         f"(anula {_TIPO_LABEL.get(orig['tipo'], 'comprobante')} "
                         f"{str(orig['punto_venta']).zfill(4)}-{str(orig['numero']).zfill(8)})",
                referencia="", medio_pago="Cuenta Corriente", caja_id=None, usuario_id=user["id"],
            )
    return db.get_factura(nota_id)


@router.post("/{factura_id}/nota-debito", dependencies=[Depends(require_role_json("admin"))])
async def nota_debito(factura_id: int, user: dict = Depends(get_current_user_json)):
    orig = db.get_factura(factura_id)
    if not orig:
        raise HTTPException(404, "Factura no encontrada")
    nd_tipo = _TIPO_ND.get(orig["tipo"])
    if not nd_tipo:
        raise HTTPException(400, "Tipo de comprobante no admite nota de débito")
    nota_id = await _crear_nota(orig, nd_tipo, "Referencia", user["id"])
    return db.get_factura(nota_id)


async def _crear_nota(orig: dict, nuevo_tipo: int, obs_prefijo: str, usuario_id: int) -> int:
    fecha_hoy = datetime.date.today().isoformat()
    punto_venta = orig["punto_venta"]
    numero, ta, arca = await get_next_numero_with_arca(punto_venta, nuevo_tipo)

    nota_id = db.create_factura(
        tipo=nuevo_tipo, punto_venta=punto_venta, numero=numero, fecha=fecha_hoy,
        cliente_cuit=orig["cliente_cuit"], cliente_razon=orig["cliente_razon"],
        cliente_iva_cond=orig.get("cliente_iva_cond") or 0, items=orig["items"],
        subtotal=orig["subtotal"], iva_amount=orig["iva_amount"], total=orig["total"],
        concepto=orig.get("concepto", 1),
        observaciones=f"{obs_prefijo} {_TIPO_LABEL.get(orig['tipo'], 'comprobante')} "
                      f"{str(orig['punto_venta']).zfill(4)}-{str(orig['numero']).zfill(8)}",
        cliente_domicilio=orig.get("cliente_domicilio", ""),
        fch_serv_desde=orig.get("fch_serv_desde", ""), fch_serv_hasta=orig.get("fch_serv_hasta", ""),
        fch_vto_pago=fecha_hoy, cbte_asoc_tipo=orig["tipo"], cbte_asoc_pv=orig["punto_venta"],
        cbte_asoc_nro=orig["numero"], usuario_id=usuario_id,
    )
    nota = db.get_factura(nota_id)
    nota = await _solicitar_cae(nota_id, nota, ta, arca)
    pdf_path = pdf_gen.generate_pdf_factura(nota)
    db.update_factura_pdf_path(nota_id, pdf_path)
    return nota_id
