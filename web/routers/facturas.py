import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse, Response
from typing import Annotated

import datetime

import database as db
import pdf_generator as pdf_gen
import arca_wsaa
import arca_wsfe
import config_manager
import email_sender
from web.auth import require_auth
from web.templates_config import templates
from web.helpers.auth_helper import get_current_user_id
from web.helpers.form_helper import extract_client_from_form, extract_items_from_form, calculate_totals
from web.helpers.arca_helper import get_next_numero_with_arca, solicitar_cae as _solicitar_cae
from web.helpers.email_helper import send_comprobante, smtp_configurado

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]

_TIPOS_POR_CONDICION = {
    "Responsable Inscripto": [
        {"value": 1, "label": "Factura A"},
        {"value": 6, "label": "Factura B"},
    ],
    "IVA Exento": [
        {"value": 6, "label": "Factura B"},
    ],
    "Monotributista": [
        {"value": 11, "label": "Factura C"},
    ],
}
_TIPOS_DEFAULT = _TIPOS_POR_CONDICION["Monotributista"]

# Factura → tipo de Nota de Crédito / Débito correspondiente
_TIPO_NC = {1: 3,  6: 8,  11: 13}
_TIPO_ND = {1: 2,  6: 7,  11: 12}
_TIPO_LABEL = {
    1: "Factura A",        6: "Factura B",        11: "Factura C",
    3: "Nota de Crédito A", 8: "Nota de Crédito B", 13: "Nota de Crédito C",
    2: "Nota de Débito A",  7: "Nota de Débito B",  12: "Nota de Débito C",
}


def _tipos_emisor():
    cfg = config_manager.load()
    cond = cfg.get("empresa_iva_condition", "Monotributista")
    return _TIPOS_POR_CONDICION.get(cond, _TIPOS_DEFAULT)


CONCEPTOS = [
    {"value": 1, "label": "Productos"},
    {"value": 2, "label": "Servicios"},
    {"value": 3, "label": "Productos y Servicios"},
]

CONDICIONES_VENTA = [
    "Contado",
    "Tarjeta de Débito",
    "Tarjeta de Crédito",
    "Cuenta Corriente",
    "Cheque",
    "Transferencia Bancaria",
    "Otros medios de pago electrónico",
    "Otra",
]

IVA_CODES = {
    "Responsable Inscripto": 1,
    "IVA Responsable Inscripto": 1,
    "Monotributista": 6,
    "Responsable Monotributo": 6,
    "IVA Exento": 4,
    "Consumidor Final": 5,
    "No Alcanzado": 3,
    "IVA No Responsable": 3,
}


def _arca_punto_venta():
    configs = db.obtener_todas_arca_configs()
    return configs[0].get("punto_venta", 1) if configs else 1


_PAGE_SIZE = 50


