"""Log de actividad y de autenticación de Restolibra.

El dominio sigue siendo de LibraCore, pero `get_actividad_log` arma una
línea de tiempo unificada con un `UNION ALL` de 7 orígenes, y **dos de esos
orígenes (ventas y stock) leen tablas que en Restolibra ya no son la fuente
de verdad** desde P8: las ventas viven en `sales` y el stock en
`stock_movements` (ver `db_ventas.py` / `db_stock.py`).

Como las 7 partes se concatenan dentro de una sola función, no alcanza con
redefinir un fragmento: se redefine `get_actividad_log` entera acá, con las
otras cinco partes (caja, facturas, turnos, remitos, presupuestos) idénticas
a LibraCore. El resto del módulo (`registrar_auth_event`, `get_auth_log`,
`contar_login_fallidos_recientes`) se re-exporta tal cual. **LibraCore no se
toca**. Mismo patrón exacto que Contalibra (P7) — copia deliberada.
"""
from libracore.db.core import get_connection
from libracore.db.logs import (  # noqa: F401
    _LOG_TIPOS,
    registrar_auth_event,
    get_auth_log,
    contar_login_fallidos_recientes,
)


def get_actividad_log(tipos=None, usuario_id=None, turno_id=None,
                      desde="", hasta="", limit=200, offset=0) -> list[dict]:
    """
    Devuelve una línea de tiempo unificada de todos los movimientos del sistema.
    Cada fila: {fecha, tipo, descripcion, monto, usuario, turno_id, ref_id, ref_tabla}
    """
    partes = []

    # — Ventas — (sobre `sales`; el turno sale de `venta_links`)
    partes.append("""
        SELECT
            s.created_at AS ts,
            s.occurred_on AS fecha,
            'venta'       AS tipo,
            'Venta ' || s.number ||
              CASE WHEN s.customer_name_snapshot != ''
                   THEN ' — ' || s.customer_name_snapshot ELSE '' END
              || ' (' || COALESCE(s.status_detail, s.status) || ')'  AS descripcion,
            CAST(s.total AS REAL) AS monto,  -- ver nota del CAST en la parte de stock
            COALESCE(u.nombre, '')        AS usuario,
            vl.turno_id,
            s.id          AS ref_id,
            'ventas'      AS ref_tabla
        FROM sales s
        LEFT JOIN venta_links vl ON vl.venta_id = s.id
        LEFT JOIN usuarios u ON u.id = s.created_by
    """)

    # — Caja —
    partes.append("""
        SELECT
            cm.created_at AS ts,
            cm.fecha,
            'caja'        AS tipo,
            cm.tipo || ': ' || cm.concepto AS descripcion,
            cm.monto      AS monto,
            COALESCE(u.nombre, '') AS usuario,
            NULL          AS turno_id,
            cm.id         AS ref_id,
            'caja_movimientos' AS ref_tabla
        FROM caja_movimientos cm
        LEFT JOIN usuarios u ON u.id = cm.usuario_id
    """)

    # — Stock — (sobre `stock_movements`; el tipo original está en reason_code)
    partes.append("""
        SELECT
            sm.created_at AS ts,
            substr(sm.occurred_at, 1, 10) AS fecha,
            'stock'       AS tipo,
            COALESCE(sm.reason_code, sm.movement_type) || ' ' || ci.name ||
              -- Doble CAST a propósito: `quantity_delta` es NUMERIC y SQLite
              -- guarda "-3.0" como el entero -3, con lo que el texto quedaría
              -- "-3 kg" en vez del "-3.0 kg" que venía mostrando la versión
              -- sobre `movimientos_stock` (columna REAL). Se preserva el
              -- formato para no cambiar lo que se ve en pantalla.
              ' (' || CAST(CAST(sm.quantity_delta AS REAL) AS TEXT) || ' ' || ci.unit_code || ')'
              || CASE WHEN sm.note != '' THEN ' — ' || sm.note ELSE '' END
              AS descripcion,
            ABS(CAST(sm.quantity_delta AS REAL)) AS monto,
            COALESCE(u.nombre, '') AS usuario,
            NULL          AS turno_id,
            sm.id         AS ref_id,
            'movimientos_stock' AS ref_tabla
        FROM stock_movements sm
        JOIN catalog_items ci ON ci.id = sm.item_id
        LEFT JOIN usuarios u ON u.id = sm.created_by
    """)

    # — Facturas —
    partes.append("""
        SELECT
            f.created_at  AS ts,
            f.fecha,
            'factura'     AS tipo,
            'Factura tipo ' || f.tipo ||
              ' N° ' || printf('%04d', f.punto_venta) ||
              '-' || printf('%08d', f.numero) ||
              CASE WHEN f.cliente_razon IS NOT NULL AND f.cliente_razon != ''
                   THEN ' — ' || f.cliente_razon ELSE '' END
              AS descripcion,
            f.total       AS monto,
            COALESCE(u.nombre, '') AS usuario,
            NULL          AS turno_id,
            f.id          AS ref_id,
            'facturas'    AS ref_tabla
        FROM facturas f
        LEFT JOIN usuarios u ON u.id = f.usuario_id
    """)

    # — Turnos (apertura y cierre como eventos separados) —
    partes.append("""
        SELECT
            t.created_at  AS ts,
            -- `substr` y no `DATE()`: las otras ramas del UNION traen `fecha`
            -- como texto (`sales.occurred_on`, `remitos.date`,
            -- `presupuestos.date` y el `substr` de stock son todas columnas
            -- TEXT), y PostgreSQL exige que las ramas de un UNION tengan
            -- tipos compatibles: `DATE(t.apertura)` devuelve `date` y la
            -- consulta entera moria con "UNION types text and date cannot be
            -- matched" -- o sea, la pantalla de Logs no cargaba NADA. SQLite
            -- no chequea nada de esto y por eso la suite vieja lo dejaba
            -- pasar. `apertura` es texto ISO (`2026-05-26 23:50:59`), asi que
            -- los primeros 10 caracteres son la misma fecha que devolvia
            -- `DATE()`; verificado contra las bases reales antes de tocar.
            substr(t.apertura, 1, 10) AS fecha,
            'turno'       AS tipo,
            CASE t.estado
              WHEN 'abierto' THEN 'Turno #' || t.id || ' abierto — fondo $' || t.monto_inicial
              ELSE 'Turno #' || t.id || ' cerrado — declarado $' ||
                   COALESCE(CAST(t.monto_declarado_cierre AS TEXT), '0')
            END           AS descripcion,
            t.monto_inicial AS monto,
            COALESCE(u.nombre, '') AS usuario,
            t.id          AS turno_id,
            t.id          AS ref_id,
            'turnos_caja' AS ref_tabla
        FROM turnos_caja t
        JOIN usuarios u ON u.id = t.usuario_id
    """)

    # — Remitos —
    partes.append("""
        SELECT
            r.created_at  AS ts,
            r.date        AS fecha,
            'remito'      AS tipo,
            'Remito ' || r.number || ' — ' || r.client_name AS descripcion,
            r.total       AS monto,
            COALESCE(u.nombre, '') AS usuario,
            NULL          AS turno_id,
            r.id          AS ref_id,
            'remitos'     AS ref_tabla
        FROM remitos r
        LEFT JOIN usuarios u ON u.id = r.usuario_id
    """)

    # — Presupuestos —
    partes.append("""
        SELECT
            p.created_at  AS ts,
            p.date        AS fecha,
            'presupuesto' AS tipo,
            'Presupuesto ' || p.number || ' — ' || p.client_name ||
              ' (' || p.status || ')' AS descripcion,
            p.total       AS monto,
            COALESCE(u.nombre, '') AS usuario,
            NULL          AS turno_id,
            p.id          AS ref_id,
            'presupuestos' AS ref_tabla
        FROM presupuestos p
        LEFT JOIN usuarios u ON u.id = p.usuario_id
    """)

    # ── filtros post-UNION ──────────────────────────────────────────────────────
    where, params = [], []

    if tipos:
        marks = ",".join("?" * len(tipos))
        where.append(f"tipo IN ({marks})")
        params.extend(tipos)

    if desde:
        where.append("fecha >= ?"); params.append(desde)
    if hasta:
        where.append("fecha <= ?"); params.append(hasta)
    if turno_id:
        where.append("turno_id = ?"); params.append(turno_id)

    union_sql = "\nUNION ALL\n".join(partes)

    # Para filtrar por usuario necesitamos un wrapper con un JOIN auxiliar
    if usuario_id:
        sql = f"""
            SELECT * FROM (
                {union_sql}
            ) sub
            WHERE usuario = (SELECT nombre FROM usuarios WHERE id=?)
        """
        params_final = [usuario_id] + params
        if where:
            sql += " AND " + " AND ".join(where)
    else:
        sql = f"""
            SELECT * FROM (
                {union_sql}
            ) sub
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        params_final = params

    sql += " ORDER BY ts DESC, ref_id DESC LIMIT ? OFFSET ?"
    params_final += [limit, offset]

    with get_connection() as conn:
        rows = conn.execute(sql, params_final).fetchall()
    return [dict(r) for r in rows]


def get_actividad_count(tipos=None, usuario_id=None, turno_id=None,
                        desde="", hasta="") -> int:
    """Cuenta total de filas para paginación."""
    rows = get_actividad_log(tipos=tipos, usuario_id=usuario_id, turno_id=turno_id,
                             desde=desde, hasta=hasta, limit=10000, offset=0)
    return len(rows)
