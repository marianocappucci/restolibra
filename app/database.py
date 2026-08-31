import os

# Infraestructura compartida y módulos por dominio, extraídos de este archivo
# como parte del split en módulos lógicos (Fase 3 de LibraCore, sub-paso
# previo dentro de cada producto, sin cambiar comportamiento — ver
# wiki/entities/libracore.md). Re-exportados acá para que los call sites
# existentes (`db.get_connection()`, `db.DB_PATH`, `db.create_usuario(...)`,
# etc.) no cambien una línea.
from libracore.db.schema import init_core_schema
from libracore.db.clients import sincronizar_parties_de_clientes
from libracommerce.db.schema import init_schema as init_commerce_schema
from libraedge.db.changelog import init_changelog_schema
from libraedge.db.schema import init_schema as init_edge_schema
from app.db_core import _AR_TZ, _ar_now, _DATA_DIR, DB_PATH, ES_POSTGRES, get_connection, minutos_desde  # noqa: F401
from app.schema_propio import init_schema_propio  # noqa: F401  (lo usa init_db)
from app.db_usuarios import (  # noqa: F401
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
    ensure_demo_user,
    # Recuperacion de contrasena por correo (libraauth v0.5.0).
    solicitar_reset_password,
    resetear_password_con_token,
    EmailNotConfigured,
    InvalidResetToken,
    # Config SMTP por backoffice, cifrada en reposo (libraauth v0.6.0).
    leer_config_smtp,
    guardar_config_smtp,
    borrar_config_smtp,
    ClaveDeCifradoAusente,
    SIN_CAMBIOS,
)
from app.db_tesoreria import (  # noqa: F401
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
from app.db_caja import (  # noqa: F401
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
    anular_caja_movimiento,
    delete_caja_movimiento,
)
from app.db_egresos import (  # noqa: F401
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
from app.db_modulos import get_modulos, apply_plan  # noqa: F401
from app.db_listas_precio import (  # noqa: F401
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
from app.db_turnos import (  # noqa: F401
    create_turno,
    get_turno_activo,
    get_turno_activo_any,
    get_all_turnos,
    get_turno,
    get_resumen_turno,
    cerrar_turno,
    vincular_venta_turno,
)
from app.db_dashboard import get_dashboard_data  # noqa: F401
from app.db_logs import (  # noqa: F401
    get_actividad_log,
    get_actividad_count,
    registrar_auth_event,
    get_auth_log,
    contar_login_fallidos_recientes,
)
from app.db_arca_config import (  # noqa: F401
    crear_arca_config,
    obtener_arca_config,
    obtener_todas_arca_configs,
    actualizar_arca_config,
    eliminar_arca_config,
)
from app.db_cuenta_corriente import (  # noqa: F401
    get_cc_saldo,
    get_cc_movimientos,
    get_clientes_con_saldo_cc,
    create_cc_pago,
    delete_cc_pago,
)
from app.db_libros_iva import get_facturas_para_iva, get_egresos_para_iva  # noqa: F401
from app.db_reportes import (  # noqa: F401
    get_reporte_ventas,
    get_reporte_medios_pago,
    get_reporte_productos_top,
    get_reporte_caja,
    get_reporte_caja_medios,
    get_reporte_stock_bajo,
    get_reporte_resumen,
)
from app.db_productos import (  # noqa: F401
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
from app.db_recetas import (  # noqa: F401
    get_receta,
    guardar_receta,
    eliminar_receta,
    producir_receta,
    costo_receta,
    food_cost_pct,
    get_reporte_food_cost,
    get_consumo_insumos,
)
from app.db_stock import (  # noqa: F401
    add_movimiento_stock,
    get_stock_actual,
    get_stock_todos,
    get_movimientos_stock,
    ajustar_stock,
    descontar_stock_venta,
    _parse_modificadores,
    _resumen_modificadores,
)
from app.db_clients import (  # noqa: F401
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
from app.db_remitos_presupuestos import (  # noqa: F401
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
from app.db_facturas import (  # noqa: F401
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
from app.db_mp import (  # noqa: F401
    get_mp_pago,
    create_mp_pago,
    get_mp_pago_by_id,
    get_mp_pagos_by_estado,
    get_mp_pagos_historial,
    update_mp_pago_estado,
    crear_alias_facturacion,
    get_alias_facturacion_by_cliente,
    eliminar_alias_facturacion,
    # 🔴 Estos dos FALTABAN, y con ellos faltaba el sistema entero de alias de
    # facturacion: `db_mp.py` los re-exportaba desde el Tier 2 de LibraCore y
    # `database.py` --que es la fachada que usa todo el producto-- no. Ningun
    # camino podia llamarlos aunque quisiera. Es el mecanismo que en Contalibra
    # emitio dos comprobantes al CUIT equivocado.
    get_cliente_por_alias_pago,
    resolver_cliente_pago,
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
from app.db_ventas import (  # noqa: F401
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
    acreditar_pago_qr,
)
from app.db_salones import (  # noqa: F401
    get_salones,
    get_salon,
    create_salon,
    update_salon,
    delete_salon,
)
from app.db_reservas import (  # noqa: F401
    get_reservas,
    get_reserva,
    get_proximas_reservas_por_mesa,
    RESERVA_BUFFER_MINUTOS,
    crear_reserva,
    cancelar_reserva,
    cumplir_reserva,
)
from app.db_pedidos import (  # noqa: F401
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
from app.db_mesas import (  # noqa: F401
    get_mesas,
    get_mesa,
    create_mesa,
    update_mesa,
    set_mesa_estado,
    liberar_mesa,
    delete_mesa,
    resumen_salon_ahora,
)
from app.db_comandas import (  # noqa: F401
    ESTACIONES,
    COMANDA_ESTADOS,
    enviar_a_estaciones,
    get_comanda,
    get_comandas_estacion,
    set_comanda_estado,
    avanzar_comanda,
)
from app.db_cobro_pedido import cobrar_pedido  # noqa: F401
from app.db_reportes_gastronomicos import reporte_gastronomia  # noqa: F401

# Antes de P8, descontar_stock_venta (libracore.db.stock) era receta-aware
# vía un hook inyectado acá (configure_resolver_receta), para no acoplar
# LibraCore a un dominio de producto específico. Desde P8, db_stock.py es
# implementación propia de Restolibra y llama a db_recetas.get_receta()
# directo — el hook ya no se usa y LibraCore no se toca.


def _repuntar_fk_ventas_pagos_postgres(conn):
    """Lo mismo que el rebuild de SQLite, pero en dos `ALTER TABLE`.

    PostgreSQL si sabe cambiar una constraint, asi que no hay que reconstruir
    la tabla ni copiar filas. Sin `PRAGMA`, sin `sqlite_master` y sin mover un
    solo dato. Mismo criterio que en Contalibra.
    """
    definiciones = conn.execute("""
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'ventas_pagos'::regclass AND contype = 'f'
    """).fetchall()

    if any("REFERENCES sales(" in d[1] for d in definiciones):
        return

    huerfanas = conn.execute("""
        SELECT COUNT(*) FROM ventas_pagos vp
        LEFT JOIN sales s ON s.id = vp.venta_id
        WHERE s.id IS NULL
    """).fetchone()[0]
    if huerfanas:
        print(
            f"[ADVERTENCIA] ventas_pagos: {huerfanas} fila(s) referencian una venta "
            "que no esta en `sales`. Se conservan tal cual: revisar a mano.",
            flush=True,
        )

    for nombre, definicion in definiciones:
        if "venta_id" in definicion:
            conn.execute(f"ALTER TABLE ventas_pagos DROP CONSTRAINT {nombre}")

    # `NOT VALID` cuando hay filas colgadas: es el equivalente exacto de lo que
    # hace el camino de SQLite, donde el rebuild las copia con el pragma
    # apagado y la FK queda declarada pero sin verificar sobre ellas. Es
    # deliberado -- son registros de dinero. PostgreSQL no acepta agregar una FK
    # que las filas violan, y `NOT VALID` dice lo mismo: no revises lo que ya
    # esta, aplica la regla de aca en adelante. Se valida a mano despues.
    sufijo = " NOT VALID" if huerfanas else ""
    conn.execute(
        "ALTER TABLE ventas_pagos ADD CONSTRAINT ventas_pagos_venta_id_fkey "
        f"FOREIGN KEY (venta_id) REFERENCES sales(id) ON DELETE CASCADE{sufijo}"
    )
    conn.commit()


def _migrar_ventas_pagos_a_sales(conn):
    """Repunta la FK de `ventas_pagos` de `ventas(id)` (schema de LibraCore)
    a `sales(id)` (LibraCommerce), que es donde viven las ventas de
    Restolibra desde P8. Mismo fix que Contalibra (2026-07-30).

    El schema compartido de LibraCore crea la tabla con `REFERENCES
    ventas(id)`, así que sobre una base desde cero cada INSERT de un pago
    falla con FOREIGN KEY constraint (el pragma está activo por conexión).
    Idempotente: si ya apunta a `sales`, no hace nada.

    `ventas_pagos` no tiene tablas hijas, así que el rebuild no pisa la
    trampa del RENAME de SQLite que reescribe las FK de las hijas — la
    misma que sí apareció en P8 con `pedidos`/`comandas`.
    """
    if ES_POSTGRES:
        # Contra PostgreSQL no existen ni `sqlite_master` ni el PRAGMA, y el
        # rebuild de 12 pasos no hace falta: la constraint se cambia y listo.
        _repuntar_fk_ventas_pagos_postgres(conn)
        return

    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='ventas_pagos'"
    ).fetchone()
    if not row or "REFERENCES sales(" in row[0]:
        return

    # Ver el comentario equivalente en contalibra/database.py: las filas que
    # no tienen su venta en `sales` no se descartan (son registros de
    # dinero), se copian igual y se avisa, porque quedan como referencias
    # colgadas y eso tiene que ser una decisión de alguien.
    huerfanas = conn.execute("""
        SELECT COUNT(*) FROM ventas_pagos vp
        LEFT JOIN sales s ON s.id = vp.venta_id
        WHERE s.id IS NULL
    """).fetchone()[0]
    if huerfanas:
        print(
            f"[ADVERTENCIA] ventas_pagos: {huerfanas} fila(s) referencian una venta "
            "que no está en `sales` (entorno a medio migrar de P8). Se conservan "
            "tal cual, pero quedan como referencias colgadas: revisar a mano.",
            flush=True,
        )

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("ALTER TABLE ventas_pagos RENAME TO ventas_pagos_old")
        conn.execute("""
            CREATE TABLE ventas_pagos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id   INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
                medio      TEXT NOT NULL,
                monto      REAL NOT NULL,
                referencia TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','-3 hours'))
            )
        """)
        conn.execute("""
            INSERT INTO ventas_pagos (id, venta_id, medio, monto, referencia, created_at)
            SELECT id, venta_id, medio, monto, referencia, created_at
            FROM ventas_pagos_old
        """)
        conn.execute("DROP TABLE ventas_pagos_old")
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def init_db():
    with get_connection() as conn:
        init_core_schema(conn)
        # Catálogo/stock/ventas viven en las tablas de LibraCommerce desde
        # P8 (ver db_productos.py). Conviven en el MISMO archivo SQLite que
        # el resto de Restolibra, a propósito: `crear_venta_directa`/
        # `cobrar_pedido` cruzan ambos motores en una única transacción
        # atómica. Mismo patrón que Contalibra (P7).
        init_commerce_schema(conn)
        _migrar_ventas_pagos_a_sales(conn)

        # Depósito por defecto: LibraCommerce no seed-ea ninguna location, y
        # sin al menos una cualquier movimiento de stock revienta con NOT
        # NULL location_id sobre una base desde cero. Mismo fix que
        # Contalibra (2026-07-30).
        if not conn.execute("SELECT 1 FROM locations LIMIT 1").fetchone():
            conn.execute(
                "INSERT INTO locations (name, description, is_default, active)"
                " VALUES ('Depósito principal', '', 1, 1)"
            )

        # Las 9 tablas propias de este producto, con sus índices y los tres
        # ALTER históricos. El DDL vive en `app/schema_propio.py` y no acá desde
        # el 2026-08-25, porque la baseline de Alembic
        # (`migrations/versions/0001_baseline_restolibra.py`) llama a esa MISMA
        # función: si el DDL siguiera suelto acá, la revisión tendría que
        # re-expresarlo y serían dos fuentes de verdad que se desincronizan en
        # el primer cambio.
        #
        # 🔴 Desde esa revisión la función es de **sólo lectura**: una columna
        # nueva va como revisión de Alembic, no como línea agregada ahí. Ver su
        # docstring para el reparto completo de las 67 tablas.
        init_schema_propio(conn)

        # Las tablas del nodo offline (LibraEdge). Van acá **y** en la revisión
        # `0003_libraedge` de Alembic, que llama a estas mismas dos funciones:
        # el trato que sostiene `test_schema_propio_congelado` es que el arranque
        # y la cadena dejen el MISMO schema, y ese test compara la base
        # resultante, no el texto de la revisión.
        #
        # Se crean en toda instancia, sea nodo o no: el central las necesita
        # igual — `node_identity` para autenticar a los nodos que le pushean,
        # `sync_inbox` para deduplicar y `sync_changelog` para publicar la
        # bajada. Crearlas sólo en los nodos dejaría dos schemas distintos en
        # silencio, que es lo que la baseline advierte de las FK condicionales.
        init_edge_schema(conn)
        init_changelog_schema(conn)

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
        conn.commit()

    # Backfill de los `parties` espejo de `clients` (libracore v1.2.0). Va
    # al final y FUERA del `with`: necesita que `init_commerce_schema` ya
    # haya creado `parties`, y abre su propia conexión. Sin espejo, vender a
    # un cliente creado después de P8 falla con FOREIGN KEY constraint (ver
    # libracore/db/clients.py). Idempotente.
    sincronizar_parties_de_clientes()


# ═══════════════════════════════════════════════════════════════════════════════
# Módulo Restaurant — salones, mesas, pedidos, comandas
# ═══════════════════════════════════════════════════════════════════════════════