@router.get("/facturas")
def facturas_list(request: Request, user: Auth,
                  q: str = "", vista: str = "facturas",
                  desde: str = "", hasta: str = "", page: int = 1):
    offset = (page - 1) * _PAGE_SIZE
    result = db.get_facturas_filtradas(desde, hasta, q, vista, _PAGE_SIZE, offset)
    total_pages = max(1, (result["total"] + _PAGE_SIZE - 1) // _PAGE_SIZE)
    return templates.TemplateResponse(request, "facturas/list.html", {
        "facturas":    result["items"],
        "q":           q,
        "vista":       vista,
        "desde":       desde,
        "hasta":       hasta,
        "page":        page,
        "total_pages": total_pages,
        "total_items": result["total"],
        "active":      "facturas",
    })


@router.post("/facturas/borrador-pdf")
async def factura_borrador_pdf(request: Request, user: Auth):
    """Genera un PDF de borrador con los datos del formulario, sin guardar ni llamar a ARCA."""
    import tempfile, os as _os
    form = await request.form()
    try:
        tipo        = int(form.get("tipo", 11))
        punto_venta = int(form.get("punto_venta", 1) or 1)
        concepto    = int(form.get("concepto", 2))
        fecha_str       = str(form.get("fecha", datetime.date.today().isoformat())).strip()
        observations    = str(form.get("observations", "")).strip()
        condicion_venta = str(form.get("condicion_venta", "")).strip()
        fch_serv_desde  = str(form.get("fch_serv_desde", "")).strip()
        fch_serv_hasta  = str(form.get("fch_serv_hasta", "")).strip()
        fch_vto_pago    = str(form.get("fch_vto_pago", "")).strip()
        tax_rate    = 0.0 if tipo == 11 else float(form.get("tax_rate", "0.21") or "0.21")

        cliente = extract_client_from_form(form)
        client_id      = cliente["client_id"]
        client_name    = cliente["client_name"]
        client_cuit    = cliente["client_cuit"]
        client_address = cliente["client_address"]
        client_iva     = cliente["client_iva"]

        items = extract_items_from_form(form)
        if not items:
            items = [{"description": "Ejemplo de servicio", "qty": 1, "unit_price": 1000.0, "subtotal": 1000.0}]

        totals     = calculate_totals(items, tax_rate)
        subtotal   = totals["subtotal"]
        iva_amount = totals["iva_amount"]
        total      = totals["total"]

        factura_draft = {
            "id": 0,
            "tipo": tipo,
            "punto_venta": punto_venta,
            "numero": 0,
            "fecha": fecha_str,
            "cliente_cuit": client_cuit,
            "cliente_razon": client_name or "BORRADOR",
            "cliente_iva_cond": IVA_CODES.get(client_iva, 0),
            "cliente_domicilio": client_address,
            "items": items,
            "subtotal": subtotal,
            "iva_amount": iva_amount,
            "total": total,
            "concepto": concepto,
            "observaciones": observations,
            "condicion_venta": condicion_venta,
            "fch_serv_desde": fch_serv_desde,
            "fch_serv_hasta": fch_serv_hasta,
            "fch_vto_pago": fch_vto_pago,
            "cae": "",
            "cae_vto": "",
        }

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.close()
        pdf_gen.generate_pdf_factura(factura_draft, output_dir=_os.path.dirname(tmp.name))
        # generate_pdf_factura usa punto_venta y numero para el nombre, entonces lo buscamos
        pv  = str(punto_venta).zfill(4)
        num = "00000000"
        pdf_path = _os.path.join(_os.path.dirname(tmp.name), f"factura_{pv}_{num}.pdf")
        if not _os.path.exists(pdf_path):
            pdf_path = tmp.name  # fallback
        with open(pdf_path, "rb") as f:
            content = f.read()
        try:
            _os.unlink(pdf_path)
            _os.unlink(tmp.name)
        except Exception:
            pass
        return Response(content, media_type="application/pdf",
                        headers={"Content-Disposition": 'inline; filename="borrador.pdf"'})
    except Exception as e:
        return Response(f"Error generando borrador: {e}", status_code=500)


@router.get("/facturas/nueva")
def factura_nueva_get(request: Request, user: Auth, from_presupuesto: int = 0, from_factura: int = 0, from_venta: int = 0):
    tipos = _tipos_emisor()
    es_monotributista = len(tipos) == 1 and tipos[0]["value"] == 11
    prefill = None
    if from_presupuesto:
        pres = db.get_presupuesto(from_presupuesto)
        if pres:
            client_iva = ""
            if pres.get("client_id"):
                c = db.get_client(pres["client_id"])
                if c:
                    client_iva = c.get("iva_condition", "")
            prefill = {
                "client_id":      pres.get("client_id") or "",
                "client_name":    pres["client_name"],
                "client_cuit":    pres.get("client_cuit", ""),
                "client_address": pres.get("client_address", ""),
                "client_iva":     client_iva,
                "concepto":       2,
                "observations":   pres.get("observations", ""),
                "items":          pres["items"],
            }
    elif from_factura:
        orig = db.get_factura(from_factura)
        if orig:
            matched_client = None
            if orig.get("cliente_cuit"):
                matched_client = next(
                    (c for c in db.get_all_clients() if c.get("cuit_dni") == orig["cliente_cuit"]),
                    None,
                )
            prefill = {
                "client_id":       matched_client["id"] if matched_client else "",
                "client_name":     orig.get("cliente_razon", ""),
                "client_cuit":     orig.get("cliente_cuit", ""),
                "client_address":  orig.get("cliente_domicilio", ""),
                "client_iva":      matched_client.get("iva_condition", "") if matched_client else "",
                "concepto":        orig.get("concepto", 1),
                "observations":    orig.get("observaciones", ""),
                "items":           orig["items"],
                "tipo":            orig["tipo"],
                "punto_venta":     orig["punto_venta"],
                "condicion_venta": orig.get("condicion_venta", ""),
                "fch_serv_desde":  orig.get("fch_serv_desde", ""),
                "fch_serv_hasta":  orig.get("fch_serv_hasta", ""),
                "fch_vto_pago":    orig.get("fch_vto_pago", ""),
            }
    elif from_venta:
        v = db.get_venta(from_venta)
        if v:
            client_iva = client_cuit = client_address = ""
            client_id = v.get("cliente_id") or ""
            if client_id:
                c = db.get_client(client_id)
                if c:
                    client_iva     = c.get("iva_condition", "")
                    client_cuit    = c.get("cuit_dni", "")
                    client_address = c.get("address", "")
            # Los ítems de venta usan nombre/precio; el form de factura espera
            # description/qty/unit_price (ver extract_items_from_form).
            items = [
                {"description": it.get("nombre", ""),
                 "qty":         it.get("qty", 1),
                 "unit_price":  it.get("precio", 0)}
                for it in (v.get("items") or [])
            ]
            prefill = {
                "client_id":      client_id,
                "client_name":    v.get("cliente_nombre", "") or "",
                "client_cuit":    client_cuit,
                "client_address": client_address,
                "client_iva":     client_iva,
                "concepto":       1,
                "observations":   v.get("observaciones", ""),
                "items":          items,
            }
    return templates.TemplateResponse(request, "facturas/form.html", {
        "clientes":            db.get_all_clients(),
        "tipos":               tipos,
        "conceptos":           CONCEPTOS,
        "condiciones_venta":   CONDICIONES_VENTA,
        "punto_venta":         _arca_punto_venta(),
        "active":              "facturas",
        "factura":             None,
        "error":               None,
        "es_monotributista":   es_monotributista,
        "prefill":             prefill,
    })


@router.post("/facturas/nueva")
async def factura_nueva_post(request: Request, user: Auth):
    form = await request.form()
    clientes = db.get_all_clients()

    try:
        tipo        = int(form.get("tipo", 6))
        punto_venta = int(form.get("punto_venta", 1) or 1)
        concepto         = int(form.get("concepto", 1))
        condicion_venta  = str(form.get("condicion_venta", "")).strip()
        fecha_str        = str(form.get("fecha", "")).strip()
        observations     = str(form.get("observations", "")).strip()
        fch_serv_desde  = str(form.get("fch_serv_desde", "")).strip()
        fch_serv_hasta  = str(form.get("fch_serv_hasta", "")).strip()
        fch_vto_pago    = str(form.get("fch_vto_pago",   "")).strip()
        # Factura C (monotributista) nunca discrimina IVA
        tax_rate    = 0.0 if tipo == 11 else float(form.get("tax_rate", "0.21"))

        cliente = extract_client_from_form(form)
        client_id      = cliente["client_id"]
        client_name    = cliente["client_name"]
        client_cuit    = cliente["client_cuit"]
        client_address = cliente["client_address"]
        client_iva     = cliente["client_iva"]

        if not client_name:
            raise ValueError("El nombre/razón social del cliente es requerido.")

        items = extract_items_from_form(form)
        if not items:
            raise ValueError("Debe agregar al menos un ítem válido.")

        totals     = calculate_totals(items, tax_rate)
        subtotal   = totals["subtotal"]
        iva_amount = totals["iva_amount"]
        total      = totals["total"]
        iva_code   = IVA_CODES.get(client_iva, 0)

        numero, ta, arca = await get_next_numero_with_arca(punto_venta, tipo)

        uid = get_current_user_id(user)
        factura_id = db.create_factura(
            tipo=tipo, punto_venta=punto_venta, numero=numero,
            fecha=fecha_str, cliente_cuit=client_cuit,
            cliente_razon=client_name, cliente_iva_cond=iva_code,
            items=items, subtotal=subtotal, iva_amount=iva_amount,
            total=total, concepto=concepto, observaciones=observations,
            cliente_domicilio=client_address,
            fch_serv_desde=fch_serv_desde,
            fch_serv_hasta=fch_serv_hasta,
            fch_vto_pago=fch_vto_pago,
            condicion_venta=condicion_venta,
            usuario_id=uid,
        )
        factura = db.get_factura(factura_id)

        factura = await _solicitar_cae(factura_id, factura, ta, arca)

        pdf_path = pdf_gen.generate_pdf_factura(factura)
        db.update_factura_pdf_path(factura_id, pdf_path)

        # Si la condición de venta es Cuenta Corriente, registrar movimiento en caja
        if condicion_venta == "Cuenta Corriente":
            pv_str = str(punto_venta).zfill(4)
            num_str = str(numero).zfill(8)
            tipo_label = {1: "Factura A", 6: "Factura B", 11: "Factura C"}.get(tipo, "Factura")
            db.create_caja_movimiento(
                fecha=fecha_str,
                tipo="ingreso",
                concepto=f"Factura {tipo_label} {pv_str}-{num_str} — {client_name}",
                monto=total,
                referencia="",
                factura_id=factura_id,
                medio_pago="Cuenta Corriente",
                usuario_id=uid,
            )

        return RedirectResponse(f"/facturas/{factura_id}", status_code=303)

    except Exception as e:
        tipos = _tipos_emisor()
        return templates.TemplateResponse(request, "facturas/form.html", {
            "clientes": clientes, "tipos": tipos, "conceptos": CONCEPTOS,
            "condiciones_venta": CONDICIONES_VENTA,
            "punto_venta": _arca_punto_venta(),
            "active": "facturas", "factura": None, "error": str(e),
            "es_monotributista": len(tipos) == 1 and tipos[0]["value"] == 11,
        }, status_code=422)


def _detail_ctx(factura: dict, error: str = "") -> dict:
    from pdf_generator import _TIPO_LABELS, _CONCEPTO_LABELS, _IVA_LABELS

    es_factura = factura["tipo"] in (1, 6, 11)

    # Notas de crédito y débito que referencian esta factura
    ncs = db.get_nc_de_factura(factura["tipo"], factura["punto_venta"], factura["numero"]) if es_factura else []
    nds = db.get_nd_de_factura(factura["tipo"], factura["punto_venta"], factura["numero"]) if es_factura else []

    # Factura original que esta NC/ND referencia
    factura_original = None
    if factura.get("cbte_asoc_tipo") and factura.get("cbte_asoc_nro"):
        factura_original = db.get_factura_por_tipo_pv_nro(
            factura["cbte_asoc_tipo"], factura["cbte_asoc_pv"], factura["cbte_asoc_nro"]
        )

    cobros = db.get_cobros_factura(factura["id"]) if es_factura else []
    total_cobrado = sum(c["monto"] for c in cobros)
    pendiente     = max(0.0, round(factura["total"] - total_cobrado, 2)) if es_factura else 0.0

    # Intentar obtener email del cliente para pre-llenar el modal
    cliente_email = ""
    if factura.get("client_id"):
        c = db.get_client(factura["client_id"])
        if c:
            cliente_email = c.get("email", "")

    cajas = db.get_all_cajas() if es_factura else []

    return {
        "factura":          factura,
        "tipo_label":       _TIPO_LABELS.get(factura["tipo"], "Documento"),
        "concepto_label":   _CONCEPTO_LABELS.get(factura.get("concepto", 1), "Productos"),
        "iva_label":        _IVA_LABELS.get(factura.get("cliente_iva_cond") or 0, ""),
        "active":           "facturas",
        "arca_error":       error,
        "notas_credito":    ncs,
        "notas_debito":     nds,
        "factura_original": factura_original,
        "tipo_labels":      _TIPO_LABELS,
        "cobros":           cobros,
        "cobro":            cobros[-1] if cobros else None,
        "total_cobrado":    total_cobrado,
        "pendiente":        pendiente,
        "cajas":            cajas,
        "medio_labels":     db.MEDIOS_PAGO_LABELS,
        "cliente_email":    cliente_email,
        "email_ok":         None,
        "email_error":      None,
    }


@router.get("/facturas/{factura_id}")
def factura_detail(request: Request, factura_id: int, user: Auth):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "facturas/detail.html",
                                      _detail_ctx(factura))


