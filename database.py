import sqlite3
import json
import os
import contextlib

# Infraestructura compartida y módulos por dominio, extraídos de este archivo
# como parte del split en módulos lógicos (Fase 3 de LibraCore, sub-paso
# previo dentro de cada producto, sin cambiar comportamiento — ver
# wiki/entities/libracore.md). Re-exportados acá para que los call sites
# existentes (`db.get_connection()`, `db.DB_PATH`, `db.create_usuario(...)`,
# etc.) no cambien una línea.
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


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                address       TEXT,
                cuit_dni      TEXT,
                email         TEXT,
                phone         TEXT,
                iva_condition TEXT DEFAULT '',
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS remitos (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                number         TEXT NOT NULL UNIQUE,
                date           TEXT NOT NULL,
                client_id      INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                client_name    TEXT NOT NULL,
                client_address TEXT,
                client_cuit    TEXT,
                client_email   TEXT,
                client_phone   TEXT,
                items          TEXT NOT NULL,
                subtotal       REAL NOT NULL,
                tax_rate       REAL NOT NULL DEFAULT 0.21,
                tax_amount     REAL NOT NULL,
                total          REAL NOT NULL,
                observations   TEXT,
                pdf_path       TEXT,
                created_at     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS presupuestos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                number          TEXT NOT NULL UNIQUE,
                date            TEXT NOT NULL,
                valid_until     TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pendiente',
                client_id       INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                client_name     TEXT NOT NULL,
                client_address  TEXT,
                client_cuit     TEXT,
                client_email    TEXT,
                client_phone    TEXT,
                items           TEXT NOT NULL,
                subtotal        REAL NOT NULL,
                tax_rate        REAL NOT NULL DEFAULT 0.21,
                tax_amount      REAL NOT NULL,
                total           REAL NOT NULL,
                observations    TEXT,
                pdf_path        TEXT,
                remito_id       INTEGER REFERENCES remitos(id),
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS facturas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo            INTEGER NOT NULL,
                punto_venta     INTEGER NOT NULL,
                numero          INTEGER NOT NULL,
                fecha           TEXT NOT NULL,
                cliente_cuit    TEXT,
                cliente_razon   TEXT,
                cliente_iva_cond INTEGER,
                items           TEXT NOT NULL,
                subtotal        REAL NOT NULL,
                iva_amount      REAL NOT NULL,
                total           REAL NOT NULL,
                concepto        INTEGER NOT NULL DEFAULT 1,
                cae             TEXT,
                cae_vto         TEXT,
                observaciones   TEXT,
                pdf_path        TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS cajas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT NOT NULL,
                descripcion TEXT DEFAULT '',
                medios_pago TEXT NOT NULL DEFAULT '[]',
                activo      INTEGER NOT NULL DEFAULT 1,
                es_default  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS caja_movimientos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha       TEXT NOT NULL,
                tipo        TEXT NOT NULL,
                concepto    TEXT NOT NULL,
                monto       REAL NOT NULL,
                referencia  TEXT DEFAULT '',
                factura_id  INTEGER,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS mp_pagos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                mp_payment_id   TEXT NOT NULL UNIQUE,
                status          TEXT,
                monto           REAL,
                payer_email     TEXT,
                payer_name      TEXT,
                factura_id      INTEGER,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS mp_movimientos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                mp_movement_id  TEXT NOT NULL UNIQUE,
                tipo            TEXT,
                monto           REAL,
                fecha           TEXT,
                descripcion     TEXT,
                origen_nombre   TEXT,
                origen_banco    TEXT,
                origen_cbu      TEXT,
                payer_email     TEXT,
                payer_name      TEXT,
                payer_id_type   TEXT,
                payer_id_number TEXT,
                estado_factura  TEXT DEFAULT 'pendiente',
                factura_id      INTEGER,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS arca_config (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                empresa         TEXT NOT NULL UNIQUE,
                cuit            TEXT NOT NULL,
                punto_venta     INTEGER NOT NULL,
                clave_path      TEXT NOT NULL,
                certificado_path TEXT NOT NULL,
                ambiente        TEXT DEFAULT 'homologacion',
                activo          INTEGER DEFAULT 1,
                alias           TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                updated_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS usuarios (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                nombre        TEXT NOT NULL,
                email         TEXT DEFAULT '',
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'operador',
                activo        INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS modulos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                modulo     TEXT NOT NULL UNIQUE,
                habilitado INTEGER NOT NULL DEFAULT 1,
                plan       TEXT NOT NULL DEFAULT 'estandar'
            );

            CREATE TABLE IF NOT EXISTS productos (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo       TEXT UNIQUE,
                nombre       TEXT NOT NULL,
                descripcion  TEXT DEFAULT '',
                precio_venta REAL NOT NULL DEFAULT 0,
                precio_costo REAL NOT NULL DEFAULT 0,
                unidad       TEXT NOT NULL DEFAULT 'u',
                categoria    TEXT DEFAULT '',
                activo       INTEGER NOT NULL DEFAULT 1,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS recetas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id     INTEGER NOT NULL UNIQUE REFERENCES productos(id) ON DELETE CASCADE,
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
                ingrediente_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
                cantidad       REAL NOT NULL DEFAULT 0,
                created_at     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS depositos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT NOT NULL,
                descripcion TEXT DEFAULT '',
                activo      INTEGER NOT NULL DEFAULT 1,
                es_default  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS categorias_producto (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS categorias_egreso (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS proveedores (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre        TEXT NOT NULL,
                cuit_dni      TEXT DEFAULT '',
                email         TEXT DEFAULT '',
                phone         TEXT DEFAULT '',
                address       TEXT DEFAULT '',
                iva_condition TEXT DEFAULT '',
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS egresos (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha            TEXT NOT NULL,
                proveedor_id     INTEGER REFERENCES proveedores(id) ON DELETE SET NULL,
                proveedor_nombre TEXT NOT NULL DEFAULT '',
                tipo_comprobante TEXT NOT NULL DEFAULT 'otro',
                numero           TEXT DEFAULT '',
                categoria        TEXT DEFAULT '',
                concepto         TEXT NOT NULL,
                monto_neto       REAL NOT NULL DEFAULT 0,
                iva_pct          REAL NOT NULL DEFAULT 0,
                iva_monto        REAL NOT NULL DEFAULT 0,
                total            REAL NOT NULL,
                estado           TEXT NOT NULL DEFAULT 'pendiente',
                observaciones    TEXT DEFAULT '',
                usuario_id       INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
                created_at       TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS egresos_pagos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                egreso_id   INTEGER NOT NULL REFERENCES egresos(id) ON DELETE CASCADE,
                fecha       TEXT NOT NULL,
                monto       REAL NOT NULL,
                caja_id     INTEGER REFERENCES cajas(id) ON DELETE SET NULL,
                medio_pago  TEXT DEFAULT '',
                referencia  TEXT DEFAULT '',
                usuario_id  INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS turnos_caja (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id             INTEGER NOT NULL REFERENCES usuarios(id),
                apertura               TEXT NOT NULL,
                cierre                 TEXT,
                monto_inicial          REAL NOT NULL DEFAULT 0,
                monto_declarado_cierre REAL,
                monto_esperado_cierre  REAL,
                estado                 TEXT NOT NULL DEFAULT 'abierto',
                notas                  TEXT DEFAULT '',
                created_at             TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS movimientos_stock (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
                tipo        TEXT NOT NULL,
                cantidad    REAL NOT NULL,
                referencia  TEXT DEFAULT '',
                venta_id    INTEGER REFERENCES ventas(id) ON DELETE SET NULL,
                usuario_id  INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
                fecha       TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS ventas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                numero          TEXT NOT NULL UNIQUE,
                fecha           TEXT NOT NULL,
                cliente_id      INTEGER REFERENCES clients(id) ON DELETE SET NULL,
                cliente_nombre  TEXT DEFAULT '',
                items           TEXT NOT NULL,
                subtotal        REAL NOT NULL DEFAULT 0,
                descuento       REAL NOT NULL DEFAULT 0,
                total           REAL NOT NULL DEFAULT 0,
                estado          TEXT NOT NULL DEFAULT 'cobrada',
                factura_id      INTEGER REFERENCES facturas(id) ON DELETE SET NULL,
                remito_id       INTEGER REFERENCES remitos(id) ON DELETE SET NULL,
                usuario_id      INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
                observaciones   TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS ventas_pagos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id   INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
                medio      TEXT NOT NULL,
                monto      REAL NOT NULL,
                referencia TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
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
                venta_id       INTEGER REFERENCES ventas(id) ON DELETE SET NULL,
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
        # UNIQUE aparte (no en el executescript de arriba): si por algún motivo
        # ya existieran duplicados de tipo+punto_venta+numero en una instancia
        # (no debería, pero es defensivo), que falle solo esto sin tumbar el
        # resto de init_db al arrancar la app. Cierra la race condition de
        # numeración (auditoría de Restolibra, "race condition en numeración")
        # junto con el retry en create_factura() — portado desde Contalibra.
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_facturas_numero_unico "
                "ON facturas(tipo, punto_venta, numero)"
            )
        except sqlite3.Error as e:
            print(f"[WARN] No se pudo crear idx_facturas_numero_unico (¿hay duplicados "
                  f"de tipo+punto_venta+numero?): {e}")
        # Migración: columnas faltantes
        cols = [r[1] for r in conn.execute("PRAGMA table_info(clients)").fetchall()]
        if "iva_condition" not in cols:
            conn.execute("ALTER TABLE clients ADD COLUMN iva_condition TEXT DEFAULT ''")
        if "activo" not in cols:
            conn.execute("ALTER TABLE clients ADD COLUMN activo INTEGER DEFAULT 1")
        fact_cols = [r[1] for r in conn.execute("PRAGMA table_info(facturas)").fetchall()]
        if "cliente_domicilio" not in fact_cols:
            conn.execute("ALTER TABLE facturas ADD COLUMN cliente_domicilio TEXT DEFAULT ''")
        if "fch_serv_desde" not in fact_cols:
            conn.execute("ALTER TABLE facturas ADD COLUMN fch_serv_desde TEXT DEFAULT ''")
        if "fch_serv_hasta" not in fact_cols:
            conn.execute("ALTER TABLE facturas ADD COLUMN fch_serv_hasta TEXT DEFAULT ''")
        if "fch_vto_pago" not in fact_cols:
            conn.execute("ALTER TABLE facturas ADD COLUMN fch_vto_pago TEXT DEFAULT ''")
        if "cbte_asoc_tipo" not in fact_cols:
            conn.execute("ALTER TABLE facturas ADD COLUMN cbte_asoc_tipo INTEGER DEFAULT 0")
        if "cbte_asoc_pv" not in fact_cols:
            conn.execute("ALTER TABLE facturas ADD COLUMN cbte_asoc_pv INTEGER DEFAULT 0")
        if "cbte_asoc_nro" not in fact_cols:
            conn.execute("ALTER TABLE facturas ADD COLUMN cbte_asoc_nro INTEGER DEFAULT 0")
        if "condicion_venta" not in fact_cols:
            conn.execute("ALTER TABLE facturas ADD COLUMN condicion_venta TEXT DEFAULT ''")
        if "usuario_id" not in fact_cols:
            conn.execute("ALTER TABLE facturas ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL")

        remito_cols = [r[1] for r in conn.execute("PRAGMA table_info(remitos)").fetchall()]
        if remito_cols and "usuario_id" not in remito_cols:
            conn.execute("ALTER TABLE remitos ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL")

        pres_cols = [r[1] for r in conn.execute("PRAGMA table_info(presupuestos)").fetchall()]
        if pres_cols and "usuario_id" not in pres_cols:
            conn.execute("ALTER TABLE presupuestos ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL")

        caja_cols = [r[1] for r in conn.execute("PRAGMA table_info(caja_movimientos)").fetchall()]
        if caja_cols and "usuario_id" not in caja_cols:
            conn.execute("ALTER TABLE caja_movimientos ADD COLUMN usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL")

        prod_cols = [r[1] for r in conn.execute("PRAGMA table_info(productos)").fetchall()]
        if "stock_minimo" not in prod_cols:
            conn.execute("ALTER TABLE productos ADD COLUMN stock_minimo REAL NOT NULL DEFAULT 0")
        if "estacion" not in prod_cols:
            conn.execute("ALTER TABLE productos ADD COLUMN estacion TEXT DEFAULT ''")
        if "vendible" not in prod_cols:
            conn.execute("ALTER TABLE productos ADD COLUMN vendible INTEGER NOT NULL DEFAULT 1")
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
        ventas_cols = [r[1] for r in conn.execute("PRAGMA table_info(ventas)").fetchall()]
        if ventas_cols and "turno_id" not in ventas_cols:
            conn.execute("ALTER TABLE ventas ADD COLUMN turno_id INTEGER REFERENCES turnos_caja(id) ON DELETE SET NULL")
        if ventas_cols and "mp_order_id" not in ventas_cols:
            conn.execute("ALTER TABLE ventas ADD COLUMN mp_order_id TEXT DEFAULT ''")
        if ventas_cols and "mp_payment_id" not in ventas_cols:
            conn.execute("ALTER TABLE ventas ADD COLUMN mp_payment_id TEXT DEFAULT ''")

        client_cols = [r[1] for r in conn.execute("PRAGMA table_info(clients)").fetchall()]
        if "auto_facturar" not in client_cols:
            conn.execute("ALTER TABLE clients ADD COLUMN auto_facturar INTEGER NOT NULL DEFAULT 0")

        mp_cols = [r[1] for r in conn.execute("PRAGMA table_info(mp_pagos)").fetchall()]
        if mp_cols and "estado_factura" not in mp_cols:
            conn.execute("ALTER TABLE mp_pagos ADD COLUMN estado_factura TEXT DEFAULT NULL")
        if mp_cols and "payment_type" not in mp_cols:
            conn.execute("ALTER TABLE mp_pagos ADD COLUMN payment_type TEXT DEFAULT NULL")
        if mp_cols and "payment_method" not in mp_cols:
            conn.execute("ALTER TABLE mp_pagos ADD COLUMN payment_method TEXT DEFAULT NULL")
        if mp_cols and "descripcion_mp" not in mp_cols:
            conn.execute("ALTER TABLE mp_pagos ADD COLUMN descripcion_mp TEXT DEFAULT NULL")
        if mp_cols and "payer_id_type" not in mp_cols:
            conn.execute("ALTER TABLE mp_pagos ADD COLUMN payer_id_type TEXT DEFAULT NULL")
        if mp_cols and "payer_id_number" not in mp_cols:
            conn.execute("ALTER TABLE mp_pagos ADD COLUMN payer_id_number TEXT DEFAULT NULL")

        # Migración: cajas — caja principal por defecto
        if conn.execute("SELECT COUNT(*) FROM cajas").fetchone()[0] == 0:
            _todos_medios = json.dumps([
                "efectivo", "transferencia", "mercadopago",
                "cuenta_dni", "billetera", "cuenta_corriente",
            ])
            cur = conn.execute(
                "INSERT INTO cajas (nombre, descripcion, medios_pago, es_default) VALUES (?,?,?,1)",
                ("Caja Principal", "Caja por defecto del sistema", _todos_medios),
            )
            _default_caja_id = cur.lastrowid
        else:
            _default_caja_id = conn.execute(
                "SELECT id FROM cajas WHERE es_default=1 LIMIT 1"
            ).fetchone()
            _default_caja_id = _default_caja_id[0] if _default_caja_id else conn.execute(
                "SELECT id FROM cajas ORDER BY id LIMIT 1"
            ).fetchone()[0]

        cm_cols = [r[1] for r in conn.execute("PRAGMA table_info(caja_movimientos)").fetchall()]
        if cm_cols and "caja_id" not in cm_cols:
            conn.execute("ALTER TABLE caja_movimientos ADD COLUMN caja_id INTEGER REFERENCES cajas(id) ON DELETE SET NULL")
            conn.execute("UPDATE caja_movimientos SET caja_id=? WHERE caja_id IS NULL", (_default_caja_id,))
        if cm_cols and "medio_pago" not in cm_cols:
            conn.execute("ALTER TABLE caja_movimientos ADD COLUMN medio_pago TEXT DEFAULT ''")

        tc_cols = [r[1] for r in conn.execute("PRAGMA table_info(turnos_caja)").fetchall()]
        if tc_cols and "caja_id" not in tc_cols:
            conn.execute("ALTER TABLE turnos_caja ADD COLUMN caja_id INTEGER REFERENCES cajas(id) ON DELETE SET NULL")
            conn.execute("UPDATE turnos_caja SET caja_id=? WHERE caja_id IS NULL", (_default_caja_id,))

        # Migración: deposito_id en movimientos_stock
        ms_cols = [r[1] for r in conn.execute("PRAGMA table_info(movimientos_stock)").fetchall()]
        if ms_cols and "deposito_id" not in ms_cols:
            conn.execute("ALTER TABLE movimientos_stock ADD COLUMN deposito_id INTEGER REFERENCES depositos(id) ON DELETE SET NULL")

        # Depósito principal por defecto (se crea solo si no existe ninguno)
        if conn.execute("SELECT COUNT(*) FROM depositos").fetchone()[0] == 0:
            cur = conn.execute(
                "INSERT INTO depositos (nombre, descripcion, es_default) VALUES (?,?,1)",
                ("Depósito Principal", "Depósito por defecto del sistema"),
            )
            default_id = cur.lastrowid
            # Asignar movimientos existentes sin depósito al depósito default
            conn.execute(
                "UPDATE movimientos_stock SET deposito_id=? WHERE deposito_id IS NULL",
                (default_id,),
            )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS cuentas_tesoreria (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre        TEXT NOT NULL,
                tipo          TEXT NOT NULL DEFAULT 'banco',
                banco         TEXT DEFAULT '',
                numero        TEXT DEFAULT '',
                descripcion   TEXT DEFAULT '',
                saldo_inicial REAL NOT NULL DEFAULT 0,
                activa        INTEGER NOT NULL DEFAULT 1,
                orden         INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS movimientos_tesoreria (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha             TEXT NOT NULL,
                cuenta_id         INTEGER NOT NULL REFERENCES cuentas_tesoreria(id) ON DELETE CASCADE,
                tipo              TEXT NOT NULL,
                monto             REAL NOT NULL,
                concepto          TEXT NOT NULL DEFAULT '',
                referencia        TEXT DEFAULT '',
                cuenta_destino_id INTEGER REFERENCES cuentas_tesoreria(id) ON DELETE SET NULL,
                transferencia_id  INTEGER,
                usuario_id        INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
                created_at        TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts         TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                evento     TEXT NOT NULL,
                username   TEXT NOT NULL,
                ip         TEXT,
                detalle    TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS listas_precio (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT NOT NULL,
                descripcion TEXT DEFAULT '',
                es_default  INTEGER NOT NULL DEFAULT 0,
                activa      INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS lista_precio_items (
                lista_id    INTEGER NOT NULL REFERENCES listas_precio(id) ON DELETE CASCADE,
                producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
                precio      REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (lista_id, producto_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS cc_pagos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                monto       REAL NOT NULL,
                fecha       TEXT NOT NULL,
                concepto    TEXT DEFAULT '',
                referencia  TEXT DEFAULT '',
                medio_pago  TEXT DEFAULT 'efectivo',
                caja_id     INTEGER REFERENCES cajas(id) ON DELETE SET NULL,
                usuario_id  INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)

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

        _CATEGORIAS_EGRESO_DEFAULT = [
            "Mercadería / Materias primas",
            "Alquiler",
            "Servicios (luz, gas, internet)",
            "Sueldos y honorarios",
            "Impuestos y tasas",
            "Transporte y logística",
            "Mantenimiento y reparaciones",
            "Publicidad y marketing",
            "Bancarios y financieros",
            "Otros",
        ]
        for cat in _CATEGORIAS_EGRESO_DEFAULT:
            conn.execute("INSERT OR IGNORE INTO categorias_egreso (nombre) VALUES (?)", (cat,))


# ═══════════════════════════════════════════════════════════════════════════════
# Módulo Restaurant — salones, mesas, pedidos, comandas
# ═══════════════════════════════════════════════════════════════════════════════

ESTACIONES = ["cocina", "barra"]
COMANDA_ESTADOS = ["pendiente", "preparacion", "listo", "entregado"]
_COMANDA_NEXT = {"pendiente": "preparacion", "preparacion": "listo", "listo": "entregado"}


# ── Comandas ────────────────────────────────────────────────────────────────

def enviar_a_estaciones(pedido_id: int) -> list[int]:
    """Toma los ítems 'nuevo' del pedido, crea una comanda por estación (cocina/barra)
    con los ítems de esa estación, y marca todos los ítems como 'enviado'. Devuelve los
    ids de comanda creados (para imprimir). Ítems sin estación se marcan enviado sin comanda.

    El "tomado" de ítems es un UPDATE atómico (`WHERE estado='nuevo'`) antes de leerlos:
    si dos envíos casi simultáneos del mismo pedido compiten (doble click, dos mozos
    en la misma mesa), el segundo encuentra 0 filas para tomar y no duplica la comanda,
    en vez del check-then-act anterior donde ambos podían leer los mismos ítems 'nuevo'
    antes de que cualquiera los marcara."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE pedido_items SET estado='tomando' WHERE pedido_id=? AND estado='nuevo'",
            (pedido_id,),
        )
        if cur.rowcount == 0:
            conn.commit()
            return []
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM pedido_items WHERE pedido_id=? AND estado='tomando'", (pedido_id,)
        ).fetchall()]
        row = conn.execute(
            "SELECT COALESCE(MAX(numero),0) AS n FROM comandas WHERE pedido_id=?", (pedido_id,)
        ).fetchone()
        ronda = int(row["n"]) + 1
        creadas = []
        for estacion in ESTACIONES:
            grupo = [it for it in items if (it.get("estacion") or "") == estacion]
            if not grupo:
                continue
            _now = _ar_now()
            cur2 = conn.execute(
                "INSERT INTO comandas (pedido_id, estacion, numero, estado, created_at, updated_at) "
                "VALUES (?,?,?,'pendiente',?,?)",
                (pedido_id, estacion, ronda, _now, _now),
            )
            cid = cur2.lastrowid
            for it in grupo:
                conn.execute(
                    "UPDATE pedido_items SET comanda_id=?, estado='enviado' WHERE id=?",
                    (cid, it["id"]),
                )
            creadas.append(cid)
        conn.execute(
            "UPDATE pedido_items SET estado='enviado' WHERE pedido_id=? AND estado='tomando' "
            "AND (estacion IS NULL OR estacion='')", (pedido_id,)
        )
        conn.execute("UPDATE pedidos SET updated_at=? WHERE id=?", (_ar_now(), pedido_id))
        conn.commit()
    return creadas


def get_comanda(cid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT c.*, p.numero AS pedido_numero, p.canal, p.comensales,
                      m.nombre AS mesa_nombre, s.nombre AS salon_nombre, u.username AS mozo
               FROM comandas c
               JOIN pedidos p ON p.id = c.pedido_id
               LEFT JOIN mesas m ON m.id = p.mesa_id
               LEFT JOIN salones s ON s.id = m.salon_id
               LEFT JOIN usuarios u ON u.id = p.usuario_id
               WHERE c.id=?""",
            (cid,),
        ).fetchone()
        if not row:
            return None
        comanda = dict(row)
        comanda["items"] = [dict(r) for r in conn.execute(
            "SELECT * FROM pedido_items WHERE comanda_id=? AND estado!='anulado' ORDER BY id",
            (cid,),
        ).fetchall()]
    for it in comanda["items"]:
        resumen = _resumen_modificadores(it.get("modificadores"))
        if resumen:
            it["nota"] = f"{resumen} — {it['nota']}" if it.get("nota") else resumen
    return comanda


def get_comandas_estacion(estacion: str, estados: list[str] | None = None) -> list[dict]:
    estados = estados or ["pendiente", "preparacion", "listo"]
    ph = ",".join("?" for _ in estados)
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT c.*, p.numero AS pedido_numero, p.canal,
                       m.nombre AS mesa_nombre, s.nombre AS salon_nombre, u.username AS mozo
                FROM comandas c
                JOIN pedidos p ON p.id = c.pedido_id
                LEFT JOIN mesas m ON m.id = p.mesa_id
                LEFT JOIN salones s ON s.id = m.salon_id
                LEFT JOIN usuarios u ON u.id = p.usuario_id
                WHERE c.estacion=? AND c.estado IN ({ph})
                ORDER BY c.created_at, c.id""",
            [estacion, *estados],
        ).fetchall()
        comandas = [dict(r) for r in rows]
        for c in comandas:
            c["items"] = [dict(r) for r in conn.execute(
                "SELECT * FROM pedido_items WHERE comanda_id=? AND estado!='anulado' ORDER BY id",
                (c["id"],),
            ).fetchall()]
            for it in c["items"]:
                resumen = _resumen_modificadores(it.get("modificadores"))
                if resumen:
                    it["nota"] = f"{resumen} — {it['nota']}" if it.get("nota") else resumen
    return comandas


_ESTADO_TS_COL = {"preparacion": "preparacion_at", "listo": "listo_at", "entregado": "entregado_at"}


def _aplicar_estado_comanda(conn, cid: int, estado: str):
    """Setea estado + updated_at y, si corresponde, el timestamp de la transición
    (sólo la primera vez que entra a ese estado, vía COALESCE)."""
    now = _ar_now()
    col = _ESTADO_TS_COL.get(estado)
    if col:
        conn.execute(
            f"UPDATE comandas SET estado=?, updated_at=?, {col}=COALESCE({col}, ?) WHERE id=?",
            (estado, now, now, cid),
        )
    else:
        conn.execute(
            "UPDATE comandas SET estado=?, updated_at=? WHERE id=?", (estado, now, cid)
        )


def set_comanda_estado(cid: int, estado: str) -> bool:
    if estado not in COMANDA_ESTADOS:
        return False
    with get_connection() as conn:
        _aplicar_estado_comanda(conn, cid, estado)
    return True


def avanzar_comanda(cid: int) -> str | None:
    """Avanza la comanda al siguiente estado del flujo. Devuelve el nuevo estado."""
    with get_connection() as conn:
        row = conn.execute("SELECT estado FROM comandas WHERE id=?", (cid,)).fetchone()
        if not row:
            return None
        nuevo = _COMANDA_NEXT.get(row["estado"])
        if not nuevo:
            return row["estado"]
        _aplicar_estado_comanda(conn, cid, nuevo)
    return nuevo


# ── Cobro del pedido → genera una venta (reusa el flujo del POS) ──────────────

def cobrar_pedido(pedido_id: int, pagos: list[dict], descuento: float = 0.0,
                  cliente_id: int | None = None, cliente_nombre: str = "",
                  observaciones: str = "", usuario_id: int | None = None) -> int:
    """Cierra el pedido generando una venta con sus ítems y pagos, moviendo caja,
    descontando stock y vinculando al turno. Devuelve el venta_id.

    Todo corre en una única transacción sobre una sola conexión: el primer paso
    es un UPDATE condicional (`WHERE estado='abierto'`) que "reclama" el pedido
    — si dos cobros llegan casi simultáneos (doble click, dos mozos), el segundo
    pierde la carrera ahí mismo y lanza ValueError antes de tocar venta/caja/
    stock, en vez de duplicar todo. Si cualquier paso posterior falla (incluido
    el descuento de stock, que antes se silenciaba), se hace rollback completo y
    el pedido queda intacto en 'abierto'."""
    pedido = get_pedido(pedido_id)
    if not pedido:
        raise ValueError("Pedido inexistente")
    if pedido["estado"] != "abierto":
        raise ValueError("El pedido no está abierto")

    items = [{
        "nombre":         it["nombre"],
        "qty":            float(it["qty"]),
        "precio":         float(it["precio"]),
        "subtotal":       float(it["subtotal"]),
        "producto_id":    it.get("producto_id"),
        "modificadores":  it.get("modificadores") or "",
    } for it in pedido["items"]]

    envio = float(pedido.get("costo_envio") or 0)
    if envio > 0:
        items.append({"nombre": "Envío", "qty": 1, "precio": envio,
                      "subtotal": envio, "producto_id": None})

    subtotal = round(sum(i["subtotal"] for i in items), 2)
    descuento = round(float(descuento or 0), 2)
    descuento = min(max(0.0, descuento), subtotal)
    total = round(subtotal - descuento, 2)

    total_pagado = round(sum(float(p["monto"]) for p in pagos), 2)
    if total_pagado >= total:
        estado = "cobrada"
    elif total_pagado > 0:
        estado = "parcial"
    else:
        estado = "pendiente"

    if not cliente_id and pedido.get("cliente_id"):
        cliente_id = pedido["cliente_id"]
    if not cliente_nombre:
        cliente_nombre = pedido.get("cliente_nombre") or ""

    fecha = _ar_now().split(" ")[0]
    obs = observaciones or f"Pedido {pedido['numero']}"
    stock_habilitado = bool(get_modulos().get("stock"))

    with get_connection() as conn:
        try:
            cur = conn.execute(
                "UPDATE pedidos SET estado='cobrando', updated_at=? WHERE id=? AND estado='abierto'",
                (_ar_now(), pedido_id),
            )
            if cur.rowcount == 0:
                raise ValueError(
                    "El pedido ya fue cobrado o modificado por otra operación"
                )

            numero = get_next_venta_numero(conn=conn)
            venta_id = create_venta(
                numero=numero, fecha=fecha, items=items,
                subtotal=subtotal, descuento=descuento, total=total,
                cliente_id=cliente_id, cliente_nombre=cliente_nombre,
                usuario_id=usuario_id, observaciones=obs, estado=estado,
                conn=conn,
            )
            for i, p in enumerate(pagos):
                monto = float(p["monto"])
                referencia = p.get("referencia") or f"pedido:{pedido_id}:venta:{venta_id}:pago:{i}"
                add_venta_pago(venta_id, p["medio"], monto, referencia, conn=conn)
                create_caja_movimiento(
                    fecha=fecha, tipo="ingreso",
                    concepto=f"Venta {numero} (pedido {pedido['numero']}) — {p['medio']}",
                    monto=monto, referencia=referencia,
                    medio_pago=p["medio"], usuario_id=usuario_id,
                    conn=conn,
                )

            if stock_habilitado:
                descontar_stock_venta(venta_id, items, fecha=fecha, usuario_id=usuario_id, conn=conn)

            if usuario_id:
                turno = get_turno_activo(usuario_id, conn=conn)
                if turno:
                    vincular_venta_turno(venta_id, turno["id"], conn=conn)

            conn.execute(
                "UPDATE pedidos SET estado='cobrado', venta_id=?, updated_at=? WHERE id=?",
                (venta_id, _ar_now(), pedido_id),
            )
            if pedido.get("mesa_id"):
                conn.execute("UPDATE mesas SET estado='libre' WHERE id=?", (pedido["mesa_id"],))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return venta_id


# ── Reportes gastronómicos + tiempos ─────────────────────────────────────────


def reporte_gastronomia(desde: str, hasta: str) -> dict:
    """Métricas del módulo restaurant en [desde, hasta] (fechas 'YYYY-MM-DD'):
    - Ventas por canal (pedidos cobrados): cantidad, total, ticket promedio.
    - Tiempos de comanda por estación (minutos): espera, preparación y total, sobre las
      comandas que llegaron a 'listo' en el período."""
    ini, fin = desde + " 00:00:00", hasta + " 23:59:59"
    with get_connection() as conn:
        canales = [dict(r) for r in conn.execute(
            """SELECT p.canal AS canal, COUNT(*) AS n,
                      COALESCE(SUM(v.total), 0) AS total
               FROM pedidos p JOIN ventas v ON v.id = p.venta_id
               WHERE p.estado = 'cobrado' AND v.fecha >= ? AND v.fecha <= ?
               GROUP BY p.canal
               ORDER BY total DESC""",
            (desde, hasta),
        ).fetchall()]
        for c in canales:
            c["ticket"] = round(c["total"] / c["n"], 2) if c["n"] else 0.0

        tiempos = [dict(r) for r in conn.execute(
            """SELECT estacion,
                      COUNT(*) AS n,
                      AVG((julianday(preparacion_at) - julianday(created_at)) * 1440) AS espera_min,
                      AVG((julianday(listo_at)       - julianday(preparacion_at)) * 1440) AS prep_min,
                      AVG((julianday(listo_at)       - julianday(created_at)) * 1440) AS total_min
               FROM comandas
               WHERE listo_at IS NOT NULL AND created_at >= ? AND created_at <= ?
               GROUP BY estacion
               ORDER BY estacion""",
            (ini, fin),
        ).fetchall()]
        for t in tiempos:
            for k in ("espera_min", "prep_min", "total_min"):
                t[k] = round(t[k], 1) if t[k] is not None else None
    return {
        "desde": desde, "hasta": hasta,
        "canales": canales,
        "total_n": sum(c["n"] for c in canales),
        "total_total": round(sum(c["total"] for c in canales), 2),
        "tiempos": tiempos,
    }
