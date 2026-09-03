"""Aprovisionamiento del nodo offline, del lado del CENTRAL.

Los tres pasos que hay que dar una vez por sucursal, antes de instalar nada en
la PC del cliente:

    python -m scripts.nodo_offline publicar          # instala los triggers y siembra
    python -m scripts.nodo_offline registrar node-1  # da de alta el nodo y emite su secreto
    python -m scripts.nodo_offline estado            # que hay publicado y que nodos existen

Se corre **en el contenedor del cliente**, con su `RESTOLIBRA_DATABASE_URL`, del
mismo modo que el resto de los scripts de este repo.

## Por que la lista de tablas vive aca y no en LibraEdge

Es el **reparto de autoridad** de este producto: que datos manda el central y el
nodo sólo espeja. LibraEdge no puede saberlo — no conoce ni un nombre de tabla de
Restolibra, y esa ignorancia es la que lo hace reusable. Ver el análisis
`nodo-libraedge-espejo-local` en el wiki.

## Lo que NO se publica, y no es un olvido

Las tablas de **autoridad del nodo** (`pedidos`, `ventas`, `caja_movimientos`,
`turnos_caja`, `movimientos_stock`, `sales`…) quedan afuera a propósito: el nodo
las genera y las sube. Publicarlas haría que el central se las mandara de vuelta
y el nodo se pisara sus propios datos.

Y las de **fuera de alcance** (ARCA, Mercado Pago, cuenta corriente, compras,
egresos) tampoco: sin conectividad no hay autorización fiscal ni pasarela de
pago, así que espejarlas daría la impresión de que funcionan offline.
"""

import argparse
import sys
from datetime import UTC

#: El reparto de autoridad de la Fase 0: qué tablas manda el central y el nodo
#: sólo espeja. **Sólo los nombres** — la clave primaria NO se declara acá.
#:
#: 🔴 Se declaraban las dos cosas, y estaba mal. La PK no es una decisión: es un
#: hecho del schema, y escribirla a mano se equivoca en silencio. Pasó al primer
#: intento contra la base real: `units` tiene PK `code`, no `id`, así que el
#: trigger publicaba `row_id` nulo y el aprovisionamiento moría con una violación
#: de NOT NULL en la mitad de la lista. Ahora se lee de la base — ver
#: `_clave_primaria()`.
TABLAS_DE_REFERENCIA = frozenset({
    # LibraCore
    "clients", "modulos", "usuarios", "proveedores", "cuentas_tesoreria",
    "cajas",
    #
    # 🔴 NO están `productos`, `categorias_producto`, `listas_precio` ni
    # `lista_precio_items`, y no es un olvido: **este producto no las lee.**
    #
    # Existen en la base porque el DDL de LibraCore las crea, pero desde la
    # migración a LibraCommerce (P8) el catálogo y los precios de Restolibra
    # viven en `catalog_items`, `categories`, `price_lists` e `item_prices`.
    # Medido el 2026-08-31: cero consultas a las cuatro en `app/`, y ninguno de
    # los routers del motor que este producto monta --facturas, ARCA, config,
    # MercadoPago-- las toca. El propio `app/db_listas_precio.py` dice en su
    # primera línea que corre sobre `price_lists`/`item_prices`.
    #
    # Espejarlas sería peor que no hacerlo: le mandaría al nodo tablas vacías
    # que nadie consulta, y el espejo se vería completo mientras la fuente real
    # está en otro lado. `lista_precio_items` además tiene PK compuesta
    # `(lista_id, producto_id)`, así que el aplicador la salteaba y el
    # `publicar` terminaba diciendo "21 de 22" — un faltante que parecía un
    # problema y era una tabla que sobraba.
    #
    # LibraCommerce
    "catalog_items", "categories", "item_codes", "item_prices", "price_lists",
    "units", "locations", "parties",
    # Propias de Restolibra
    "mesas", "salones", "recetas", "receta_items",
})


