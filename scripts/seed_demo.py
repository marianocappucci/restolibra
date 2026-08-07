#!/usr/bin/env python3
"""Carga los datos de la demo pública de Restolibra — ítem 8 de los pendientes
transversales de Libra.

**Para qué.** Una demo vacía no muestra nada: quien entra ve pantallas en blanco
y se va. Este script deja la instancia con una parrilla andando, para que las
pantallas se puedan mirar.

**Por la API y no por SQL**, a propósito: así los datos pasan por las mismas
validaciones y los mismos servicios que usa la pantalla. Un seed por SQL puede
crear estados que la aplicación nunca produciría —una mesa ocupada sin pedido,
por ejemplo— y entonces lo que se muestra no es el producto.

**No cubre sólo el caso feliz.** Deja los estados que las pantallas distinguen:
mesas libres y ocupadas, pedidos abiertos y cobrados, una reserva para hoy,
productos por estación (cocina y barra) — que es lo que reparte el KDS— y
stock por debajo del mínimo.

🔴 **No emite facturas.** El módulo de facturación habla con ARCA de verdad; una
demo pública no puede pedir CAE contra el padrón por cada visita.

**Es idempotente**: si el registro ya existe no lo duplica.

> 🔴 **Nunca contra la instancia de un cliente.** Se planta si el host no es de
> dev, demo, prueba o local. Ojo: la instancia productiva de Restolibra es
> `sistema.restolibra.com.ar` —servida por un contenedor llamado
> `restolibra-demo`, que **no** es una demo—.

Uso:
    python scripts/seed_demo.py --url https://demo.restolibra.com.ar \\
        --usuario admin --password ...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from http.cookiejar import CookieJar
from urllib.parse import urlparse

HOY = date.today()

#: Los subdominios que NO son de un cliente. Se compara el host entero o su
#: primera etiqueta, **no como substring de la URL**.
_HOSTS_NO_PRODUCTIVOS = ("dev", "demo", "prueba", "localhost", "127.0.0.1")


def url_no_productiva(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    return host in _HOSTS_NO_PRODUCTIVOS or host.split(".")[0] in _HOSTS_NO_PRODUCTIVOS


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar())
        )

    def _pedir(self, metodo: str, ruta: str, cuerpo=None):
        datos = json.dumps(cuerpo, default=str).encode() if cuerpo is not None else None
        req = urllib.request.Request(
            f"{self.base}{ruta}", data=datos, method=metodo,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self.opener.open(req, timeout=30) as r:
                crudo = r.read()
                return json.loads(crudo) if crudo else None
        except urllib.error.HTTPError as e:
            detalle = e.read().decode(errors="replace")[:300]
            raise RuntimeError(f"{metodo} {ruta} -> {e.code}: {detalle}") from None

    def get(self, ruta):
        return self._pedir("GET", ruta)

    def post(self, ruta, cuerpo=None):
        return self._pedir("POST", ruta, cuerpo)

    def put(self, ruta, cuerpo=None):
        return self._pedir("PUT", ruta, cuerpo)


def _lista(datos):
    """Los listados de este producto a veces vienen envueltos. Devuelve siempre
    la lista."""
    if datos is None:
        return []
    if isinstance(datos, list):
        return datos
    return next((v for v in datos.values() if isinstance(v, list)), [])


def obtener_o_crear(api: Api, ruta: str, clave: str, valor, cuerpo: dict,
                    ruta_alta: str | None = None):
    """Crea el registro si no está. Devuelve `(registro, es_nuevo)`."""
    for existente in _lista(api.get(ruta)):
        if existente.get(clave) == valor:
            return existente, False
    return api.post(ruta_alta or ruta, cuerpo), True


# ── El local ──────────────────────────────────────────────────────────────
#
# Una parrilla de barrio. Se eligió un rubro donde la carta se reparte entre
# cocina y barra —que es lo que hace el KDS— y donde salón, mostrador y delivery
# conviven, que son los tres canales del producto.

CATEGORIAS = ["Entradas", "Parrilla", "Guarniciones", "Postres", "Bebidas"]

#: (nombre, código, categoría, precio, costo, estación)
#:
#: La **estación** es lo que reparte el pedido entre las pantallas del KDS. Con
#: todo en una sola, esa pantalla muestra siempre lo mismo.
CARTA = [
    ("Provoleta", "ENT-01", "Entradas", 9500, 5200, "cocina"),
    ("Empanada de carne", "ENT-02", "Entradas", 2200, 1100, "cocina"),
    ("Bife de chorizo", "PAR-01", "Parrilla", 26000, 16000, "cocina"),
    ("Entraña", "PAR-02", "Parrilla", 24000, 15000, "cocina"),
    ("Vacío", "PAR-03", "Parrilla", 22000, 13500, "cocina"),
    ("Pollo a la parrilla", "PAR-04", "Parrilla", 17000, 9500, "cocina"),
    ("Papas fritas", "GUA-01", "Guarniciones", 7500, 3200, "cocina"),
    ("Ensalada mixta", "GUA-02", "Guarniciones", 6800, 2900, "cocina"),
    ("Flan casero", "POS-01", "Postres", 6500, 2800, "cocina"),
    ("Agua sin gas 500 cc", "BEB-01", "Bebidas", 2500, 1200, "barra"),
    ("Gaseosa línea Coca 500 cc", "BEB-02", "Bebidas", 3200, 1700, "barra"),
    ("Cerveza artesanal pinta", "BEB-03", "Bebidas", 6500, 3400, "barra"),
    ("Vino Malbec copa", "BEB-04", "Bebidas", 5800, 2900, "barra"),
]

STOCK = {
    "ENT-01": 24,
    "ENT-02": 80,
    "PAR-01": 15,
    "PAR-02": 4,       # bajo
    "PAR-03": 12,
    "PAR-04": 18,
    "BEB-01": 60,
    "BEB-02": 48,
    "BEB-03": 0,       # se acabó
    "BEB-04": 30,
    # Las guarniciones se venden en casi todos los pedidos y no estaban acá:
    # quedaban en negativo, y peor, un poco mas negativo en cada corrida.
    "GUA-01": 40,
    "GUA-02": 25,
}

SALONES = [
    {"nombre": "Salón principal", "orden": 1},
    {"nombre": "Vereda", "orden": 2},
]

#: (salón, nombre de la mesa, capacidad)
MESAS = [
    ("Salón principal", "1", 4),
    ("Salón principal", "2", 4),
    ("Salón principal", "3", 6),
    ("Salón principal", "4", 2),
    ("Vereda", "V1", 4),
    ("Vereda", "V2", 2),
]

CLIENTES = [
    {"name": "Consumidor final", "iva_condition": "Consumidor Final"},
    {"name": "Gustavo Peralta", "cuit_dni": "20-27456789-3",
     "iva_condition": "Consumidor Final", "phone": "11 5566-1122"},
    {"name": "Hotel Los Álamos", "cuit_dni": "30-71333555-7",
     "iva_condition": "Responsable Inscripto", "phone": "11 4300-9900",
     "address": "Av. Santa Fe 2100, CABA"},
]


def sembrar(api: Api) -> None:
    hechos = {}

    def contar(clave: str, nuevo: bool):
        creados, existentes = hechos.get(clave, (0, 0))
        hechos[clave] = (creados + int(nuevo), existentes + int(not nuevo))

    print("Categorías…")
    for nombre in CATEGORIAS:
        _, nuevo = obtener_o_crear(api, "/api/productos/categorias", "nombre",
                                   nombre, {"nombre": nombre})
        contar("categorías", nuevo)

    print("Carta…")
    productos = {}
    for nombre, codigo, categoria, precio, costo, estacion in CARTA:
        registro, nuevo = obtener_o_crear(api, "/api/productos", "codigo", codigo, {
            "nombre": nombre, "codigo": codigo, "categoria": categoria,
            "precio_venta": precio, "precio_costo": costo,
            "estacion": estacion, "stock_minimo": 5,
        })
        productos[codigo] = registro["id"]
        contar("carta", nuevo)

    print("Stock…")
    for codigo, cantidad in STOCK.items():
        if cantidad == 0:
            continue
        # `modo: absoluto` es idempotente: fija la existencia, no la suma.
        api.post(f"/api/stock/{productos[codigo]}/ajuste", {
            "modo": "absoluto", "cantidad": cantidad,
            "referencia": "Carga inicial de la demo",
        })
        contar("stock", True)

    print("Clientes…")
    clientes = {}
    for c in CLIENTES:
        registro, nuevo = obtener_o_crear(api, "/api/clientes", "name", c["name"], c)
        clientes[c["name"]] = registro["id"]
        contar("clientes", nuevo)

    print("Salones y mesas…")
    mesas = _sembrar_salon(api, contar)

    print("Pedidos…")
    _sembrar_pedidos(api, productos, mesas, contar)

    print("Presupuestos de eventos…")
    _sembrar_presupuestos(api, clientes, contar)

    print("Operación del día (turno, ventas, facturas, caja, cobranzas)…")
    _sembrar_operacion(api, clientes, productos, contar)

    print("Tesorería…")
    _sembrar_tesoreria(api, contar)

    # 🔴 El stock se vuelve a fijar DESPUÉS de las ventas, y no es redundante:
    # las ventas descuentan, así que sin esto la primera corrida termina en un
    # número y la segunda —que saltea las ventas ya creadas— en otro. Modo
    # `absoluto`: correrlo de nuevo no cambia nada.
    # 🔴 Acá NO se saltea el cero, a diferencia de la carga inicial. Allá 0
    # significa "no toques, dejalo sin abastecer"; acá significa "volvé a
    # cero". Salteándolo, cada corrida empujaba ese ítem un poco más abajo
    # —negativo— y el seed dejaba de ser idempotente.
    for codigo, cantidad in STOCK.items():
        api.post(f"/api/stock/{productos[codigo]}/ajuste", {
            "modo": "absoluto", "cantidad": cantidad,
            "referencia": "Ajuste de inventario",
        })

    # El logo del negocio, para que los comprobantes salgan como los de
    # un cliente y no con un hueco arriba.
    _cargar_logo(api, "Parrilla El Fogón", "F", (234, 88, 12), contar)

    print()
    for clave, (creados, existentes) in sorted(hechos.items()):
        print(f"  {clave:<12} {creados} creados, {existentes} ya estaban")


def _sembrar_salon(api: Api, contar) -> dict:
    """Salones, mesas y una reserva para hoy.

    ⚠️ **La configuración se lee de `/api/salon/config`, un solo endpoint que
    devuelve todo** (`{"salones": [...], "mesas_por_salon": {...}, "cfg": {...}}`).
    No hay `GET /api/salon/config/salones`: esa ruta existe sólo para `POST`, y
    pedirla con GET da **405**, no 404 — o sea que ni siquiera avisa que la
    ruta de lectura es otra.
    """
    def leer_config():
        cfg = api.get("/api/salon/config") or {}
        mesas = [m for lista in (cfg.get("mesas_por_salon") or {}).values()
                 for m in lista]
        return cfg.get("salones") or [], mesas

    salones_existentes, mesas_existentes = leer_config()

    salones = {s["nombre"]: s["id"] for s in salones_existentes}
    for s in SALONES:
        if s["nombre"] in salones:
            contar("salones", False)
            continue
        registro = api.post("/api/salon/config/salones", s)
        salones[s["nombre"]] = registro["id"]
        contar("salones", True)

    mesas = {m["nombre"]: m["id"] for m in mesas_existentes}
    for salon, nombre, capacidad in MESAS:
        if nombre in mesas:
            contar("mesas", False)
            continue
        registro = api.post("/api/salon/config/mesas", {
            "salon_id": salones[salon], "nombre": nombre, "capacidad": capacidad,
        })
        mesas[nombre] = registro["id"]
        contar("mesas", True)

    # Una reserva para hoy a la noche: la pantalla de reservas existe y sin
    # ninguna se ve siempre vacía.
    if not _lista(api.get(f"/api/salon/reservas?fecha={HOY.isoformat()}")):
        try:
            api.post("/api/salon/reservas", {
                "mesa_id": mesas["3"], "fecha": HOY.isoformat(), "hora": "21:00",
                "cliente_nombre": "Familia Ledesma", "telefono": "11 6677-2233",
                "comensales": 6, "notas": "Festejo de cumpleaños",
            })
            contar("reservas", True)
        except RuntimeError as e:
            print(f"  -- reserva: {e}")
    else:
        contar("reservas", False)

    return mesas


def _sembrar_pedidos(api: Api, productos: dict, mesas: dict, contar) -> None:
    """Pedidos en los tres canales y en distintos estados.

    Cada pedido se arma con el mismo recorrido que hace el salón: abrir la
    mesa, cargar los ítems, mandarlos a cocina y —según el caso— cobrar.
    Armarlos por SQL dejaría mesas ocupadas sin pedido y comandas que el KDS
    nunca recibió.
    """
    if _pedidos_activos(api) >= 3:
        contar("pedidos", False)
        print("  (ya hay pedidos cargados)")
        return

    # Mesa 1: en curso, ya enviado a cocina. Es lo que el KDS tiene que mostrar.
    _pedido_de_mesa(api, mesas.get("1"), productos,
                    [("PAR-01", 2), ("GUA-01", 1), ("BEB-04", 2)],
                    enviar=True, cobrar=False, contar=contar)

    # Mesa 3: recién sentados, sin mandar a cocina todavía.
    _pedido_de_mesa(api, mesas.get("3"), productos,
                    [("ENT-01", 1), ("ENT-02", 6)],
                    enviar=False, cobrar=False, contar=contar)

    # Delivery cobrado: cierra el circuito y deja algo en la caja del día.
    try:
        # ⚠️ El alta devuelve `{"pedido_id": N}`, **no** un objeto con `id` —
        # igual que `mesa/{id}/abrir`. Los dos endpoints del salón devuelven el
        # id con ese nombre, y suponer `id` da un `KeyError` que no dice nada.
        pedido_id = api.post("/api/pedidos", {
            "canal": "delivery", "cliente_nombre": "Gustavo Peralta",
            "telefono": "11 5566-1122", "direccion": "Bulnes 1450, CABA",
            "repartidor": "Moto 2", "costo_envio": 2500,
        })["pedido_id"]
        for codigo, cantidad in (("PAR-04", 1), ("GUA-01", 1), ("BEB-02", 2)):
            api.post(f"/api/pedidos/{pedido_id}/items", {
                "producto_id": productos[codigo], "qty": cantidad,
            })
        api.post(f"/api/pedidos/{pedido_id}/enviar", {})
        # ⚠️ `cobrar` espera **`pagos`**, una lista: este producto admite cobro
        # mixto y por eso no hay un `medio`/`monto` suelto. Acá había una copia
        # con la forma vieja —el otro cobro del mismo archivo ya lo hacía
        # bien—, así que el pedido de delivery se quedaba sin cobrar en cada
        # corrida con un 422 que el seed avisaba y salteaba.
        api.post(f"/api/pedidos/{pedido_id}/cobrar", {
            "pagos": [{"medio": "efectivo",
                       "monto": _total(api.get(f"/api/pedidos/{pedido_id}"))}],
        })
        contar("pedidos", True)
    except RuntimeError as e:
        print(f"  -- pedido de delivery: {e}")


def _pedido_de_mesa(api: Api, mesa_id, productos: dict, items, *,
                    enviar: bool, cobrar: bool, contar) -> None:
    if mesa_id is None:
        return
    try:
        # `abrir` devuelve `{"pedido_id": N}` — y es **idempotente**: si la
        # mesa ya tiene un pedido abierto devuelve ese mismo, sin crear otro.
        # O sea que el id sale de acá y no hay que salir a buscarlo al listado.
        pedido_id = api.post(f"/api/salon/mesa/{mesa_id}/abrir",
                             {"comensales": 4})["pedido_id"]
        for codigo, cantidad in items:
            api.post(f"/api/pedidos/{pedido_id}/items", {
                "producto_id": productos[codigo], "qty": cantidad,
            })
        if enviar:
            api.post(f"/api/pedidos/{pedido_id}/enviar", {})
        if cobrar:
            # ⚠️ `cobrar` espera **`pagos`**, una lista: este producto admite
            # cobro mixto (mitad efectivo, mitad tarjeta) y por eso no hay un
            # `medio`/`monto` suelto.
            api.post(f"/api/pedidos/{pedido_id}/cobrar", {
                "pagos": [{"medio": "efectivo",
                           "monto": _total(api.get(f"/api/pedidos/{pedido_id}"))}],
            })
        contar("pedidos", True)
    except RuntimeError as e:
        print(f"  -- mesa {mesa_id}: {e}")


def _pedidos_activos(api: Api) -> int:
    """Cuántos pedidos hay abiertos, contando los tres canales **y las mesas**.

    ⚠️ `/api/pedidos` es el board de mostrador: devuelve
    `{"por_canal": {"barra": [...], "takeaway": [...], "delivery": [...]}}` y
    **excluye los de salón** a propósito — ésos viven en el mapa de mesas, que
    es otra pantalla. Contar sólo ahí da 1 donde hay 3.
    """
    board = api.get("/api/pedidos") or {}
    de_mostrador = sum(len(v) for v in (board.get("por_canal") or {}).values())
    mapa = api.get("/api/salon/mapa") or {}
    ocupadas = sum(1 for m in (mapa.get("mesas") or [])
                   if m.get("pedido_id") or m.get("estado") == "ocupada")
    return de_mostrador + ocupadas


def _total(pedido) -> float:
    for clave in ("total", "total_final", "importe_total"):
        if isinstance(pedido, dict) and pedido.get(clave) is not None:
            return float(pedido[clave])
    return 0.0



def _tiene_modulo(api, ruta: str) -> bool:
    """Si la instancia expone esa ruta.

    🔴 Restolibra pinea una version de libracore anterior a los recibos
    numerados, asi que `/api/recibos` **no existe** y pedirlo mata el seed
    entero. Lo que no esta se saltea con un aviso; asumir que dos productos de
    la misma familia tienen los mismos modulos es exactamente el error que
    esto evita.
    """
    try:
        api.get(ruta)
        return True
    except RuntimeError as e:
        if "404" in str(e):
            return False
        raise
    except json.JSONDecodeError:
        # 🔴 Este producto sirve la SPA con un catch-all: una ruta que no
        # existe contesta **200 con el index.html**, no un 404. Sin esto, el
        # helper no decía "no está" sino que reventaba y se llevaba puesto el
        # seed entero. Misma trampa que ya obligó a que el botón de la demo
        # validara la forma de la respuesta y no el código.
        return False



def _sembrar_presupuestos(api: Api, clientes: dict, contar) -> None:
    """Presupuestos de eventos, en los estados que la pantalla distingue, y el
    remito que sale del aceptado.

    En una parrilla el presupuesto es el de un evento —un cumpleaños, una cena
    de empresa—, no el de un mostrador. El aceptado genera su remito, que es el
    flujo natural del producto: uno aceptado sin remito se lee como algo a
    medio hacer.
    """
    if _lista(api.get("/api/presupuestos")):
        contar("presupuestos", False)
        print("  (ya hay presupuestos cargados)")
        return

    PLAN = [
        ("Hotel Los Álamos", 10, [
            ("Servicio de catering para 40 personas", 1, 680000),
            ("Mozos adicionales (2)", 2, 45000),
        ], "aceptado"),
        ("Gustavo Peralta", 5, [
            ("Cumpleaños 25 personas — menú parrilla", 1, 390000),
        ], "enviado"),
        ("Hotel Los Álamos", 2, [
            ("Coffee break para reunión (15)", 1, 96000),
        ], "rechazado"),
        # En borrador: el estado inicial, y el que la pantalla usa para saber
        # qué se puede seguir editando.
        ("Gustavo Peralta", 0, [
            ("Menú degustación para 8", 1, 210000),
        ], None),
    ]

    for cliente, dias, items, estado in PLAN:
        fecha = HOY - timedelta(days=dias)
        try:
            presupuesto = api.post("/api/presupuestos", {
                "date": fecha.isoformat(),
                "valid_until": (fecha + timedelta(days=30)).isoformat(),
                "client_id": clientes.get(cliente),
                "items": [{"description": d, "qty": c, "unit_price": p}
                          for d, c, p in items],
                "observations": "Presupuesto de ejemplo de la demo.",
            })
        except RuntimeError as e:
            print(f"  -- presupuesto de {cliente}: {e}")
            continue
        contar("presupuestos", True)
        if estado:
            try:
                api.post(f"/api/presupuestos/{presupuesto['id']}/estado", {
                    "estado": estado,
                    "convertir_remito": estado == "aceptado",
                })
            except RuntimeError as e:
                print(f"  -- estado {estado}: {e}")



def _sembrar_tesoreria(api: Api, contar) -> None:
    """Cuentas de tesorería, sus movimientos y una transferencia entre las dos.

    Tesorería es la plata que **no** está en la caja del día: la cuenta del
    banco, el efectivo guardado. Por eso son cuentas propias y no movimientos
    de caja — y por eso la transferencia entre las dos es el ejemplo que hace
    entender la pantalla: mostrar sólo ingresos deja la mitad sin verse.
    """
    resumen = api.get("/api/tesoreria") or {}
    if resumen.get("cuentas"):
        contar("tesoreria", False)
        print("  (ya hay cuentas de tesorería)")
        return

    cuentas = {}
    for nombre, tipo, banco, saldo in (
        ("Cuenta corriente Banco Nación", "banco", "Banco Nación", 850000),
        ("Efectivo en caja fuerte", "efectivo", "", 220000),
    ):
        try:
            creada = api.post("/api/tesoreria/cuentas", {
                "nombre": nombre, "tipo": tipo, "banco": banco,
                "saldo_inicial": saldo,
                "descripcion": "Cuenta de ejemplo de la demo",
            })
            cuentas[nombre] = creada.get("id") or creada.get("cuenta", {}).get("id")
            contar("tesoreria", True)
        except RuntimeError as e:
            print(f"  -- cuenta {nombre}: {e}")

    banco = cuentas.get("Cuenta corriente Banco Nación")
    caja_fuerte = cuentas.get("Efectivo en caja fuerte")

    if banco:
        for tipo, concepto, monto in (
            ("ingreso", "Depósito de la recaudación del fin de semana", 380000),
            ("egreso", "Pago a proveedor de bebidas", 145000),
        ):
            try:
                api.post(f"/api/tesoreria/cuentas/{banco}/movimiento", {
                    "fecha": HOY.isoformat(), "tipo": tipo,
                    "monto": monto, "concepto": concepto,
                    "referencia": "Movimiento de ejemplo",
                })
                contar("tesoreria_mov", True)
            except RuntimeError as e:
                print(f"  -- movimiento de tesorería: {e}")

    if banco and caja_fuerte:
        try:
            api.post("/api/tesoreria/transferencia", {
                "cuenta_origen_id": caja_fuerte, "cuenta_destino_id": banco,
                "monto": 100000, "fecha": HOY.isoformat(),
                "concepto": "Depósito del efectivo de la semana",
            })
            contar("transferencia", True)
        except RuntimeError as e:
            print(f"  -- transferencia: {e}")


def _sesion_del_visitante(api):
    """Una sesión con el usuario de la demo, si la instancia es una demo.

    Existe para lo que el producto ordena **por usuario**: un turno de caja
    abierto por el admin no aparece en la pantalla del visitante, aunque esté
    ahí. Las credenciales salen del entorno del contenedor.
    """
    usuario = os.environ.get("DEMO_USERNAME", "").strip()
    clave = os.environ.get("DEMO_PASSWORD", "")
    if not usuario or not clave:
        return None
    base = getattr(api, "base", None)
    if not base:
        return None
    sesion = Api(base)
    try:
        sesion.post("/api/login", {"username": usuario, "password": clave})
    except RuntimeError as e:
        print(f"  -- no se pudo entrar como {usuario}: {e}")
        return None
    return sesion


def _sembrar_operacion(api: Api, clientes: dict, productos: dict, contar) -> None:
    """Turno de caja, ventas, facturas internas, recibos, cobranza, caja y
    egresos: diez pantallas del menú que se abrían vacías.

    🔴 **Las facturas se emiten SIN CAE, y es a propósito.** El módulo habla
    con ARCA de verdad, pero sin certificado configurado —y una demo no lo
    tiene— el comprobante nace como documento interno: se ve la pantalla, el
    detalle y el PDF con su maqueta real, sin pedir CAE contra el padrón ni
    emitir nada fiscal desde una demo pública.
    """
    visitante = _sesion_del_visitante(api)
    quien = visitante or api
    if not _lista(quien.get("/api/turnos")):
        try:
            quien.post("/api/turnos/abrir", {
                "monto_inicial": 30000, "notas": "Apertura de caja de la demo",
            })
            contar("turno", True)
        except RuntimeError as e:
            print(f"  -- turno: {e}")

    print("Proveedores…")
    for p in (
        {"nombre": "Distribuidora de bebidas del Centro", "cuit_dni": "30-71234567-9",
         "email": "ventas@bebidascentro.com.ar", "iva_condition": "Responsable Inscripto"},
        {"nombre": "Carnicería El Novillo", "cuit_dni": "20-24567890-1",
         "email": "pedidos@elnovillo.com.ar", "iva_condition": "Monotributista"},
    ):
        _, nuevo = obtener_o_crear(api, "/api/proveedores", "nombre", p["nombre"], p)
        contar("proveedores", nuevo)

    if not _lista(api.get("/api/listas-precio")):
        try:
            api.post("/api/listas-precio", {
                "nombre": "Delivery",
                "descripcion": "Recargo del 10% sobre la carta del salón",
            })
            contar("listas", True)
        except RuntimeError as e:
            print(f"  -- lista de precios: {e}")

    medios = _lista(api.get("/api/ventas/medios-pago")) or ["Efectivo"]
    def medio(preferido):
        planos = [m if isinstance(m, str) else (m.get("nombre") or m.get("id"))
                  for m in medios]
        return next((m for m in planos if preferido.lower() in str(m).lower()), planos[0])

    def item(codigo, nombre, qty, precio):
        return {"nombre": nombre, "qty": qty, "precio": precio,
                "producto_id": productos.get(codigo)}

    ventas_hechas = {v.get("observaciones") for v in _lista(api.get("/api/ventas"))}
    primera = None
    for cliente, items, pagos, obs in _VENTAS_DEL_DIA(item, medio):
        if obs in ventas_hechas:
            continue
        try:
            venta = api.post("/api/ventas", {
                "fecha": HOY.isoformat(),
                "cliente_id": clientes.get(cliente),
                "items": [i for i in items if i["producto_id"]],
                "pagos": [{"medio": m, "monto": mo, "referencia": ""} for m, mo in pagos],
                "observaciones": obs,
            })
            contar("ventas", True)
            primera = primera or venta
        except RuntimeError as e:
            print(f"  -- venta ({obs}): {e}")

    if primera and _tiene_modulo(api, "/api/recibos"):
        if not _lista(api.get("/api/recibos")):
            try:
                api.post(f"/api/recibos/venta/{primera['id']}", {})
                contar("recibos", True)
            except RuntimeError as e:
                print(f"  -- recibo: {e}")
    elif primera:
        print("  (esta instancia no tiene recibos numerados: libracore < 1.9.0)")

    if not _lista(api.get("/api/facturas")):
        for tipo, cliente, items in (
            (6, "Hotel Los Álamos", [("Servicio de catering para evento", 1, 185000)]),
            (11, "Gustavo Peralta", [("Cena para dos", 1, 42000)]),
        ):
            try:
                api.post("/api/facturas", {
                    "tipo": tipo, "fecha": HOY.isoformat(),
                    "client_id": clientes.get(cliente),
                    "client_name": cliente,
                    "items": [{"description": d, "qty": c, "unit_price": p}
                              for d, c, p in items],
                    "tax_rate": 0.21, "condicion_venta": "Contado",
                    "observations": "Comprobante interno de la demo (sin CAE).",
                })
                contar("facturas", True)
            except RuntimeError as e:
                print(f"  -- factura tipo {tipo}: {e}")

    # Cuenta corriente: un pago a cuenta del cliente que compra fiado. La
    # deuda nace de las ventas, así que esto sólo tiene sentido si el cliente
    # ya tiene saldo — y si no lo tiene, el producto lo dice y se saltea.
    cliente_cc = clientes.get("Hotel Los Álamos")
    if cliente_cc and not _lista(api.get("/api/cuenta-corriente")):
        try:
            api.post(f"/api/cuenta-corriente/{cliente_cc}/pagar", {
                "monto": 50000, "fecha": HOY.isoformat(),
                "concepto": "Pago a cuenta", "medio_pago": medio("efectivo"),
                "referencia": "Recibo de la demo",
            })
            contar("cobranzas", True)
        except RuntimeError as e:
            print(f"  -- cobranza: {e}")

    if not _lista(api.get("/api/caja")):
        for tipo, concepto, monto in (
            ("ingreso", "Aporte del socio", 40000),
            ("egreso", "Compra de hielo y carbón", 18500),
        ):
            try:
                api.post("/api/caja", {
                    "fecha": HOY.isoformat(), "tipo": tipo, "concepto": concepto,
                    "monto": monto, "medio_pago": medio("efectivo"),
                    "referencia": "Movimiento de ejemplo",
                })
                contar("caja", True)
            except RuntimeError as e:
                print(f"  -- caja {tipo}: {e}")

    # 🔴 Dos cosas medidas contra la demo, iguales que en Contalibra (mismo
    # motor de Libros de IVA):
    #
    # 1. **El libro de compras sólo toma `tipo_comprobante = 'factura'`** (el
    #    filtro está en el SQL de `get_egresos_para_iva`). Con egresos sueltos
    #    el lado de compras salía vacío y el export bajaba 0 bytes.
    # 2. **`iva_pct` es una fracción**, no puntos: el alta hace
    #    `monto_neto * iva_pct` sin dividir por 100. Con `21` el IVA de un gasto
    #    de $38.000 salía $798.000.
    proveedores = {p["nombre"]: p["id"] for p in _lista(api.get("/api/proveedores"))}
    if not _lista(api.get("/api/egresos")):
        for concepto, categoria, neto, prov, numero in (
            ("Bebidas para el salón", "Mercadería / Materias primas", 168000,
             "Distribuidora de bebidas del Centro", "0002-00004417"),
            ("Carne y achuras de la semana", "Mercadería / Materias primas", 284000,
             "Carnicería El Novillo", "0001-00000926"),
            ("Alquiler del local", "Alquiler", 450000, None, ""),
            ("Gas envasado", "Servicios", 62000, None, ""),
            ("Servilletas y descartables", "Insumos", 38000, None, ""),
        ):
            try:
                api.post("/api/egresos", {
                    "fecha": HOY.isoformat(), "concepto": concepto,
                    "categoria": categoria, "monto_neto": neto, "iva_pct": 0.21,
                    # Con proveedor y número es una factura de compra y entra al
                    # libro; sin ellos es un gasto interno. Los dos casos están
                    # a propósito: la pantalla muestra la diferencia.
                    "tipo_comprobante": "factura" if prov else "otro",
                    "numero": numero,
                    "proveedor_id": proveedores.get(prov),
                    "observaciones": "Gasto de ejemplo de la demo",
                })
                contar("egresos", True)
            except RuntimeError as e:
                print(f"  -- egreso {concepto}: {e}")


def _VENTAS_DEL_DIA(item, medio):
    """El plan de ventas, como función para poder usar los helpers de arriba."""
    return [
        ("Consumidor final",
         [item("PAR-01", "Bife de chorizo", 2, 26000),
          item("GUA-01", "Papas fritas", 2, 7500)],
         [(medio("efectivo"), 67000)], "Venta de mostrador"),
        ("Hotel Los Álamos",
         [item("PAR-03", "Vacío", 4, 22000)],
         [(medio("tarjeta"), 88000)], "Pedido de oficina"),
    ]



def _cargar_logo(api, nombre: str, inicial: str, color: tuple, contar) -> None:
    """Dibuja el logo del negocio y lo sube a Configuración.

    🔴 **Se genera, no se commitea.** PIL viene en la imagen del producto, así
    que el seed lo dibuja en el momento: no hay binarios en el repo y cambiar
    el color es cambiar una línea. Mismo criterio que el resto del seed — el
    estado limpio es código, no un archivo guardado a mano.

    Sin logo, los PDF de la demo salen con un hueco arriba: el interesado ve
    dónde iría el suyo pero no cómo se ve.

    ⚠️ El campo del multipart se llama **`logo`**, no `file`: con `file` la API
    contesta 422. Está leído del openapi de la instancia.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  (sin PIL: se saltea el logo)")
        return

    # 🔴 La ruta de configuración no es la misma en todos los productos, y
    # pedir la que no existe **no da 404**: el catch-all de la SPA contesta
    # 200 con el index.html y el parseo revienta. Así que la guarda no puede
    # depender de acertarla: ante cualquier duda se sube el logo, que es
    # inocuo, en vez de arriesgar quedarse sin él.
    for ruta in ("/api/config/empresa", "/api/config"):
        try:
            actual = api.get(ruta)
        except Exception:
            continue
        if isinstance(actual, dict):
            plano = str(actual)
            if '"logo"' in plano or "'logo'" in plano:
                if any("logo" in str(k) and v for k, v in actual.items()):
                    contar("logo", False)
                    return
            break

    imagen = Image.new("RGBA", (520, 160), (255, 255, 255, 0))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.rounded_rectangle((8, 20, 128, 140), radius=24, fill=color)
    dibujo.text((52, 60), inicial, fill=(255, 255, 255))
    dibujo.text((150, 55), nombre, fill=(30, 30, 30))
    dibujo.line((150, 95, 150 + min(340, len(nombre) * 11), 95), fill=color, width=4)

    # 🔴 La subida es multipart a mano, así que necesita la URL y el opener del
    # `Api` real. La suite corre el seed contra un doble que habla directo con
    # la app y no tiene ninguno de los dos: sin esta guarda, `api.base`
    # reventaba con AttributeError y se llevaba puestos **11 tests** del seed
    # entero, no sólo el del logo.
    if not getattr(api, "base", None) or not getattr(api, "opener", None):
        return

    import io
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")

    limite = "----seed" + "0" * 12
    cuerpo = (
        f"--{limite}\r\n"
        'Content-Disposition: form-data; name="logo"; filename="logo.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode() + buffer.getvalue() + f"\r\n--{limite}--\r\n".encode()

    import urllib.request
    pedido = urllib.request.Request(
        f"{api.base}/api/config/empresa/logo", data=cuerpo, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={limite}"},
    )
    try:
        api.opener.open(pedido, timeout=30)
        contar("logo", True)
    except Exception as e:
        print(f"  -- logo: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--usuario", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument(
        "--force", action="store_true",
        help="Correr contra una URL que no parece de dev ni de demo. No usar.",
    )
    args = ap.parse_args()

    if not url_no_productiva(args.url) and not args.force:
        print(f"ERROR: {args.url} no parece una instancia de dev ni de demo.",
              file=sys.stderr)
        print("Este script NO se corre contra la instancia de un cliente.",
              file=sys.stderr)
        return 2

    api = Api(args.url)
    api.post("/api/login", {"username": args.usuario, "password": args.password})
    sembrar(api)
    return 0


if __name__ == "__main__":
    sys.exit(main())
