"""Facturación de una venta del módulo Ventas — mostrador, mesa y QR MercadoPago.

Es el camino que faltaba **en este producto**. Hasta el 2026-08-31 Restolibra
era el único de los cuatro que cobran con QR que no emitía comprobante al
acreditarse el pago: `webhooks._cobro_de_venta_por_qr` devolvía `None` siempre,
con un comentario que decía que "este producto no emite comprobante". Contalibra
lo hace desde el 2026-08-19 (`mp_auto_facturar_ventas`), VentaLibra con
`mp_qr.auto_facturar_prendida()` y LibraClub con `mp_auto_facturar_reservas`.

> 🔴 **No era el ambiente de prueba.** El humano preguntó si la opción no
> aparecía por estar contra una cuenta de prueba de MercadoPago. No: el
> interruptor de la pantalla estaba apagado por configuración
> (`Config.tsx`, `autoFacturar: false`) y detrás no había nada que emitiera.

Dos diferencias con `mp_facturacion.generar_factura_mp` —el camino de la
bandeja—, y son la razón por la que esto no es una llamada a esa función:

1. **No registra movimiento de caja.** La venta ya registró uno por cada medio
   de pago acreditado, dentro de la misma transacción que la creó
   (`db_ventas.crear_venta_directa` y `db_cobro_pedido.cobrar_pedido`). Volver a
   registrarlo duplicaría el ingreso.
2. **No crea un cliente.** Una mesa sin cliente se factura a Consumidor Final
   sin persistir nada — un restaurante con 200 cubiertos por día llenaría
   `clients` en una semana. `generar_factura_mp` sí lo crea, porque ahí el
   pagador es un cliente real al que se le factura de nuevo el mes que viene.

Lo demás sí se comparte: la numeración y el CAE salen de `libracore`
(`arca_helper`), igual que el alta manual de `POST /api/facturas`.

## Lo que este archivo NO trajo de Contalibra

- **La alícuota por venta externa.** Allá una venta puede llegar de otro
  producto trayendo su propia alícuota (`ventas_origen_externo`, el caso de
  MedLibra con las prestaciones exentas). Acá esa tabla no existe: las ventas
  nacen en este producto, así que la alícuota es la del comprobante.
"""
import datetime
import logging

from libracore.db.caja import resolver_punto_venta

from app import config_manager
from app import database as db
from app import pdf_generator as pdf_gen
from app.web.helpers.arca_helper import (
    ambiente_de, get_next_numero_with_arca, solicitar_cae,
)

logger = logging.getLogger(__name__)

# Cliente sintético para la venta de mostrador sin cliente asignado. No se
# guarda en `clients`: viaja hasta `create_factura`, que snapshotea razón
# social, CUIT y domicilio en la propia factura.
CONSUMIDOR_FINAL = {
    "name": "Consumidor Final",
    "cuit_dni": "",
    "iva_condition": "Consumidor Final",
    "address": "",
    "email": "",
}

_IVA_CODES = {
    "Responsable Inscripto": 1, "IVA Responsable Inscripto": 1,
    "Monotributista": 6, "Responsable Monotributo": 6,
    "IVA Exento": 4, "Consumidor Final": 5,
    "No Alcanzado": 3, "IVA No Responsable": 3,
}

# Misma tasa por defecto que el formulario manual (`FacturaPayload.tax_rate`).
IVA_RATE_DEFAULT = 0.21

# Los ids son los de `libracore.medios_pago.ELEGIBLES`; los valores, los de
# `CONDICIONES_VENTA` en `libracore.facturas_router` (que es lo que acepta ARCA).
#
# 🔴 **La tarjeta va partida porque ARCA la parte.** Débito y crédito son dos
# condiciones de venta distintas en el comprobante, y por eso el vocabulario de
# la familia las distingue desde LibraCore v1.50.0 — un `tarjeta` a secas
# obligaba a adivinar o a caer en "Otra", que es declarar de menos.
#
# Los históricos (`tarjeta`, `mercado_pago`, `debito`, `credito`) entran acá
# también: **hay ventas viejas con esos medios**, y facturarlas después no puede
# caer en "Otra" sólo porque la grafía cambió.
_MEDIO_A_CONDICION = {
    "efectivo": "Contado",
    "transferencia": "Transferencia Bancaria",
    "tarjeta_debito": "Tarjeta de Débito",
    "tarjeta_credito": "Tarjeta de Crédito",
    "cheque": "Cheque",
    "mercadopago": "Otros medios de pago electrónico",
    "cuenta_dni": "Otros medios de pago electrónico",
    "billetera": "Otros medios de pago electrónico",
    "cuenta_corriente": "Cuenta Corriente",
    # Grafías históricas — ver `libracore.medios_pago.HISTORICOS`.
    "tarjeta": "Tarjeta de Crédito",
    "debito": "Tarjeta de Débito",
    "credito": "Tarjeta de Crédito",
    "mercado_pago": "Otros medios de pago electrónico",
    "qr": "Otros medios de pago electrónico",
}