def _clave_primaria(conn, tabla: str) -> str | None:
    """La PK de `tabla` según la base, o `None` si no sirve para espejar.

    Devuelve `None` cuando la tabla no tiene PK o la tiene compuesta: el
    aplicador del nodo hace `ON CONFLICT (una_columna)`, así que una PK de dos
    columnas no se puede espejar con este mecanismo. Saltearla **diciéndolo** es
    mejor que publicar cambios que el nodo no va a poder aplicar — eso trabaría
    su bajada en ese cursor, para siempre.
    """
    filas = conn.execute(
        """SELECT a.attname
             FROM pg_index i
             JOIN pg_attribute a
               ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = ?::regclass AND i.indisprimary""",
        (tabla,),
    ).fetchall()
    if len(filas) != 1:
        return None
    return filas[0][0]


def _conexion():
    from app.db_core import get_connection

    return get_connection()


def _tablas_que_existen(conn) -> list[str]:
    """Las de la lista que realmente están en esta base.

    No todas existen en toda instancia: `modulos` y `usuarios` son de LibraCore,
    las de catálogo de LibraCommerce, y una base a medio migrar puede no tener
    alguna. Publicar sobre una tabla inexistente aborta el aprovisionamiento
    entero por la primera que falte; saltearla e **informarlo** es mejor que
    fallar o que hacerlo en silencio.
    """
    presentes = []
    for tabla in sorted(TABLAS_DE_REFERENCIA):
        fila = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables"
            " WHERE table_schema = 'public' AND table_name = ?", (tabla,)
        ).fetchone()
        if fila and fila[0]:
            presentes.append(tabla)
    return presentes


def orden_de_siembra(conn, tablas: list[str]) -> list[str]:
    """`tablas` ordenadas para que un padre se siembre antes que su hijo.

    🔴 **Sin esto la bajada revienta con una violación de foreign key**, y no es
    hipotético: `sembrar` recorría la lista en orden alfabético, y
    `catalog_items` va antes que `categories` — así que el nodo recibía el
    producto antes que su categoría. Hay más: `item_prices` → `catalog_items`,
    `mesas` → `salones`, `receta_items` → `recetas`.

    **Sólo hace falta para la siembra.** Los cambios que vienen después llegan en
    orden causal solos: el central no puede insertar un hijo antes que su padre
    —se lo impide la misma FK— así que el trigger del padre disparó antes y su
    cursor es menor.

    Una dependencia circular entre tablas publicadas no se puede ordenar; se
    devuelven al final y el que falle lo dirá con su nombre, en vez de colgarse.
    """
    dependencias = {tabla: set() for tabla in tablas}
    for hijo, padre in conn.execute(
        """SELECT c.conrelid::regclass::text, c.confrelid::regclass::text
             FROM pg_constraint c WHERE c.contype = 'f'"""
    ).fetchall():
        if hijo in dependencias and padre in dependencias and hijo != padre:
            dependencias[hijo].add(padre)

    ordenadas: list[str] = []
    pendientes = dict(dependencias)
    while pendientes:
        libres = sorted(t for t, deps in pendientes.items() if not (deps - set(ordenadas)))
        if not libres:  # ciclo: se devuelven al final, en orden estable
            ordenadas.extend(sorted(pendientes))
            break
        ordenadas.extend(libres)
        for tabla in libres:
            pendientes.pop(tabla)
    return ordenadas


