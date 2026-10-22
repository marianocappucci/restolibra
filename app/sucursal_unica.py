"""La sucursal única de Restolibra («Casa central»): lo que el producto aporta al sustrato de sucursales del motor.

Restolibra es de un solo local, pero el motor (`libracommerce`) ya sabe de sucursales: el depósito pertenece a una,
la venta anota la del depósito del que sale, la caja (`cajas.sucursal_id`, de LibraCore) también. Hasta ahora todo
eso quedaba en NULL, y desde libraedge v0.20.0 (`validar_registro=depositos_sin_sucursal`) un depósito activo sin
sucursal impide vincular la PC del local. Esto las junta en **una** sucursal predeterminada (decisión del humano,
2026-10-22: sucursal única, como Contalibra). **Nada visible cambia** con una sola sucursal: ninguna pantalla ni ruta
de sucursales se monta (`/api/sucursales` sigue sin existir) y el kit sólo ofrece sucursal con dos o más.

La lógica de fondo es del motor (ADR-063 de libracommerce): `catalogo.adoptar_sucursal_unica` y
`catalogo.completar_sucursal_de_ventas`. Acá queda lo propio del producto: el nombre, las cajas (que son de
LibraCore, no del motor comercial) y el camino de vuelta.

**La misma función en las dos puntas**, como el resto de las tablas propias de la cadena: la revisión de Alembic
`0007_sucursal_unica` (el deploy de una instancia que ya existe) y `init_db()` (el alta de una instancia nueva y cada
reinicio) llaman a `adoptar`. Una instancia nueva y una vieja convergen por el mismo camino, y correrla dos veces no
hace nada la segunda.
"""
from __future__ import annotations

from typing import Any

#: El nombre de la sucursal única (decisión del humano, 2026-10-16).
NOMBRE = "Casa central"


def sucursal_predeterminada() -> int | None:
    """El id de la sucursal predeterminada («Casa central»), o `None` si la instancia todavía no tiene ninguna.

    Es el `OpcionesCajas.sucursal_por_defecto` de libracore (ADR-062): una caja creada por `POST /api/cajas` sin
    `sucursal_id` nace en ella y no queda en NULL hasta el próximo arranque. Abre su propia conexión (el motor la
    llama sin argumentos) y lee con la función del motor comercial, la misma que usa el router de depósitos."""
    from libracommerce.erp import catalogo

    from app.db_core import get_connection

    with get_connection() as conn:
        return catalogo.get_default_sucursal_id(conn)


def adoptar(conn: Any) -> dict:
    """Deja la instancia con su sucursal única y devuelve un informe de lo que hizo (todo en cero si no había nada).

    1. La sucursal predeterminada «Casa central» (la crea si no hay ninguna) y todos los depósitos bajo ella.
    2. Las cajas sin sucursal pasan a ella. Una caja que ya tiene una no se toca.
    3. Las ventas de antes se completan con la sucursal de su depósito, con el criterio de `erp.margen`.

    **Una instancia que ya tiene sucursales propias no se toca** (a diferencia de Contalibra, que nunca tuvo ninguna):
    Restolibra no monta el router de sucursales, pero hasta libraedge v0.20.0 soporte las creaba a mano para vincular un
    nodo. Con dos o más sucursales, o con una sola que no es la predeterminada, no hay «la» sucursal única que adoptar y
    elegir una es del dueño de los datos, no de un arranque (el motor, además, levanta `ValueError`: tirar `init_db()`
    dejaría la instancia sin arrancar). No se asigna ningún depósito ni caja y el informe trae `omitida` con el motivo.

    No commitea: es del caller. Serializada entre procesos por el candado del motor (va primero)."""
    from libracommerce.db.candado import serializar_esquema
    from libracommerce.erp import catalogo

    serializar_esquema(conn)  # primero: lo que se decide abajo (cuántas sucursales hay) se lee ya con el candado tomado
    sucursales_antes, predeterminadas = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(CASE WHEN is_default = 1 THEN 1 ELSE 0 END), 0) FROM branches"
    ).fetchone()
    if sucursales_antes > 1 or (sucursales_antes == 1 and not predeterminadas):
        return {
            "sucursal_id": catalogo.get_default_sucursal_id(conn),
            "sucursal_creada": False,
            "depositos_asignados": 0,
            "cajas_asignadas": 0,
            "ventas_completadas": 0,
            "omitida": f"la instancia ya tiene {sucursales_antes} sucursal(es) propia(s) y no hay una única que adoptar",
        }
    huerfanos_antes = conn.execute("SELECT COUNT(*) FROM locations WHERE branch_id IS NULL").fetchone()[0]
    sucursal_id = catalogo.adoptar_sucursal_unica(conn, NOMBRE)
    cajas = conn.execute("UPDATE cajas SET sucursal_id = ? WHERE sucursal_id IS NULL", (sucursal_id,)).rowcount or 0
    ventas = catalogo.completar_sucursal_de_ventas(conn)
    return {
        "sucursal_id": sucursal_id,
        "sucursal_creada": sucursales_antes == 0,
        "depositos_asignados": huerfanos_antes,
        "cajas_asignadas": cajas,
        "ventas_completadas": ventas,
        "omitida": None,
    }


