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
    for c in CLIENTES:
        _, nuevo = obtener_o_crear(api, "/api/clientes", "name", c["name"], c)
        contar("clientes", nuevo)

    print("Salones y mesas…")
    mesas = _sembrar_salon(api, contar)

    print("Pedidos…")
    _sembrar_pedidos(api, productos, mesas, contar)

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
        api.post(f"/api/pedidos/{pedido_id}/cobrar", {
            "medio": "efectivo",
            "monto": _total(api.get(f"/api/pedidos/{pedido_id}")),
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