def publicar() -> int:
    """Instala el trigger del changelog en cada tabla de referencia y la siembra.

    Idempotente en las dos mitades: el trigger se reinstala sin duplicarse, pero
    **sembrar sí vuelve a volcar la tabla entera** — son upserts, así que
    reaplicarlos es inofensivo, pero engorda el changelog. Por eso sólo se
    siembra lo que todavía no tiene nada publicado.
    """
    from libraedge.db.changelog import (
        desinstalar_trigger,
        instalar_trigger,
        sembrar,
        tablas_publicadas,
    )

    publicadas = []
    salteadas: list[str] = []
    sobrantes: list[str] = []
    with _conexion() as conn:
        presentes = _tablas_que_existen(conn)
        faltantes = sorted(TABLAS_DE_REFERENCIA - set(presentes))
        if faltantes:
            print(f"  (no están en esta base, se saltean: {', '.join(faltantes)})")

        # Un padre se siembra antes que su hijo, o el nodo rechaza la fila con
        # una violación de FK y la bajada queda trabada en ese cursor.
        for tabla in orden_de_siembra(conn, presentes):
            pk = _clave_primaria(conn, tabla)
            if pk is None:
                # 🔴 Se anota para FALLAR al final, no sólo para imprimirlo.
                # Una tabla que el nodo no puede espejar es un agujero en su
                # copia, y un agujero que sale por pantalla entre veinte líneas
                # de "trigger ok" se lee como parte del ruido. Con la lista
                # depurada no debería saltearse ninguna: si aparece una, alguien
                # agregó algo que el espejo no sabe aplicar, y el
                # aprovisionamiento tiene que parar ahí.
                print(f"  {tabla}: SALTEADA — sin PK de una sola columna, el "
                      f"espejo del nodo no podría aplicarla")
                salteadas.append(tabla)
                continue
            instalar_trigger(conn, tabla, pk)
            publicadas.append(tabla)
            ya = conn.execute(
                "SELECT COUNT(*) FROM sync_changelog WHERE table_name = ?", (tabla,)
            ).fetchone()[0]
            if ya:
                print(f"  {tabla}: trigger ok (pk {pk}), ya tenía {ya} cambios")
                continue
            sembradas = sembrar(conn, tabla, pk)
            print(f"  {tabla}: trigger ok (pk {pk}), sembradas {sembradas} filas")

        # 🔴 CONVERGER, no solo agregar. Sacar una tabla de la lista de arriba
        # NO desinstala su trigger: un aprovisionamiento anterior ya lo dejó
        # puesto y sigue escribiendo al changelog de algo que el nodo ya no
        # espera. Pasó al sacar las cuatro tablas de precios de LibraCore el
        # 2026-08-31: tres de ellas seguían publicando en el central de demo.
        #
        # Lo instalado se lee del catálogo de PostgreSQL, no de una lista: si
        # se comparara contra otra lista en código, las dos podrían estar
        # igual de desactualizadas.
        sobrantes = [
            tabla for tabla in tablas_publicadas(conn)
            if tabla not in TABLAS_DE_REFERENCIA
        ]
        for tabla in sobrantes:
            desinstalar_trigger(conn, tabla)
            print(f"  {tabla}: trigger RETIRADO — ya no está en la lista")

        conn.commit()
    print(f"Publicadas {len(publicadas)} de {len(presentes)} tablas presentes.")
    if sobrantes:
        print(f"Retirados {len(sobrantes)} triggers de tablas que salieron de la lista.")
    if salteadas:
        print()
        print(f"🔴 {len(salteadas)} tabla(s) sin publicar: {', '.join(salteadas)}.")
        print("El nodo va a espejar una copia INCOMPLETA. O la tabla no hace")
        print("falta --y hay que sacarla de TABLAS_DE_REFERENCIA-- o el")
        print("aplicador tiene que aprender a manejar su clave primaria.")
        return 1
    return 0


def espejo_del_nodo(conn) -> dict[str, str]:
    """`tabla: pk` de lo que este central publica — lo que el nodo debe espejar.

    Sale de la **misma** fuente que usa `publicar()`, y no de una copia: si el
    central publica una tabla que el nodo no espeja, el aplicador del nodo la
    rechaza y la bajada **queda trabada en ese cursor para siempre**.
    """
    return {
        tabla: pk for tabla in _tablas_que_existen(conn)
        if (pk := _clave_primaria(conn, tabla)) is not None
    }