@router.post("/facturas/{factura_id}/autorizar")
async def factura_autorizar(request: Request, factura_id: int, user: Auth):
    """Reintenta obtener CAE para una factura pendiente."""
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)

    if factura.get("cae"):
        return RedirectResponse(f"/facturas/{factura_id}", status_code=303)

    arca_cfg = db.obtener_todas_arca_configs()
    arca     = arca_cfg[0] if arca_cfg else None
    if not arca or not arca.get("certificado_path") or not arca.get("clave_path"):
        return templates.TemplateResponse(request, "facturas/detail.html",
            {**_detail_ctx(factura),
             "arca_error": "ARCA no está configurado. Cargá los certificados en Configuración."})

    cert_path, clave_path = config_manager.resolve_cert_paths(
        arca["certificado_path"], arca["clave_path"]
    )
    try:
        ta = await arca_wsaa.autenticar(
            cert_path, clave_path, arca["ambiente"]
        )
        cae_data = await arca_wsfe.solicitar_cae(
            factura, arca["cuit"], ta["token"], ta["sign"], arca["ambiente"]
        )
        db.update_factura_cae(factura_id, cae_data["cae"], cae_data["cae_vto"])
        factura = db.get_factura(factura_id)
        pdf_path = pdf_gen.generate_pdf_factura(factura)
        db.update_factura_pdf_path(factura_id, pdf_path)
        return RedirectResponse(f"/facturas/{factura_id}", status_code=303)

    except Exception as e:
        factura = db.get_factura(factura_id)
        return templates.TemplateResponse(request, "facturas/detail.html",
            {**_detail_ctx(factura), "arca_error": str(e)})


