import os

# Infraestructura compartida y módulos por dominio, extraídos de este archivo
# como parte del split en módulos lógicos (Fase 3 de LibraCore, sub-paso
# previo dentro de cada producto, sin cambiar comportamiento — ver
# wiki/entities/libracore.md). Re-exportados acá para que los call sites
# existentes (`db.get_connection()`, `db.DB_PATH`, `db.create_usuario(...)`,
# etc.) no cambien una línea.
from libracore.db.schema import init_core_schema
from libracommerce.db.schema import init_schema as init_commerce_schema
from db_core import _AR_TZ, _ar_now, _DATA_DIR, DB_PATH, get_connection, minutos_desde  # noqa: F401
from db_usuarios import (  # noqa: F401
    _hash_password,
    _verify_password,
    _DUMMY_PASSWORD_HASH,
    create_usuario,
    get_usuario_by_username,
    get_usuario_by_id,
    get_all_usuarios,
    update_usuario,
    update_usuario_password,
    delete_usuario,
    check_usuario_credentials,
    ensure_admin_user,
)
from db_tesoreria import (  # noqa: F401
    get_all_cuentas_tesoreria,
    get_cuenta_tesoreria,
    create_cuenta_tesoreria,
    update_cuenta_tesoreria,
    delete_cuenta_tesoreria,
    get_movimientos_tesoreria,
    create_movimiento_tesoreria,
    create_transferencia_tesoreria,
    delete_movimiento_tesoreria,
    get_resumen_tesoreria,
)
from db_caja import (  # noqa: F401
    MEDIOS_PAGO_LABELS,
    get_all_cajas,
    get_caja_config,
    get_default_caja_id,
    create_caja_config,
    update_caja_config,
    set_default_caja,
    delete_caja_config,
    create_caja_movimiento,
    get_caja_movimientos,
    get_caja_resumen,
    get_cobro_factura,
    get_cobros_factura,
    delete_caja_movimiento,
)
from db_egresos import (  # noqa: F401
    get_categorias_egreso,
    create_categoria_egreso,
    delete_categoria_egreso,
    get_all_proveedores,
    get_proveedor,
    search_proveedores,
    create_proveedor,
    update_proveedor,
    delete_proveedor,
    create_egreso,
    get_egreso,
    get_all_egresos,
    get_resumen_egresos,
    delete_egreso,
    get_pagos_egreso,
    create_pago_egreso,
)
from db_modulos import get_modulos, apply_plan  # noqa: F401
from db_listas_precio import (  # noqa: F401
    get_all_listas_precio,
    get_lista_precio,
    create_lista_precio,
    update_lista_precio,
    delete_lista_precio,
    get_lista_precio_items,
    get_precio_en_lista,
    get_precios_lista_dict,
    save_lista_precio_items,
    apply_porcentaje_lista,
    importar_precios_lista,
)
from db_turnos import (  # noqa: F401
    create_turno,
    get_turno_activo,
    get_turno_activo_any,
    get_all_turnos,
    get_turno,
    get_resumen_turno,
    cerrar_turno,
    vincular_venta_turno,
)
from db_dashboard import get_dashboard_data  # noqa: F401
from db_logs import (  # noqa: F401
    get_actividad_log,
    get_actividad_count,
    registrar_auth_event,
    get_auth_log,
    contar_login_fallidos_recientes,
)
from db_arca_config import (  # noqa: F401
    crear_arca_config,
    obtener_arca_config,
    obtener_todas_arca_configs,
    actualizar_arca_config,
    eliminar_arca_config,
)
from db_cuenta_corriente import (  # noqa: F401
    get_cc_saldo,
    get_cc_movimientos,
    get_clientes_con_saldo_cc,
    create_cc_pago,
    delete_cc_pago,
)
from db_libros_iva import get_facturas_para_iva, get_egresos_para_iva  # noqa: F401
from db_reportes import (  # noqa: F401
    get_reporte_ventas,
    get_reporte_medios_pago,
    get_reporte_productos_top,
    get_reporte_caja,
    get_reporte_caja_medios,
    get_reporte_stock_bajo,
    get_reporte_resumen,
)
from db_productos import (  # noqa: F401
    get_all_depositos,
    get_deposito,
    get_default_deposito_id,
    create_deposito,
    update_deposito,
    set_default_deposito,
    delete_deposito,
    get_stock_por_deposito,
    get_stock_producto_todos_depositos,
    transferir_stock,
    get_categorias_producto,
    create_categoria_producto,
    delete_categoria_producto,
    create_producto,
    generar_codigo_producto,
    get_all_productos,
    get_producto,
    get_producto_by_codigo,
    update_producto,
    delete_producto,
)
from db_recetas import (  # noqa: F401
    get_receta,
    guardar_receta,
    eliminar_receta,
    producir_receta,
    costo_receta,
    food_cost_pct,
    get_reporte_food_cost,
    get_consumo_insumos,
)
from db_stock import (  # noqa: F401
    add_movimiento_stock,
    get_stock_actual,
    get_stock_todos,
    get_movimientos_stock,
    ajustar_stock,
    descontar_stock_venta,
    _parse_modificadores,
    _resumen_modificadores,
)
from db_clients import (  # noqa: F401
    create_client,
    get_all_clients,
    get_all_clients_including_inactive,
    get_client,
    desactivar_cliente,
    activar_cliente,
    tiene_presupuestos_aprobados,
    get_facturas_by_client,
    update_client,
    toggle_auto_facturar,
    delete_client,
    get_client_by_email,
    get_client_by_cuit,
)
from db_remitos_presupuestos import (  # noqa: F401
    get_next_remito_number,
    create_remito,
    update_remito_pdf_path,
    get_all_remitos,
    get_remito,
    get_remitos_by_client,
    search_remitos,
    get_next_presupuesto_number,
    auto_vencimiento_presupuestos,
    create_presupuesto,
    update_presupuesto_pdf_path,
    update_presupuesto_status,
    update_presupuesto_remito_id,
    get_all_presupuestos,
    get_presupuestos_count_by_estado,
    get_presupuesto,
    get_presupuestos_by_client,
    search_presupuestos,
    delete_remito,
    delete_presupuesto,
    update_remito,
    update_presupuesto,
)
from db_facturas import (  # noqa: F401
    get_next_factura_numero,
    create_factura,
    get_all_facturas,
    get_facturas_filtradas,
    get_factura,
    update_factura_cae,
    update_factura_pdf_path,
    search_facturas,
    get_notas_de_factura,
    get_nc_de_factura,
    get_nd_de_factura,
    get_factura_por_tipo_pv_nro,
    delete_factura,
)
from db_mp import (  # noqa: F401
    get_mp_pago,
    create_mp_pago,
    get_mp_pago_by_id,
    get_mp_pagos_by_estado,
    get_mp_pagos_historial,
    update_mp_pago_estado,
    crear_alias_facturacion,
    get_alias_facturacion_by_cliente,
    eliminar_alias_facturacion,
    get_mp_movimiento_by_mp_id,
    create_mp_movimiento,
    get_mp_movimiento_by_id,
    get_mp_movimientos_by_estado,
    get_mp_movimientos_historial,
    update_mp_movimiento_datos,
    update_mp_movimiento_estado,
    get_mp_pending_count,
    vincular_mp_pago_cliente,
)
from db_ventas import (  # noqa: F401
    get_next_venta_numero,
    create_venta,
    add_venta_pago,
    crear_venta_directa,
    get_all_ventas,
    get_venta,
    anular_venta,
    vincular_venta_factura,
    vincular_venta_remito,
    set_venta_mp_order,
    set_venta_mp_payment,
    get_venta_by_mp_order,
    add_venta_pago_referencia_mp,
)
from db_salones import (  # noqa: F401
    get_salones,
    get_salon,
    create_salon,
    update_salon,
    delete_salon,
)
from db_reservas import (  # noqa: F401
    get_reservas,
    get_reserva,
    get_proximas_reservas_por_mesa,
    RESERVA_BUFFER_MINUTOS,
    crear_reserva,
    cancelar_reserva,
    cumplir_reserva,
)
from db_pedidos import (  # noqa: F401
    get_next_pedido_numero,
    crear_pedido,
    get_pedidos_activos,
    get_pedido_items,
    pedido_total,
    get_pedido,
    get_pedido_abierto_de_mesa,
    add_pedido_item,
    delete_pedido_item,
    set_pedido_item_nota,
    anular_pedido,
)
from db_mesas import (  # noqa: F401
    get_mesas,
    get_mesa,
    create_mesa,
    update_mesa,
    set_mesa_estado,
    delete_mesa,
    resumen_salon_ahora,
)
from db_comandas import (  # noqa: F401
    ESTACIONES,
    COMANDA_ESTADOS,
    enviar_a_estaciones,
    get_comanda,
    get_comandas_estacion,
    set_comanda_estado,
    avanzar_comanda,
)
from db_cobro_pedido import cobrar_pedido  # noqa: F401
from db_reportes_gastronomicos import reporte_gastronomia  # noqa: F401