class SegundoNodoEnLaSucursal(RuntimeError):
    """Se intentó registrar un segundo nodo activo en una sucursal que ya tiene."""


def _rechazar_segundo_nodo(conn, node_id: str, branch_id: str) -> None:
    """🔴 Una sucursal tiene UN nodo. Los demás POS son terminales suyas.

    La topología es un nodo por local y N terminales apuntándole por la red —los
    POS son navegadores, no instalaciones—. Dos nodos en el mismo salón no es una
    variante soportada: es el escenario que rompe.

    **Y rompe de la peor manera.** Los dos nodos numeran ventas desde su propia
    base local, así que tarde o temprano emiten el mismo número. Cuando la
    segunda llega al central, el `UNIQUE` de `sales.number` la rechaza — y el
    handler la manda a revisión manual porque eso ya está previsto, pero recién
    ahí, con el ticket impreso y el cliente en la puerta. Nadie se entera hasta
    el arqueo.

    **Re-registrar el MISMO `node_id` sí es legítimo** y no se toca: es cómo se
    reemplaza una PC robada o dada de baja, y emite un secreto nuevo que invalida
    el anterior.

    La guarda es del lado del central a propósito. El instalador corre en la PC
    del cliente y no puede saber qué otras PC hay; el central es el único que ve
    la sucursal entera.
    """
    fila = conn.execute(
        """SELECT node_id FROM node_identity
            WHERE branch_id = ? AND active = 1 AND node_id <> ?
            ORDER BY node_id LIMIT 1""",
        (branch_id, node_id),
    ).fetchone()
    if fila is None:
        return
    raise SegundoNodoEnLaSucursal(
        f"La sucursal {branch_id!r} ya tiene un nodo activo: {fila[0]!r}.\n"
        f"\n"
        f"Una sucursal tiene UN nodo; los demás POS son terminales que le apuntan\n"
        f"por la red interna, sin instalar nada. Dos nodos numeran ventas en\n"
        f"paralelo desde su propia base y terminan chocando en el central, con el\n"
        f"ticket ya impreso.\n"
        f"\n"
        f"Si de verdad se reemplaza el nodo, dar de baja el anterior primero.\n"
        f"Si es la MISMA PC, registrar con el mismo node_id ({fila[0]!r}): eso\n"
        f"emite un secreto nuevo e invalida el viejo, que es lo que corresponde."
    )


def registrar(node_id: str, branch_id: str) -> int:
    """Da de alta el nodo y **muestra su secreto una sola vez**.

    Sólo se persiste el hash: no hay forma de recuperarlo después. Re-registrar
    el mismo `node_id` emite uno nuevo e invalida el anterior — que es cómo se
    reemplaza una PC robada o dada de baja.
    """
    from libraedge.db.repository import NodeRepository

    with _conexion() as conn:
        _rechazar_segundo_nodo(conn, node_id, branch_id)
        secreto = NodeRepository(conn).register_node(node_id, branch_id=branch_id)
        conn.commit()
        espejo = espejo_del_nodo(conn)

    print(f"Nodo {node_id!r} registrado en la sucursal {branch_id!r}.")
    print()
    print("  LIBRAEDGE_NODE_ID=" + node_id)
    print("  LIBRAEDGE_NODE_SECRET=" + secreto)
    print("  LIBRAEDGE_TABLAS_ESPEJO=" + ",".join(
        f"{tabla}:{pk}" for tabla, pk in sorted(espejo.items())))
    print()
    print("🔴 El secreto se muestra UNA SOLA VEZ: sólo se guarda su hash.")
    print("   Copiarlo ahora al archivo de entorno del nodo. Si se pierde, hay")
    print("   que volver a registrar el nodo, lo que invalida el anterior.")
    return 0