@router.get("/facturas/{factura_id}/pdf")
def factura_pdf(factura_id: int, user: Auth):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)
    pdf_path = pdf_gen.generate_pdf_factura(factura)
    db.update_factura_pdf_path(factura_id, pdf_path)
    pv  = str(factura["punto_venta"]).zfill(4)
    num = str(factura["numero"]).zfill(8)
    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"factura_{pv}_{num}.pdf")


@router.post("/facturas/{factura_id}/enviar-email")
async def factura_enviar_email(request: Request, factura_id: int, user: Auth):
    form    = await request.form()
    to_mail = str(form.get("email", "")).strip()
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)

    ctx = _detail_ctx(factura)

    if not smtp_configurado():
        return templates.TemplateResponse(request, "facturas/detail.html",
            {**ctx, "email_error": "Configurá el servidor SMTP en Configuración → Integraciones.",
             "email_ok": None})

    if not to_mail:
        return templates.TemplateResponse(request, "facturas/detail.html",
            {**ctx, "email_error": "Ingresá una dirección de email.", "email_ok": None})

    from pdf_generator import _TIPO_LABELS
    pdf_path   = factura.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        pdf_path = pdf_gen.generate_pdf_factura(factura)
    tipo_label = _TIPO_LABELS.get(factura["tipo"], "Comprobante")
    pv         = str(factura["punto_venta"]).zfill(4)
    num        = str(factura["numero"]).zfill(8)
    doc_label  = f"{tipo_label} {pv}-{num}"

    try:
        send_comprobante(to_email=to_mail, to_name=factura["cliente_razon"],
                         pdf_path=pdf_path, factura_label=doc_label, total=factura["total"])
        return templates.TemplateResponse(request, "facturas/detail.html",
            {**ctx, "email_ok": f"Email enviado a {to_mail}.", "email_error": None})
    except Exception as e:
        return templates.TemplateResponse(request, "facturas/detail.html",
            {**ctx, "email_error": f"Error al enviar: {e}", "email_ok": None})


