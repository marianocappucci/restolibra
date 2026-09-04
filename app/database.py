import os

from libracommerce.db.schema import init_schema as init_commerce_schema
from libracore.db.clients import sincronizar_parties_de_clientes

# Infraestructura compartida y módulos por dominio, extraídos de este archivo
# como parte del split en módulos lógicos (Fase 3 de LibraCore, sub-paso
# previo dentro de cada producto, sin cambiar comportamiento — ver
# wiki/entities/libracore.md). Re-exportados acá para que los call sites
# existentes (`db.get_connection()`, `db.DB_PATH`, `db.create_usuario(...)`,
# etc.) no cambien una línea.
from libracore.db.schema import init_core_schema
from libraedge.db.changelog import init_changelog_schema
from libraedge.db.schema import init_schema as init_edge_schema

from app.db_arca_config import (  # noqa: F401
    actualizar_arca_config,
    crear_arca_config,
    eliminar_arca_config,
    obtener_arca_config,
    obtener_todas_arca_configs,
)
from app.db_caja import (  # noqa: F401
    MEDIOS_PAGO_LABELS,
    anular_caja_movimiento,
    create_caja_config,
    create_caja_movimiento,
    delete_caja_config,
    delete_caja_movimiento,
    get_all_cajas,
    get_caja_config,
    get_caja_movimientos,
    get_caja_resumen,
    get_cobro_factura,
    get_cobros_factura,
    get_default_caja_id,
    set_default_caja,
    update_caja_config,
)
from app.db_clients import (  # noqa: F401
    activar_cliente,
    create_client,
    delete_client,
    desactivar_cliente,
    get_all_clients,
    get_all_clients_including_inactive,
    get_client,
    get_client_by_cuit,
    get_client_by_email,
    get_facturas_by_client,
    tiene_presupuestos_aprobados,
    toggle_auto_facturar,
    update_client,
)
from app.db_cobro_pedido import cobrar_pedido  # noqa: F401
from app.db_comandas import (  # noqa: F401
    COMANDA_ESTADOS,
    ESTACIONES,
    avanzar_comanda,
    enviar_a_estaciones,
    get_comanda,
    get_comandas_estacion,
    set_comanda_estado,
)
from app.db_core import _AR_TZ, _DATA_DIR, DB_PATH, ES_POSTGRES, _ar_now, get_connection, minutos_desde  # noqa: F401
from app.db_cuenta_corriente import (  # noqa: F401
    create_cc_pago,
    delete_cc_pago,
    get_cc_movimientos,
    get_cc_saldo,
    get_clientes_con_saldo_cc,
)
from app.db_dashboard import get_dashboard_data  # noqa: F401
from app.db_egresos import (  # noqa: F401
    create_categoria_egreso,
    create_egreso,
    create_pago_egreso,
    create_proveedor,
    delete_categoria_egreso,
    delete_egreso,
    delete_proveedor,
    get_all_egresos,
    get_all_proveedores,
    get_categorias_egreso,
    get_egreso,
    get_pagos_egreso,
    get_proveedor,
    get_resumen_egresos,
    search_proveedores,
    update_proveedor,
)
from app.db_facturas import (  # noqa: F401
    create_factura,
    delete_factura,
    get_all_facturas,
    get_factura,
    get_factura_por_tipo_pv_nro,
    get_facturas_filtradas,
    get_nc_de_factura,
    get_nd_de_factura,
    get_next_factura_numero,
    get_notas_de_factura,
    search_facturas,
    update_factura_cae,
    update_factura_pdf_path,
)
from app.db_libros_iva import get_egresos_para_iva, get_facturas_para_iva  # noqa: F401
from app.db_listas_precio import (  # noqa: F401
    apply_porcentaje_lista,
    create_lista_precio,
    delete_lista_precio,
    get_all_listas_precio,
    get_lista_precio,
    get_lista_precio_items,
    get_precio_en_lista,
    get_precios_lista_dict,
    importar_precios_lista,
    save_lista_precio_items,
    update_lista_precio,
)
from app.db_logs import (  # noqa: F401
    contar_login_fallidos_recientes,
    get_actividad_count,
    get_actividad_log,
    get_auth_log,
    registrar_auth_event,
)
from app.db_mesas import (  # noqa: F401
    create_mesa,
    delete_mesa,
    get_mesa,
    get_mesas,
    liberar_mesa,
    resumen_salon_ahora,
    set_mesa_estado,
    update_mesa,
)
from app.db_modulos import apply_plan, get_modulos  # noqa: F401
from app.db_mp import (  # noqa: F401
    crear_alias_facturacion,
    create_mp_movimiento,
    create_mp_pago,
    eliminar_alias_facturacion,
    get_alias_facturacion_by_cliente,
    # 🔴 Estos dos FALTABAN, y con ellos faltaba el sistema entero de alias de
    # facturacion: `db_mp.py` los re-exportaba desde el Tier 2 de LibraCore y
    # `database.py` --que es la fachada que usa todo el producto-- no. Ningun
    # camino podia llamarlos aunque quisiera. Es el mecanismo que en Contalibra
    # emitio dos comprobantes al CUIT equivocado.
    get_cliente_por_alias_pago,
    get_mp_movimiento_by_id,
    get_mp_movimiento_by_mp_id,
    get_mp_movimientos_by_estado,
    get_mp_movimientos_historial,
    get_mp_pago,
    get_mp_pago_by_id,
    get_mp_pagos_by_estado,
    get_mp_pagos_historial,
    get_mp_pending_count,
    resolver_cliente_pago,
    update_mp_movimiento_datos,
    update_mp_movimiento_estado,
    update_mp_pago_estado,
    vincular_mp_pago_cliente,
)
from app.db_pedidos import (  # noqa: F401
    add_pedido_item,
    anular_pedido,
    crear_pedido,
    delete_pedido_item,
    get_next_pedido_numero,
    get_pedido,
    get_pedido_abierto_de_mesa,
    get_pedido_items,
    get_pedidos_activos,
    pedido_total,
    set_pedido_item_nota,
)
from app.db_productos import (  # noqa: F401
    create_categoria_producto,
    create_deposito,
    create_producto,
    delete_categoria_producto,
    delete_deposito,
    delete_producto,
    generar_codigo_producto,
    get_all_depositos,
    get_all_productos,
    get_categorias_producto,
    get_default_deposito_id,
    get_deposito,
    get_producto,
    get_producto_by_codigo,
    get_stock_por_deposito,
    get_stock_producto_todos_depositos,
    set_default_deposito,
    transferir_stock,
    update_deposito,
    update_producto,
)
from app.db_recetas import (  # noqa: F401
    costo_receta,
    eliminar_receta,
    food_cost_pct,
    get_consumo_insumos,
    get_receta,
    get_reporte_food_cost,
    guardar_receta,
    producir_receta,
)
from app.db_remitos_presupuestos import (  # noqa: F401
    auto_vencimiento_presupuestos,
    convertir_presupuesto_a_remito,
    create_presupuesto,
    create_remito,
    delete_presupuesto,
    delete_remito,
    get_all_presupuestos,
    get_all_remitos,
    get_next_presupuesto_number,
    get_next_remito_number,
    get_presupuesto,
    get_presupuestos_by_client,
    get_presupuestos_count_by_estado,
    get_remito,
    get_remitos_by_client,
    search_presupuestos,
    search_remitos,
    update_presupuesto,
    update_presupuesto_pdf_path,
    update_presupuesto_remito_id,
    update_presupuesto_status,
    update_remito,
    update_remito_pdf_path,
)
from app.db_reportes import (  # noqa: F401
    get_reporte_caja,
    get_reporte_caja_medios,
    get_reporte_medios_pago,
    get_reporte_productos_top,
    get_reporte_resumen,
    get_reporte_stock_bajo,
    get_reporte_ventas,
)
from app.db_reportes_gastronomicos import reporte_gastronomia  # noqa: F401
from app.db_reservas import (  # noqa: F401
    RESERVA_BUFFER_MINUTOS,
    cancelar_reserva,
    crear_reserva,
    cumplir_reserva,
    get_proximas_reservas_por_mesa,
    get_reserva,
    get_reservas,
)
from app.db_salones import (  # noqa: F401
    create_salon,
    delete_salon,
    get_salon,
    get_salones,
    update_salon,
)
from app.db_stock import (  # noqa: F401
    _parse_modificadores,
    _resumen_modificadores,
    add_movimiento_stock,
    ajustar_stock,
    descontar_stock_venta,
    get_movimientos_stock,
    get_stock_actual,
    get_stock_todos,
)
from app.db_tesoreria import (  # noqa: F401
    create_cuenta_tesoreria,
    create_movimiento_tesoreria,
    create_transferencia_tesoreria,
    delete_cuenta_tesoreria,
    delete_movimiento_tesoreria,
    get_all_cuentas_tesoreria,
    get_cuenta_tesoreria,
    get_movimientos_tesoreria,
    get_resumen_tesoreria,
    update_cuenta_tesoreria,
)
from app.db_turnos import (  # noqa: F401
    cerrar_turno,
    create_turno,
    get_all_turnos,
    get_resumen_turno,
    get_turno,
    get_turno_activo,
    get_turno_activo_any,
    vincular_venta_turno,
)
from app.db_usuarios import (  # noqa: F401
    _DUMMY_PASSWORD_HASH,
    SIN_CAMBIOS,
    ClaveDeCifradoAusente,
    EmailNotConfigured,
    InvalidResetToken,
    _hash_password,
    _verify_password,
    borrar_config_smtp,
    check_usuario_credentials,
    create_usuario,
    delete_usuario,
    ensure_admin_user,
    ensure_demo_user,
    get_all_usuarios,
    get_usuario_by_id,
    get_usuario_by_username,
    guardar_config_smtp,
    # Config SMTP por backoffice, cifrada en reposo (libraauth v0.6.0).
    leer_config_smtp,
    resetear_password_con_token,
    # Recuperacion de contrasena por correo (libraauth v0.5.0).
    solicitar_reset_password,
    update_usuario,
    update_usuario_password,
)
from app.db_ventas import (  # noqa: F401
    acreditar_pago_qr,
    add_venta_pago,
    add_venta_pago_referencia_mp,
    anular_venta,
    crear_venta_directa,
    create_venta,
    get_all_ventas,
    get_next_venta_numero,
    get_venta,
    get_venta_by_mp_order,
    set_venta_mp_order,
    set_venta_mp_payment,
    vincular_cobros_de_venta,
    vincular_venta_factura,
    vincular_venta_remito,
)
from app.schema_propio import init_schema_propio  # noqa: F401  (lo usa init_db)

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