def dar_de_baja(node_id: str) -> int:
    """Revoca un nodo: su secreto deja de servir de inmediato.

    Es lo que hay que correr antes de registrar un nodo **distinto** en la misma
    sucursal —la guarda lo exige— y también cuando una PC se roba o se
    desafecta. No borra nada: el outbox y el histórico del nodo quedan.
    """
    from libraedge.db.repository import NodeRepository

    with _conexion() as conn:
        existe = conn.execute(
            "SELECT active FROM node_identity WHERE node_id = ?", (node_id,)
        ).fetchone()
        if existe is None:
            print(f"No hay ningún nodo {node_id!r}. Ver `estado` para la lista.")
            return 1
        if not existe[0]:
            print(f"El nodo {node_id!r} ya estaba dado de baja.")
            return 0
        NodeRepository(conn).deactivate_node(node_id)
        conn.commit()
    print(f"Nodo {node_id!r} dado de baja: su secreto deja de verificar.")
    return 0


def estado() -> int:
    """Qué hay publicado y qué nodos existen. Para comparar sin adivinar."""
    with _conexion() as conn:
        publicadas = conn.execute(
            "SELECT table_name, COUNT(*) FROM sync_changelog"
            " GROUP BY table_name ORDER BY table_name"
        ).fetchall()
        nodos = conn.execute(
            "SELECT node_id, branch_id, active, last_server_cursor,"
            " last_seen_at FROM node_identity ORDER BY node_id"
        ).fetchall()

    print("Tablas publicadas al changelog:")
    if not publicadas:
        print("  (ninguna — falta correr `publicar`)")
    for fila in publicadas:
        print(f"  {fila[0]}: {fila[1]} cambios")

    print()
    print("Nodos registrados:")
    if not nodos:
        print("  (ninguno — falta correr `registrar`)")
    for fila in nodos:
        activo = "activo" if fila[2] else "REVOCADO"
        visto = _hace_cuanto(fila[4])
        print(f"  {fila[0]} (sucursal {fila[1]}) — {activo}, cursor {fila[3] or 0},"
              f" visto {visto}")
    return 0


def _hace_cuanto(marca: str | None) -> str:
    """Texto corto para cuándo fue la última vez, o por qué no hay ninguna."""
    if not marca:
        return "NUNCA (registrado pero nunca sincronizó)"
    from datetime import datetime, timezone

    try:
        cuando = datetime.fromisoformat(marca)
    except ValueError:
        return f"fecha ilegible ({marca!r})"
    if cuando.tzinfo is None:
        cuando = cuando.replace(tzinfo=UTC)
    minutos = (datetime.now(UTC) - cuando).total_seconds() / 60
    if minutos < 2:
        return "recién"
    if minutos < 120:
        return f"hace {minutos:.0f} min"
    return f"hace {minutos / 60:.1f} h"


