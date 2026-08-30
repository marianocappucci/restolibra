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
    "clients", "modulos", "usuarios", "productos", "categorias_producto",
    "listas_precio", "lista_precio_items", "proveedores", "cuentas_tesoreria",
    "cajas",
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
    from libraedge.db.changelog import instalar_trigger, sembrar

    publicadas = []
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
                print(f"  {tabla}: SALTEADA — sin PK de una sola columna, el "
                      f"espejo del nodo no podría aplicarla")
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
        conn.commit()
    print(f"Publicadas {len(publicadas)} de {len(presentes)} tablas presentes.")
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


def registrar(node_id: str, branch_id: str) -> int:
    """Da de alta el nodo y **muestra su secreto una sola vez**.

    Sólo se persiste el hash: no hay forma de recuperarlo después. Re-registrar
    el mismo `node_id` emite uno nuevo e invalida el anterior — que es cómo se
    reemplaza una PC robada o dada de baja.
    """
    from libraedge.db.repository import NodeRepository

    with _conexion() as conn:
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


def estado() -> int:
    """Qué hay publicado y qué nodos existen. Para comparar sin adivinar."""
    with _conexion() as conn:
        publicadas = conn.execute(
            "SELECT table_name, COUNT(*) FROM sync_changelog"
            " GROUP BY table_name ORDER BY table_name"
        ).fetchall()
        nodos = conn.execute(
            "SELECT node_id, branch_id, active, last_server_cursor"
            " FROM node_identity ORDER BY node_id"
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
        print(f"  {fila[0]} (sucursal {fila[1]}) — {activo}, cursor {fila[3] or 0}")
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
    sub.add_parser("estado", help="que hay publicado y que nodos existen")

    args = parser.parse_args(argv)
    if args.comando == "publicar":
        return publicar()
    if args.comando == "registrar":
        return registrar(args.node_id, args.sucursal)
    return estado()


if __name__ == "__main__":  # pragma: no cover - lo cubren los tests de abajo
    sys.exit(main())