@router.post("/facturas/{factura_id}/eliminar")
def factura_eliminar(factura_id: int, user: Auth):
    db.delete_factura(factura_id)
    return RedirectResponse("/facturas", status_code=303)


async def _crear_nota(orig: dict, nuevo_tipo: int, obs_prefijo: str, usuario_id=None) -> int:
    """Helper compartido para crear NC o ND a partir de una factura original."""
    import datetime
    fecha_hoy   = datetime.date.today().isoformat()
    punto_venta = orig["punto_venta"]

    numero, ta, arca = await get_next_numero_with_arca(punto_venta, nuevo_tipo)

    nota_id = db.create_factura(
        tipo=nuevo_tipo, punto_venta=punto_venta, numero=numero,
        fecha=fecha_hoy,
        cliente_cuit=orig["cliente_cuit"],
        cliente_razon=orig["cliente_razon"],
        cliente_iva_cond=orig.get("cliente_iva_cond") or 0,
        items=orig["items"],
        subtotal=orig["subtotal"],
        iva_amount=orig["iva_amount"],
        total=orig["total"],
        concepto=orig.get("concepto", 1),
        observaciones=f"{obs_prefijo} {_TIPO_LABEL.get(orig['tipo'], 'comprobante')} "
                      f"{str(orig['punto_venta']).zfill(4)}-{str(orig['numero']).zfill(8)}",
        cliente_domicilio=orig.get("cliente_domicilio", ""),
        fch_serv_desde=orig.get("fch_serv_desde", ""),
        fch_serv_hasta=orig.get("fch_serv_hasta", ""),
        fch_vto_pago=fecha_hoy,
        cbte_asoc_tipo=orig["tipo"],
        cbte_asoc_pv=orig["punto_venta"],
        cbte_asoc_nro=orig["numero"],
        usuario_id=usuario_id,
    )
    nota = db.get_factura(nota_id)
    nota = await _solicitar_cae(nota_id, nota, ta, arca)
    pdf_path = pdf_gen.generate_pdf_factura(nota)
    db.update_factura_pdf_path(nota_id, pdf_path)
    return nota_id


