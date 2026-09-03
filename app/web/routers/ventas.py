
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app import database as db
from app.web.auth import require_auth

router = APIRouter()
Auth = Annotated[str, Depends(require_auth)]

# Las paginas y acciones Jinja2 de este router (list/nueva/detail/anular/
# mp-qr/mp-status) se removieron en el corte de la migracion a React --
# ver wiki/entities/restolibra.md, Etapa D; ahora viven en
# web/api/ventas.py. `mp-qr`/`mp-status` (QR dinamico de MercadoPago) no
# se reimplementaron como JSON porque el flujo de cobro con QR quedo fuera
# de alcance de esta etapa (ver comentario en frontend/src/pages/
# VentaDetalle.tsx) -- no hay ningun boton ni fetch en la SPA que los
# invoque, asi que tambien se dieron de baja aca (a diferencia de lo que
# decia el docstring viejo de web/api/ventas.py). Solo quedan las
# descargas de ticket/recibo, que la SPA linkea directo.


@router.get("/ventas/{vid}/ticket")
def venta_ticket(vid: int, user: Auth):
    from app import ticket_generator
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
    from app import pdf_generator as pg
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