class VentaNoFacturable(Exception):
    """La venta no está en condiciones de emitirse (inexistente, anulada o sin
    ítems)."""


def _tipo_comprobante(emisor_cond: str, cliente_cond: str) -> int:
    """A/B/C según el emisor, y A sólo si el cliente también es RI.

    Un Monotributista emite siempre C. Un Responsable Inscripto emite A a otro
    RI y B a todo lo demás — que en un salón es el caso normal.
    """
    if emisor_cond == "Monotributista":
        return 11
    if cliente_cond in ("Responsable Inscripto", "IVA Responsable Inscripto"):
        return 1
    return 6


def _armar_items(venta: dict, iva_rate: float) -> tuple[list, float, float, float]:
    """Convierte las líneas de la venta en líneas de factura.

    Los precios de una venta son finales (con IVA adentro); los de una factura
    son netos y el IVA se suma aparte. Con `iva_rate > 0` cada línea se
    desagrega, y el IVA del comprobante se calcula como la diferencia contra el
    total de la venta en vez de sumar los IVA línea por línea: así el total de
    la factura coincide **exacto** con lo que ya entró a la caja, sin arrastrar
    el redondeo de cada línea.
    """
    total_venta = round(float(venta["total"]), 2)
    divisor = 1 + iva_rate

    items = []
    for it in venta["items"]:
        neto_linea = round(float(it["subtotal"]) / divisor, 2)
        items.append({
            "description": it["nombre"],
            "qty": float(it["qty"]),
            "unit_price": round(float(it["precio"]) / divisor, 2),
            "subtotal": neto_linea,
        })

    descuento = round(float(venta.get("descuento") or 0), 2)
    if descuento:
        neto_desc = round(descuento / divisor, 2)
        items.append({
            "description": "Descuento",
            "qty": 1,
            "unit_price": -neto_desc,
            "subtotal": -neto_desc,
        })

    subtotal = round(sum(i["subtotal"] for i in items), 2)

    if iva_rate:
        iva_amount = round(total_venta - subtotal, 2)
        total = total_venta
    else:
        # Sin IVA discriminado las líneas ya son el total. Si no coincide con
        # el de la venta, manda la venta: es la plata que está en la caja.
        iva_amount = 0.0
        total = subtotal
        if abs(total - total_venta) > 0.01:
            logger.warning(
                "Venta %s: las líneas suman %.2f y la venta dice %.2f — "
                "se factura por las líneas",
                venta["id"], total, total_venta,
            )

    return items, subtotal, iva_amount, total


def _condicion_venta(venta: dict) -> str:
    pagos = venta.get("pagos") or []
    if len(pagos) == 1:
        return _MEDIO_A_CONDICION.get(pagos[0].get("medio", ""), "Otra")
    if len(pagos) > 1:
        return "Otra"
    return "Contado"


def _punto_venta(venta: dict) -> int:
    """El punto de venta de ARCA que le toca a esta venta.

    🔑 **El del mostrador donde se cobró, no el de la empresa.** La cadena es
    usuario → turno abierto → caja → punto de venta, y la resuelve LibraCore.
    Un cliente con dos mostradores necesita numeración fiscal separada, porque
    ARCA numera por (tipo, punto de venta).

    Se resuelve por el `usuario_id` **de la venta** y no por el de la sesión: la
    auto-factura la dispara el webhook de MercadoPago, donde no hay nadie
    logueado. Sin esto, un cobro por QR numeraría por el punto de venta de la
    empresa y el mismo cobro por efectivo por el del mostrador — dos series para
    la misma caja.

    Si esa caja no tiene uno propio —o el turno ya cerró— cae al de la empresa,
    que es como funcionan hoy todas las instancias.
    """
    propio = resolver_punto_venta(venta.get("usuario_id"))
    if propio:
        return propio
    configs = db.obtener_todas_arca_configs()
    return configs[0].get("punto_venta", 1) if configs else 1