# Antes de P8, descontar_stock_venta (libracore.db.stock) era receta-aware
# vía un hook inyectado acá (configure_resolver_receta), para no acoplar
# LibraCore a un dominio de producto específico. Desde P8, db_stock.py es
# implementación propia de Restolibra y llama a db_recetas.get_receta()
# directo — el hook ya no se usa y LibraCore no se toca.


def init_db():
    with get_connection() as conn:
        init_core_schema(conn)
        # Catálogo/stock/ventas viven en las tablas de LibraCommerce desde
        # P8 (ver db_productos.py). Conviven en el MISMO archivo SQLite que
        # el resto de Restolibra, a propósito: `crear_venta_directa`/
        # `cobrar_pedido` cruzan ambos motores en una única transacción
        # atómica. Mismo patrón que Contalibra (P7).
        init_commerce_schema(conn)

        # Referencias cruzadas entre la venta (LibraCommerce) y contextos que
        # no son suyos: facturación/remitos y turno de caja (LibraCore) y
        # MercadoPago. No van dentro de `sales` para no meter dominio ajeno en
        # el motor genérico — ver db_ventas.py.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS venta_links (
                venta_id      INTEGER PRIMARY KEY REFERENCES sales(id) ON DELETE CASCADE,
                factura_id    INTEGER REFERENCES facturas(id) ON DELETE SET NULL,
                remito_id     INTEGER REFERENCES remitos(id) ON DELETE SET NULL,
                turno_id      INTEGER REFERENCES turnos_caja(id) ON DELETE SET NULL,
                mp_order_id   TEXT DEFAULT '',
                mp_payment_id TEXT DEFAULT ''
            )
        """)

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS recetas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id     INTEGER NOT NULL UNIQUE REFERENCES catalog_items(id) ON DELETE CASCADE,
                rinde           REAL NOT NULL DEFAULT 1,
                rinde_unidad    TEXT NOT NULL DEFAULT 'u',
                rendimiento_pct REAL NOT NULL DEFAULT 100,
                activo          INTEGER NOT NULL DEFAULT 1,
                notas           TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS receta_items (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                receta_id      INTEGER NOT NULL REFERENCES recetas(id) ON DELETE CASCADE,
                ingrediente_id INTEGER NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
                cantidad       REAL NOT NULL DEFAULT 0,
                created_at     TEXT DEFAULT (datetime('now'))
            );

            -- ─────────────── Módulo Restaurant (salón / comandas) ───────────────
            CREATE TABLE IF NOT EXISTS salones (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                orden  INTEGER NOT NULL DEFAULT 0,
                activo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS mesas (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                salon_id   INTEGER NOT NULL REFERENCES salones(id) ON DELETE CASCADE,
                nombre     TEXT NOT NULL,
                capacidad  INTEGER NOT NULL DEFAULT 4,
                orden      INTEGER NOT NULL DEFAULT 0,
                estado     TEXT NOT NULL DEFAULT 'libre',    -- libre | ocupada | cuenta
                activo     INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS pedidos (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                numero         TEXT NOT NULL,
                canal          TEXT NOT NULL DEFAULT 'salon', -- salon | barra | takeaway | delivery
                mesa_id        INTEGER REFERENCES mesas(id) ON DELETE SET NULL,
                estado         TEXT NOT NULL DEFAULT 'abierto', -- abierto | cobrado | anulado
                comensales     INTEGER NOT NULL DEFAULT 1,
                usuario_id     INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
                cliente_id     INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                cliente_nombre TEXT DEFAULT '',
                direccion      TEXT DEFAULT '',
                telefono       TEXT DEFAULT '',
                repartidor     TEXT DEFAULT '',
                costo_envio    REAL NOT NULL DEFAULT 0,
                hora_retiro    TEXT DEFAULT '',
                observaciones  TEXT DEFAULT '',
                venta_id       INTEGER REFERENCES sales(id) ON DELETE SET NULL,
                created_at     TEXT DEFAULT (datetime('now')),
                updated_at     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS comandas (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id      INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                estacion       TEXT NOT NULL,                     -- cocina | barra
                numero         INTEGER NOT NULL DEFAULT 0,        -- ronda dentro del pedido
                estado         TEXT NOT NULL DEFAULT 'pendiente', -- pendiente | preparacion | listo | entregado
                preparacion_at TEXT,                              -- timestamps de transición (tiempos)
                listo_at       TEXT,
                entregado_at   TEXT,
                created_at     TEXT DEFAULT (datetime('now')),
                updated_at     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS pedido_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id   INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
                comanda_id  INTEGER REFERENCES comandas(id) ON DELETE SET NULL,
                producto_id INTEGER REFERENCES productos(id) ON DELETE SET NULL,
                nombre      TEXT NOT NULL,
                qty         REAL NOT NULL DEFAULT 1,
                precio      REAL NOT NULL DEFAULT 0,
                subtotal    REAL NOT NULL DEFAULT 0,
                estacion    TEXT DEFAULT '',                  -- cocina | barra | '' (sin comanda)
                nota        TEXT DEFAULT '',
                estado      TEXT NOT NULL DEFAULT 'nuevo',     -- nuevo | enviado | anulado
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS reservas (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                mesa_id        INTEGER NOT NULL REFERENCES mesas(id) ON DELETE CASCADE,
                fecha          TEXT NOT NULL,                  -- YYYY-MM-DD
                hora           TEXT NOT NULL,                  -- HH:MM
                cliente_nombre TEXT NOT NULL DEFAULT '',
                telefono       TEXT DEFAULT '',
                comensales     INTEGER NOT NULL DEFAULT 1,
                notas          TEXT DEFAULT '',
                estado         TEXT NOT NULL DEFAULT 'pendiente', -- pendiente | cumplida | cancelada
                created_at     TEXT DEFAULT (datetime('now'))
            );
        """)
        # Índices — agregados en la auditoría 2026-07-12 (wiki/analyses/restolibra-auditoria-produccion).
        # Antes de crear el índice único de "una mesa, un pedido abierto", limpiamos
        # cualquier duplicado que ya exista (ej. de la condición de carrera que este
        # mismo índice viene a prevenir) para no romper el arranque de la app.
        dups = conn.execute("""
            SELECT mesa_id FROM pedidos WHERE estado='abierto' AND mesa_id IS NOT NULL
            GROUP BY mesa_id HAVING COUNT(*) > 1
        """).fetchall()
        for d in dups:
            rows = conn.execute(
                "SELECT id FROM pedidos WHERE mesa_id=? AND estado='abierto' ORDER BY id DESC",
                (d["mesa_id"],),
            ).fetchall()
            for old in rows[1:]:
                conn.execute(
                    "UPDATE pedidos SET estado='abierto_duplicado', updated_at=? WHERE id=?",
                    (_ar_now(), old["id"]),
                )
        conn.executescript("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_pedido_mesa_abierta
                ON pedidos(mesa_id) WHERE estado='abierto';
            CREATE INDEX IF NOT EXISTS idx_pedidos_estado ON pedidos(estado);
            CREATE INDEX IF NOT EXISTS idx_comandas_estacion_estado ON comandas(estacion, estado);
            CREATE INDEX IF NOT EXISTS idx_pedido_items_pedido ON pedido_items(pedido_id);
            CREATE INDEX IF NOT EXISTS idx_pedido_items_comanda ON pedido_items(comanda_id);
            CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha);
            CREATE INDEX IF NOT EXISTS idx_caja_movimientos_fecha ON caja_movimientos(fecha);
        """)
        # Migraciones específicas del módulo restaurant (tablas de extensión,
        # no cubiertas por libracore.db.schema.init_core_schema).
        ped_cols = [r[1] for r in conn.execute("PRAGMA table_info(pedidos)").fetchall()]
        if ped_cols and "hora_retiro" not in ped_cols:
            conn.execute("ALTER TABLE pedidos ADD COLUMN hora_retiro TEXT DEFAULT ''")
        com_cols = [r[1] for r in conn.execute("PRAGMA table_info(comandas)").fetchall()]
        for _col in ("preparacion_at", "listo_at", "entregado_at"):
            if com_cols and _col not in com_cols:
                conn.execute(f"ALTER TABLE comandas ADD COLUMN {_col} TEXT")
        pi_cols = [r[1] for r in conn.execute("PRAGMA table_info(pedido_items)").fetchall()]
        if pi_cols and "modificadores" not in pi_cols:
            conn.execute("ALTER TABLE pedido_items ADD COLUMN modificadores TEXT DEFAULT ''")

        # Seed de módulos: inserta sólo los que no existen aún
        _MODULOS_DEFAULT = [
            ("clientes",      1, "basico"),
            ("caja",          1, "basico"),
            ("cajas",         1, "basico"),
            ("ventas",        1, "basico"),
            ("facturacion",   1, "estandar"),
            ("remitos",       1, "estandar"),
            ("presupuestos",  1, "estandar"),
            ("productos",     1, "estandar"),
            ("stock",         1, "premium"),
            ("depositos",     1, "premium"),
            ("reportes",      1, "estandar"),
            ("egresos",           1, "estandar"),
            ("proveedores",       1, "estandar"),
            ("tesoreria",         1, "estandar"),
            ("cuenta_corriente",  1, "estandar"),
            ("listas_precio",     1, "estandar"),
            ("libros_iva",        1, "estandar"),
            ("restaurant",        1, "basico"),
        ]
        for modulo, habilitado, plan in _MODULOS_DEFAULT:
            conn.execute(
                "INSERT OR IGNORE INTO modulos (modulo, habilitado, plan) VALUES (?,?,?)",
                (modulo, habilitado, plan),
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Módulo Restaurant — salones, mesas, pedidos, comandas
# ═══════════════════════════════════════════════════════════════════════════════