def desadoptar(conn: Any) -> dict:
    """El camino de vuelta de `adoptar` (el `downgrade` de la revisión `0007`): deja en NULL todo lo que apuntaba a la
    sucursal única y la borra.

    🔴 **Sólo si es la que `adoptar` creó, y se identifica por la forma que dejó**: la ÚNICA sucursal de la instancia,
    la predeterminada, con el nombre `NOMBRE`. Si hay más de una (se activó multisucursal después), o la única fue
    renombrada o no es la predeterminada, ya no es «la de la migración»: no se toca nada y se dice por qué
    (`RuntimeError`). Tampoco se baja si algún precio (`item_prices`) u orden de compra (`purchase_orders`) apunta a
    ella: dejarlos en NULL volvería general un precio que es de una sucursal, y borrarla dejaría la referencia colgando.

    Sin sucursales, no hace nada (una base que nunca la adoptó)."""
    filas = conn.execute("SELECT id, name, is_default FROM branches ORDER BY id").fetchall()
    if not filas:
        return {"sucursal_id": None, "depositos": 0, "cajas": 0, "ventas": 0}
    if len(filas) != 1 or not filas[0][2] or filas[0][1] != NOMBRE:
        raise RuntimeError(
            f"No se puede deshacer la sucursal única: la instancia no tiene sólo «{NOMBRE}» como sucursal "
            f"predeterminada (hay {len(filas)}: {[(f[0], f[1]) for f in filas]}). Con más sucursales, o con una "
            "renombrada, deshacerlo borraría datos que ya no son de la migración."
        )
    sucursal_id = filas[0][0]
    for tabla in ("item_prices", "purchase_orders"):
        n = conn.execute(f"SELECT COUNT(*) FROM {tabla} WHERE branch_id = ?", (sucursal_id,)).fetchone()[0]
        if n:
            raise RuntimeError(
                f"No se puede deshacer la sucursal única: {n} fila(s) de {tabla} apuntan a ella "
                f"(branch_id={sucursal_id}). Dejarlas sin sucursal cambiaría lo que significan."
            )
    informe = {"sucursal_id": sucursal_id}
    for clave, sql in (
        ("depositos", "UPDATE locations SET branch_id = NULL WHERE branch_id = ?"),
        ("cajas", "UPDATE cajas SET sucursal_id = NULL WHERE sucursal_id = ?"),
        ("ventas", "UPDATE sales SET branch_id = NULL WHERE branch_id = ?"),
    ):
        informe[clave] = conn.execute(sql, (sucursal_id,)).rowcount or 0
    conn.execute("DELETE FROM branches WHERE id = ?", (sucursal_id,))
    return informe