async def facturar_venta(venta_id: int, *, usuario_id: int | None = None) -> dict:
    """Emite la factura de una venta, pide el CAE, genera el PDF y las vincula.

    Idempotente: si la venta ya tiene factura devuelve esa, sin emitir otra. Es
    lo que sostiene el reintento del webhook de MercadoPago, que puede llegar
    más de una vez para el mismo pago, y el poll de `mp-status`, que le pega
    cada pocos segundos mientras el cliente escanea.

    No toca la caja — ver el docstring del módulo.
    """
    venta = db.get_venta(venta_id)
    if not venta:
        raise VentaNoFacturable(f"La venta {venta_id} no existe.")

    if venta.get("factura_id"):
        logger.info("Venta %s ya facturada (factura %s), no se reemite",
                    venta_id, venta["factura_id"])
        return db.get_factura(venta["factura_id"])

    # `estado` y no `status`: en este producto `get_venta` devuelve el estado ya
    # traducido, y `anular_venta` deja `status_detail='anulada'`.
    if venta.get("estado") == "anulada":
        raise VentaNoFacturable(f"La venta {venta_id} está anulada.")

    cfg = config_manager.load()
    emisor_cond = cfg.get("empresa_iva_condition", "Monotributista")

    cliente = CONSUMIDOR_FINAL
    if venta.get("cliente_id"):
        registrado = db.get_client(venta["cliente_id"])
        if registrado:
            cliente = registrado

    tipo = _tipo_comprobante(emisor_cond, cliente.get("iva_condition", "Consumidor Final"))
    # El tipo C no discrimina IVA: emitirlo con alícuota dejaría el neto y el
    # total distintos en un comprobante que sólo tiene total.
    iva_rate = 0.0 if tipo == 11 else IVA_RATE_DEFAULT

    items, subtotal, iva_amount, total = _armar_items(venta, iva_rate)
    if not items:
        raise VentaNoFacturable(f"La venta {venta_id} no tiene ítems.")

    punto_venta = _punto_venta(venta)
    numero, ta, arca = await get_next_numero_with_arca(punto_venta, tipo)

    factura_id = db.create_factura(
        tipo=tipo, punto_venta=punto_venta, numero=numero,
        fecha=datetime.date.today().isoformat(),
        cliente_cuit=cliente.get("cuit_dni", ""),
        cliente_razon=cliente["name"],
        cliente_iva_cond=_IVA_CODES.get(cliente.get("iva_condition", "Consumidor Final"), 5),
        items=items,
        subtotal=subtotal, iva_amount=iva_amount, total=total,
        concepto=1,  # Productos
        observaciones=f"Venta {venta['numero']}",
        condicion_venta=_condicion_venta(venta),
        usuario_id=usuario_id if usuario_id is not None else venta.get("usuario_id"),
        # 🔴 Obligatorio desde LibraCore v1.71.0, y **sin default a propósito**:
        # un comprobante emitido contra homologación trae CAE y numeración del
        # WSFE de homologación. Sin marcarlo entra al Libro IVA del cliente y le
        # rompe la correlatividad.
        #
        # Sale de `ambiente_de(arca)` —el MISMO `arca` con el que se acaba de
        # pedir el número— y no de la config leída aparte: leerlas por separado
        # dejaría la factura marcada con un ambiente distinto del que la numeró
        # si el selector cambia entre las dos lecturas. Además ese tercer valor
        # no siempre es un dict —en dev es el string `"_dev_mock_"`— y
        # `ambiente_de` es justamente quien sabe traducirlo.
        ambiente=ambiente_de(arca),
    )

    factura = db.get_factura(factura_id)
    factura = await solicitar_cae(factura_id, factura, ta, arca)

    try:
        pdf_path = pdf_gen.generate_pdf_factura(factura)
        db.update_factura_pdf_path(factura_id, pdf_path)
        factura = db.get_factura(factura_id)
    except Exception:
        # El PDF se regenera solo al descargarlo; perderlo no invalida el CAE,
        # y fallar acá dejaría la factura emitida y sin vincular a la venta.
        logger.exception("Error generando el PDF de la factura %s", factura_id)

    db.vincular_venta_factura(venta_id, factura_id)

    # La plata de esta venta ya entró a la caja cuando se cobró; lo que faltaba
    # era atarla al comprobante. Sin esto la factura sale "Sin cobrar" aunque el
    # dinero esté adentro — y registrar un cobro nuevo lo contaría dos veces.
    vinculados = db.vincular_cobros_de_venta(venta["numero"], factura_id)
    logger.info("Factura %s de la venta %s: %s movimiento(s) de caja vinculados",
                factura_id, venta_id, vinculados)

    return factura


async def facturar_si_esta_prendida(venta_id: int, cfg: dict | None = None) -> int | None:
    """Emite la factura de la venta **si la instancia tiene la automática
    prendida**, y devuelve su id. `None` si está apagada o si falló.

    🔑 **Existe porque hay DOS caminos** por los que este producto se entera de
    que el QR se pagó: el webhook de MercadoPago y el poll de
    `GET /api/ventas/{id}/mp-status`. En la instancia real de Contalibra el
    webhook **no llegó nunca** —cero POST en el log— y el único camino vivo era
    el poll; si sólo facturara el webhook, la venta quedaría cobrada y "Sin
    facturar" sin que nada lo dijera. Los dos llaman acá.

    **No propaga el error**: el cobro ya está registrado, y perderlo sería peor
    que quedarse sin la factura, que se puede emitir después a mano desde el
    detalle de la venta.
    """
    cfg = config_manager.load() if cfg is None else cfg
    if not cfg.get("mp_auto_facturar_ventas"):
        return None
    try:
        factura = await facturar_venta(venta_id)
    except Exception as e:
        logger.error("Error auto-facturando la venta %s: %s", venta_id, e)
        return None
    logger.info("Auto-factura de la venta %s: id=%s CAE=%s",
                venta_id, factura["id"], factura.get("cae") or "sin CAE")
    return factura["id"]