@router.get("/facturas/{factura_id}/nota-credito")
def nc_confirm_get(request: Request, factura_id: int, user: Auth):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)
    nc_tipo = _TIPO_NC.get(factura["tipo"])
    if not nc_tipo:
        raise HTTPException(400, "Este tipo de comprobante no admite nota de crédito")
    return templates.TemplateResponse(request, "facturas/nota_confirm.html", {
        **_detail_ctx(factura),
        "nota_tipo_label": _TIPO_LABEL[nc_tipo],
        "nota_url":        f"/facturas/{factura_id}/nota-credito",
        "nota_color":      "warning",
        "nota_icono":      "description",
    })


@router.post("/facturas/{factura_id}/nota-credito")
async def nc_crear(factura_id: int, user: Auth):
    orig = db.get_factura(factura_id)
    if not orig:
        raise HTTPException(404)
    nc_tipo = _TIPO_NC.get(orig["tipo"])
    if not nc_tipo:
        raise HTTPException(400, "Tipo de comprobante no admite nota de crédito")
    nota_id = await _crear_nota(orig, nc_tipo, "Anula", usuario_id=get_current_user_id(user))
    return RedirectResponse(f"/facturas/{nota_id}", status_code=303)


@router.get("/facturas/{factura_id}/nota-debito")
def nd_confirm_get(request: Request, factura_id: int, user: Auth):
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)
    nd_tipo = _TIPO_ND.get(factura["tipo"])
    if not nd_tipo:
        raise HTTPException(400, "Este tipo de comprobante no admite nota de débito")
    return templates.TemplateResponse(request, "facturas/nota_confirm.html", {
        **_detail_ctx(factura),
        "nota_tipo_label": _TIPO_LABEL[nd_tipo],
        "nota_url":        f"/facturas/{factura_id}/nota-debito",
        "nota_color":      "info",
        "nota_icono":      "post_add",
    })