def vigilar(umbral_minutos: int) -> int:
    """Avisa qué nodos dejaron de hablar. **Sale con 1 si hay alguno.**

    🔴 El código de salida es el punto. Un comando que imprime lindo y siempre
    sale con 0 no es monitoreo: es un informe que hay que acordarse de leer, y
    nadie lee un log que casi siempre dice que todo está bien. Saliendo con 1
    lo puede usar el cron, un `healthcheck` o cualquier cosa que mire códigos.

    El umbral se pasa y no se adivina: depende del intervalo que tenga
    configurado cada instalación --por defecto el nodo cicla cada 60 s-- y este
    script no lo conoce. Un umbral de 15 minutos tolera quince ciclos perdidos.

    ⚠️ Un nodo silencioso NO significa ventas perdidas: el nodo sigue cobrando
    sin internet, y lo que cobró está en su outbox esperando. Significa que
    nadie sabe cuánto hay esperando ni desde cuándo, que es distinto y peor de
    lo que parece: el día que ese disco se rompa, recién ahí se cuenta.
    """
    with _conexion() as conn:
        nodos = conn.execute(
            "SELECT node_id, branch_id, active, last_seen_at"
            " FROM node_identity ORDER BY node_id"
        ).fetchall()

    if not nodos:
        print("No hay nodos registrados: no hay nada que vigilar.")
        return 0

    from datetime import datetime, timezone

    ahora = datetime.now(UTC)
    callados = []
    vigilados = 0
    for fila in nodos:
        node_id, sucursal, activo, visto = fila[0], fila[1], fila[2], fila[3]
        if not activo:
            print(f"  {node_id} (sucursal {sucursal}) — REVOCADO, no se vigila")
            continue
        vigilados += 1
        minutos = None
        if visto:
            try:
                cuando = datetime.fromisoformat(visto)
                if cuando.tzinfo is None:
                    cuando = cuando.replace(tzinfo=UTC)
                minutos = (ahora - cuando).total_seconds() / 60
            except ValueError:
                minutos = None
        if minutos is not None and minutos <= umbral_minutos:
            print(f"  {node_id} (sucursal {sucursal}) — al día, visto {_hace_cuanto(visto)}")
        else:
            callados.append((node_id, sucursal, visto))
            print(f"  {node_id} (sucursal {sucursal}) — SIN NOTICIAS, visto {_hace_cuanto(visto)}")

    if callados:
        print()
        print(f"{len(callados)} nodo(s) sin dar señales en {umbral_minutos} minutos.")
        print("Puede ser la conexión del local, la PC apagada o el servicio caído.")
        print("Lo cobrado sin internet sigue en el nodo; el problema es que nadie")
        print("sabe cuánto hay esperando ni desde cuándo.")
        return 1
    print()

    # 🔴 Se cuentan los VIGILADOS, no los registrados. Contaba `len(nodos)`, que
    # incluye a los revocados, así que al dar de baja el único nodo de la demo
    # —2026-08-31, con la PC apagada hacía 4 horas— el cron pasó a escribir cada
    # 10 minutos "El nodo dio señales dentro de los 15 minutos". Es un falso
    # verde de manual: la línea nombra justamente al nodo que no dio ninguna.
    if not vigilados:
        print("No hay nodos activos: todos los registrados están revocados.")
        return 0

    # Singular aparte: con un nodo la línea decía "Los 1 nodos dieron
    # señales", y esa línea es la que se repite cada 10 minutos en el log
    # del cron. La mayoría de los locales van a tener un nodo.
    sujeto = "El nodo dio" if vigilados == 1 else f"Los {vigilados} nodos dieron"
    print(f"{sujeto} señales dentro de los {umbral_minutos} minutos.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nodo_offline",
        description="Aprovisionamiento del nodo offline, del lado del central.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("publicar", help="instala los triggers y siembra la referencia")
    reg = sub.add_parser("registrar", help="da de alta un nodo y emite su secreto")
    reg.add_argument("node_id")
    reg.add_argument("--sucursal", default="principal")
    baja = sub.add_parser("dar-de-baja", help="revoca un nodo (PC robada o reemplazada)")
    baja.add_argument("node_id")
    sub.add_parser("estado", help="que hay publicado y que nodos existen")
    vig = sub.add_parser(
        "vigilar", help="sale con 1 si algun nodo dejo de dar senales")
    vig.add_argument("--umbral", type=int, default=15,
                     help="minutos sin noticias para darlo por callado")

    args = parser.parse_args(argv)
    if args.comando == "vigilar":
        return vigilar(args.umbral)
    if args.comando == "publicar":
        return publicar()
    if args.comando == "registrar":
        try:
            return registrar(args.node_id, args.sucursal)
        except SegundoNodoEnLaSucursal as choque:
            # Se imprime y se sale con 1 en vez de dejar el traceback: quien
            # corre esto está instalando en un local, y un stack trace no le
            # dice qué hacer. El mensaje sí.
            print(f"\nERROR: {choque}\n")
            return 1
    if args.comando == "dar-de-baja":
        return dar_de_baja(args.node_id)
    return estado()


if __name__ == "__main__":  # pragma: no cover - lo cubren los tests de abajo
    sys.exit(main())
