"""
Reportes del módulo restaurant: ventas por canal y tiempos de comanda por
estación. Dominio propio de Restolibra, sin equivalente en Contalibra.

`reporte_gastronomia` hace JOIN contra `ventas`, que en Restolibra ya no es
la fuente de verdad desde P8: las ventas viven en `sales` de LibraCommerce
(ver `db_ventas.py`) — `pedidos.venta_id` sigue apuntando al mismo ID
(preservado 1:1 por la migración), solo cambia la tabla/columnas de origen
(`v.fecha` -> `v.occurred_on`).

🔴 **El SQL de acá es de PostgreSQL y de nada más.** Hasta el 2026-09-01 los
tiempos de comanda se calculaban con `julianday`, que es una función de
SQLite: contra el motor real la consulta muere con `UndefinedFunction` y se
lleva puestas las DOS pantallas que llaman a esta función --
`/api/salon/reportes` (Reportes de salón) y `/api/dashboard`, que la usa para
`rep_hoy`. Sobrevivió al corte a PostgreSQL del 2026-08-10 porque ningún test
la tocaba: el guard del conftest elige el motor, pero no ejercita lo que nadie
llama. Ver `tests/test_reportes_gastronomicos.py`, que además deja un guard
sobre el fuente para que no vuelva a entrar por otro módulo -- por eso el
nombre se menciona acá SIN paréntesis: el guard busca la llamada.
"""
from app.db_core import get_connection

#: Canal sintético de las ventas que NO nacieron de un pedido: el POS de
#: mostrador clásico (`/ventas`, módulo `ventas`), que escribe derecho en
#: `sales` sin pasar por mesa ni comanda. No es un valor de `pedidos.canal`
#: --los reales son salon/barra/takeaway/delivery-- y por eso se arma aparte:
#: sin esta fila el reporte de salón mostraba MENOS que la caja del día y
#: nada lo avisaba.
CANAL_MOSTRADOR = "mostrador"


def reporte_gastronomia(desde: str, hasta: str) -> dict:
    """Métricas del módulo restaurant en [desde, hasta] (fechas 'YYYY-MM-DD'):
    - Ventas por canal (pedidos cobrados) más el mostrador (ventas sin pedido):
      cantidad, total, ticket promedio.
    - Tiempos de comanda por estación (minutos): espera, preparación y total, sobre las
      comandas que llegaron a 'listo' en el período.

    Las ventas anuladas (`sales.status = 'cancelled'`) quedan afuera de los dos
    lados. Importa sobre todo del lado de mesa: `anular_venta()` marca la venta
    y NO toca el pedido, que sigue en 'cobrado' -- sin este filtro una anulación
    seguía sumando al total de su canal.
    """
    ini, fin = desde + " 00:00:00", hasta + " 23:59:59"
    with get_connection() as conn:
        canales = [{
            "canal": r["canal"],
            "n": r["n"],
            "total": float(r["total"]),
        } for r in conn.execute(
            """SELECT p.canal AS canal, COUNT(*) AS n,
                      COALESCE(SUM(v.total), 0) AS total
               FROM pedidos p JOIN sales v ON v.id = p.venta_id
               WHERE p.estado = 'cobrado' AND v.status <> 'cancelled'
                     AND v.occurred_on >= ? AND v.occurred_on <= ?
               GROUP BY p.canal""",
            (desde, hasta),
        ).fetchall()]

        # El mostrador sale de la MISMA tabla, mirado desde adentro: una venta
        # sin `pedidos` que la apunte no nació del salón. `NOT EXISTS` y no un
        # LEFT JOIN + IS NULL porque `pedidos.venta_id` no es única por schema.
        mostrador = conn.execute(
            """SELECT COUNT(*) AS n, COALESCE(SUM(v.total), 0) AS total
               FROM sales v
               WHERE v.status <> 'cancelled'
                     AND v.occurred_on >= ? AND v.occurred_on <= ?
                     AND NOT EXISTS (SELECT 1 FROM pedidos p WHERE p.venta_id = v.id)""",
            (desde, hasta),
        ).fetchone()
        if mostrador["n"]:
            canales.append({
                "canal": CANAL_MOSTRADOR,
                "n": mostrador["n"],
                "total": float(mostrador["total"]),
            })

        # El orden por total lo hacía el `ORDER BY` de la consulta de canales;
        # con la fila del mostrador agregada después, ordenar acá es lo único
        # que deja a las dos en una sola lista ordenada.
        canales.sort(key=lambda c: c["total"], reverse=True)
        for c in canales:
            c["ticket"] = round(c["total"] / c["n"], 2) if c["n"] else 0.0

        tiempos = [dict(r) for r in conn.execute(
            """SELECT estacion,
                      COUNT(*) AS n,
                      AVG(EXTRACT(EPOCH FROM (preparacion_at::timestamp - created_at::timestamp)) / 60) AS espera_min,
                      AVG(EXTRACT(EPOCH FROM (listo_at::timestamp - preparacion_at::timestamp)) / 60) AS prep_min,
                      AVG(EXTRACT(EPOCH FROM (listo_at::timestamp - created_at::timestamp)) / 60) AS total_min
               FROM comandas
               WHERE listo_at IS NOT NULL AND created_at >= ? AND created_at <= ?
               GROUP BY estacion
               ORDER BY estacion""",
            (ini, fin),
        ).fetchall()]
        for t in tiempos:
            for k in ("espera_min", "prep_min", "total_min"):
                # `EXTRACT(EPOCH ...)` devuelve numeric: sin el float() estos
                # tres viajan como Decimal y el JSON de la SPA queda atado a
                # que el encoder de FastAPI los traduzca.
                t[k] = round(float(t[k]), 1) if t[k] is not None else None
    return {
        "desde": desde, "hasta": hasta,
        "canales": canales,
        "total_n": sum(c["n"] for c in canales),
        "total_total": round(sum(c["total"] for c in canales), 2),
        "tiempos": tiempos,
    }