@router.post("/facturas/{factura_id}/nota-debito")
async def nd_crear(factura_id: int, user: Auth):
    orig = db.get_factura(factura_id)
    if not orig:
        raise HTTPException(404)
    nd_tipo = _TIPO_ND.get(orig["tipo"])
    if not nd_tipo:
        raise HTTPException(400, "Tipo de comprobante no admite nota de débito")
    nota_id = await _crear_nota(orig, nd_tipo, "Referencia", usuario_id=get_current_user_id(user))
    return RedirectResponse(f"/facturas/{nota_id}", status_code=303)


@router.post("/facturas/{factura_id}/cobrar")
async def factura_cobrar(request: Request, factura_id: int, user: Auth):
    """Registra un cobro (total o parcial) de una factura."""
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)

    form = await request.form()
    caja_id_raw = form.get("caja_id", "")
    caja_id     = int(caja_id_raw) if caja_id_raw else None
    fecha       = str(form.get("fecha", datetime.date.today().isoformat())).strip()

    medio_ids = form.getlist("medio_id[]")
    montos    = form.getlist("monto_medio[]")
    refs      = form.getlist("ref_medio[]")

    from pdf_generator import _TIPO_LABELS
    tipo_label = _TIPO_LABELS.get(factura["tipo"], "Factura")
    pv  = str(factura["punto_venta"]).zfill(4)
    num = str(factura["numero"]).zfill(8)
    concepto = f"Cobro {tipo_label} {pv}-{num} — {factura['cliente_razon']}"
    uid = get_current_user_id(user)

    # Crear un movimiento de caja por cada medio con monto > 0
    pagos_registrados = 0
    total_cobrado_ahora = 0.0
    for medio_id, monto_s, ref in zip(medio_ids, montos, refs):
        try:
            monto = float(monto_s.replace(",", ".") or "0")
        except (ValueError, TypeError):
            monto = 0.0
        if monto <= 0:
            continue
        db.create_caja_movimiento(
            fecha=fecha, tipo="ingreso", concepto=concepto,
            monto=monto, referencia=ref.strip(),
            factura_id=factura_id, caja_id=caja_id,
            medio_pago=medio_id, usuario_id=uid,
        )
        pagos_registrados += 1
        total_cobrado_ahora += monto

    # Si la factura fue emitida a Cuenta Corriente, este cobro debe saldar
    # (total o parcialmente) la deuda del cliente en Cuenta Corriente —
    # sin este crédito, el saldo quedaba pendiente para siempre aunque la
    # factura ya estuviera cobrada.
    if total_cobrado_ahora > 0 and factura.get("condicion_venta") == "Cuenta Corriente":
        cliente_cc = db.get_client_by_cuit(factura.get("cliente_cuit"))
        if cliente_cc:
            db.create_cc_pago(
                cliente_id=cliente_cc["id"], monto=total_cobrado_ahora, fecha=fecha,
                concepto=f"Cobro {tipo_label} {pv}-{num}",
                referencia="", medio_pago="", caja_id=caja_id, usuario_id=uid,
            )

    return RedirectResponse(f"/facturas/{factura_id}", status_code=303)

@router.get("/facturas/{factura_id}/ticket")
def factura_ticket(factura_id: int, user: Auth):
    import ticket_generator
    from fastapi.responses import Response as _Resp
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)
    pdf_bytes = ticket_generator.generar_ticket_factura(factura)
    return _Resp(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="ticket_factura_{factura_id}.pdf"'},
    )


@router.get("/facturas/{factura_id}/recibo")
def factura_recibo(factura_id: int, user: Auth):
    from fastapi.responses import Response as _Resp
    factura = db.get_factura(factura_id)
    if not factura:
        raise HTTPException(404)
    cobros = db.get_cobros_factura(factura_id)
    if not cobros:
        raise HTTPException(404, detail="Esta factura no tiene cobros registrados.")
    pdf_bytes = pdf_gen.generate_pdf_recibo(factura, cobros)
    pv  = str(factura.get("punto_venta", 0)).zfill(4)
    num = str(factura.get("numero", 0)).zfill(8)
    return _Resp(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="recibo_{pv}_{num}.pdf"'},
    )
