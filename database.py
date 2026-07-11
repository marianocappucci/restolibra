import sqlite3
import json
import os
import hashlib
import secrets
from datetime import datetime as _datetime, timezone as _timezone, timedelta as _timedelta

_AR_TZ   = _timezone(_timedelta(hours=-3))   # America/Argentina/Buenos_Aires (sin DST)

def _ar_now() -> str:
    """Fecha y hora actual en zona horaria Argentina (UTC-3)."""
    return _datetime.now(_AR_TZ).strftime("%Y-%m-%d %H:%M:%S")


_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
DB_PATH   = os.path.join(_DATA_DIR, "restolibra.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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


# ── Clients ────────────────────────────────────────────────────────────────────

def create_client(name, address="", cuit_dni="", email="", phone="", iva_condition=""):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO clients (name, address, cuit_dni, email, phone, iva_condition) VALUES (?,?,?,?,?,?)",
            (name, address, cuit_dni, email, phone, iva_condition),
        )
        return cur.lastrowid


def get_all_clients():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM clients WHERE activo = 1 ORDER BY name")]


def get_all_clients_including_inactive():
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM clients ORDER BY name")]


def get_client(client_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        return dict(row) if row else None


def desactivar_cliente(client_id: int) -> bool:
    """Marca un cliente como inactivo (soft delete)."""
    with get_connection() as conn:
        conn.execute("UPDATE clients SET activo = 0 WHERE id = ?", (client_id,))
        return True


def tiene_presupuestos_aprobados(client_id: int) -> bool:
    """Verifica si un cliente tiene presupuestos en estado 'aceptado'."""
    with get_connection() as conn:
        result = conn.execute(
            "SELECT COUNT(*) FROM presupuestos WHERE client_id = ? AND status = 'aceptado'",
            (client_id,)
        ).fetchone()
        return result[0] > 0 if result else False


def get_facturas_by_client(cuit_dni: str, name: str, limit: int = 100) -> list:
    """Facturas asociadas a un cliente, buscando por CUIT o razón social."""
    with get_connection() as conn:
        conds, params = [], []
        if cuit_dni:
            conds.append("cliente_cuit = ?")
            params.append(cuit_dni)
        if name:
            conds.append("cliente_razon = ?")
            params.append(name)
        if not conds:
            return []
        where = " OR ".join(conds)
        rows = conn.execute(
            f"SELECT * FROM facturas WHERE {where} ORDER BY id DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


def update_client(client_id, name=None, address=None, cuit_dni=None, email=None,
                  phone=None, iva_condition=None, auto_facturar=None):
    client = get_client(client_id)
    if not client:
        return
    with get_connection() as conn:
        conn.execute(
            """UPDATE clients SET name=?, address=?, cuit_dni=?, email=?, phone=?,
               iva_condition=?, auto_facturar=? WHERE id=?""",
            (
                name          if name          is not None else client["name"],
                address       if address       is not None else client["address"],
                cuit_dni      if cuit_dni      is not None else client["cuit_dni"],
                email         if email         is not None else client["email"],
                phone         if phone         is not None else client["phone"],
                iva_condition if iva_condition is not None else client.get("iva_condition", ""),
                int(auto_facturar) if auto_facturar is not None else int(client.get("auto_facturar", 0)),
                client_id,
            ),
        )


def toggle_auto_facturar(client_id: int) -> bool:
    """Invierte el flag auto_facturar. Devuelve el nuevo valor."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE clients SET auto_facturar = 1 - auto_facturar WHERE id=?",
            (client_id,),
        )
        row = conn.execute("SELECT auto_facturar FROM clients WHERE id=?", (client_id,)).fetchone()
        return bool(row["auto_facturar"]) if row else False


def delete_client(client_id):
    with get_connection() as conn:
        remito_count = conn.execute(
            "SELECT COUNT(*) FROM remitos WHERE client_id=?", (client_id,)
        ).fetchone()[0]
        presupuesto_count = conn.execute(
            "SELECT COUNT(*) FROM presupuestos WHERE client_id=?", (client_id,)
        ).fetchone()[0]
        total_count = remito_count + presupuesto_count
        if total_count > 0:
            msg_parts = []
            if remito_count > 0:
                msg_parts.append(f"{remito_count} remito(s)")
            if presupuesto_count > 0:
                msg_parts.append(f"{presupuesto_count} presupuesto(s)")
            raise ValueError(f"El cliente tiene {' y '.join(msg_parts)} asociado(s) y no puede eliminarse.")
        conn.execute("DELETE FROM clients WHERE id=?", (client_id,))


# ── Remitos ────────────────────────────────────────────────────────────────────

def get_next_remito_number():
    with get_connection() as conn:
        row = conn.execute("SELECT MAX(id) FROM remitos").fetchone()
        next_id = (row[0] or 0) + 1
        return f"0001-{next_id:08d}"


def create_remito(number, date, client_id, client_name, client_address, client_cuit,
                  client_email, client_phone, items, subtotal, tax_rate, tax_amount,
                  total, observations="", pdf_path="", usuario_id=None):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO remitos
               (number, date, client_id, client_name, client_address, client_cuit,
                client_email, client_phone, items, subtotal, tax_rate, tax_amount,
                total, observations, pdf_path, usuario_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                number, date, client_id, client_name, client_address, client_cuit,
                client_email, client_phone, json.dumps(items, ensure_ascii=False),
                subtotal, tax_rate, tax_amount, total, observations, pdf_path, usuario_id,
            ),
        )
        return cur.lastrowid


def update_remito_pdf_path(remito_id, pdf_path):
    with get_connection() as conn:
        conn.execute("UPDATE remitos SET pdf_path=? WHERE id=?", (pdf_path, remito_id))


def get_all_remitos(limit=100):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM remitos ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


def get_remito(remito_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM remitos WHERE id=?", (remito_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["items"] = json.loads(d["items"])
        return d


def get_remitos_by_client(client_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM remitos WHERE client_id=? ORDER BY id DESC", (client_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


def search_remitos(query):
    q = f"%{query}%"
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM remitos
               WHERE number LIKE ? OR client_name LIKE ? OR observations LIKE ?
               ORDER BY id DESC""",
            (q, q, q),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


# ── Presupuestos ───────────────────────────────────────────────────────────────

def get_next_presupuesto_number():
    with get_connection() as conn:
        row = conn.execute("SELECT MAX(id) FROM presupuestos").fetchone()
        next_id = (row[0] or 0) + 1
        return f"PRES-{next_id:08d}"


def auto_vencimiento_presupuestos():
    """Marca como 'vencido' los presupuestos enviados cuya validez expiró."""
    with get_connection() as conn:
        conn.execute(
            """UPDATE presupuestos SET status='vencido'
               WHERE status IN ('enviado', 'pendiente')
               AND valid_until < date('now')"""
        )


def create_presupuesto(number, date, valid_until, client_id, client_name, client_address,
                       client_cuit, client_email, client_phone, items, subtotal, tax_rate,
                       tax_amount, total, observations="", pdf_path="", status="borrador",
                       usuario_id=None):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO presupuestos
               (number, date, valid_until, status, client_id, client_name, client_address,
                client_cuit, client_email, client_phone, items, subtotal, tax_rate,
                tax_amount, total, observations, pdf_path, usuario_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                number, date, valid_until, status, client_id, client_name, client_address,
                client_cuit, client_email, client_phone, json.dumps(items, ensure_ascii=False),
                subtotal, tax_rate, tax_amount, total, observations, pdf_path, usuario_id,
            ),
        )
        return cur.lastrowid


def update_presupuesto_pdf_path(presupuesto_id, pdf_path):
    with get_connection() as conn:
        conn.execute("UPDATE presupuestos SET pdf_path=? WHERE id=?", (pdf_path, presupuesto_id))


def update_presupuesto_status(presupuesto_id, status):
    with get_connection() as conn:
        conn.execute("UPDATE presupuestos SET status=? WHERE id=?", (status, presupuesto_id))


def update_presupuesto_remito_id(presupuesto_id, remito_id):
    with get_connection() as conn:
        conn.execute("UPDATE presupuestos SET remito_id=? WHERE id=?", (remito_id, presupuesto_id))


def get_all_presupuestos(limit=100, estado=None):
    auto_vencimiento_presupuestos()
    with get_connection() as conn:
        if estado:
            rows = conn.execute(
                "SELECT * FROM presupuestos WHERE status=? ORDER BY id DESC LIMIT ?",
                (estado, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM presupuestos ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


def get_presupuestos_count_by_estado():
    auto_vencimiento_presupuestos()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM presupuestos GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}


def get_presupuesto(presupuesto_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM presupuestos WHERE id=?", (presupuesto_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["items"] = json.loads(d["items"])
        return d


def get_presupuestos_by_client(client_id):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM presupuestos WHERE client_id=? ORDER BY id DESC", (client_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


def search_presupuestos(query, estado=None):
    auto_vencimiento_presupuestos()
    q = f"%{query}%"
    with get_connection() as conn:
        if estado:
            rows = conn.execute(
                """SELECT * FROM presupuestos
                   WHERE status=? AND (number LIKE ? OR client_name LIKE ? OR observations LIKE ?)
                   ORDER BY id DESC""",
                (estado, q, q, q),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM presupuestos
                   WHERE number LIKE ? OR client_name LIKE ? OR observations LIKE ?
                   ORDER BY id DESC""",
                (q, q, q),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


# ── Eliminar ───────────────────────────────────────────────────────────────────

def delete_remito(remito_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM remitos WHERE id=?", (remito_id,))


def delete_presupuesto(presupuesto_id):
    """Borra un presupuesto solo si está en estado 'borrador'."""
    with get_connection() as conn:
        presupuesto = conn.execute(
            "SELECT status FROM presupuestos WHERE id=?", (presupuesto_id,)
        ).fetchone()
        if not presupuesto:
            raise ValueError("Presupuesto no encontrado")
        status = dict(presupuesto)["status"] if presupuesto else None
        if status != "borrador":
            raise ValueError(f"No se puede borrar un presupuesto {status}")
        conn.execute("DELETE FROM presupuestos WHERE id=?", (presupuesto_id,))


# ── Actualizar ──────────────────────────────────────────────────────────────────

def update_remito(remito_id, date, client_id, client_name, client_address, client_cuit,
                  client_email, client_phone, items, subtotal, tax_rate, tax_amount,
                  total, observations=""):
    with get_connection() as conn:
        conn.execute(
            """UPDATE remitos
               SET date=?, client_id=?, client_name=?, client_address=?, client_cuit=?,
                   client_email=?, client_phone=?, items=?, subtotal=?, tax_rate=?,
                   tax_amount=?, total=?, observations=?
               WHERE id=?""",
            (
                date, client_id, client_name, client_address, client_cuit,
                client_email, client_phone, json.dumps(items, ensure_ascii=False),
                subtotal, tax_rate, tax_amount, total, observations, remito_id,
            ),
        )


def update_presupuesto(presupuesto_id, date, valid_until, status, client_id, client_name,
                       client_address, client_cuit, client_email, client_phone, items,
                       subtotal, tax_rate, tax_amount, total, observations=""):
    with get_connection() as conn:
        conn.execute(
            """UPDATE presupuestos
               SET date=?, valid_until=?, status=?, client_id=?, client_name=?,
                   client_address=?, client_cuit=?, client_email=?, client_phone=?,
                   items=?, subtotal=?, tax_rate=?, tax_amount=?, total=?, observations=?
               WHERE id=?""",
            (
                date, valid_until, status, client_id, client_name, client_address,
                client_cuit, client_email, client_phone, json.dumps(items, ensure_ascii=False),
                subtotal, tax_rate, tax_amount, total, observations, presupuesto_id,
            ),
        )


# ── Configuración ARCA ──────────────────────────────────────────────────────────

def crear_arca_config(empresa, cuit, punto_venta, clave_path, certificado_path,
                      ambiente="homologacion", alias=""):
    """Crea configuración ARCA para una empresa."""
    with get_connection() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO arca_config
                   (empresa, cuit, punto_venta, clave_path, certificado_path, ambiente, alias)
                   VALUES (?,?,?,?,?,?,?)""",
                (empresa, cuit, punto_venta, clave_path, certificado_path, ambiente, alias),
            )
            return cur.lastrowid
        except Exception as e:
            raise ValueError(f"Error creando configuración ARCA: {str(e)}")


def obtener_arca_config(empresa):
    """Obtiene configuración ARCA por nombre de empresa."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM arca_config WHERE empresa=? AND activo=1", (empresa,)
        ).fetchone()
        return dict(row) if row else None


def obtener_todas_arca_configs():
    """Obtiene todas las configuraciones ARCA activas."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM arca_config WHERE activo=1 ORDER BY empresa"
        ).fetchall()
        return [dict(r) for r in rows]


def actualizar_arca_config(empresa, cuit=None, punto_venta=None, clave_path=None,
                          certificado_path=None, ambiente=None, alias=None):
    """Actualiza configuración ARCA."""
    with get_connection() as conn:
        config = obtener_arca_config(empresa)
        if not config:
            raise ValueError(f"Configuración ARCA no encontrada para: {empresa}")

        conn.execute(
            """UPDATE arca_config
               SET cuit=?, punto_venta=?, clave_path=?, certificado_path=?,
                   ambiente=?, alias=?, updated_at=datetime('now')
               WHERE empresa=?""",
            (
                cuit if cuit is not None else config["cuit"],
                punto_venta if punto_venta is not None else config["punto_venta"],
                clave_path if clave_path is not None else config["clave_path"],
                certificado_path if certificado_path is not None else config["certificado_path"],
                ambiente if ambiente is not None else config["ambiente"],
                alias if alias is not None else config["alias"],
                empresa,
            ),
        )


def eliminar_arca_config(empresa):
    """Marca como inactivo la configuración ARCA."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE arca_config SET activo=0 WHERE empresa=?", (empresa,)
        )


# ── Facturas ────────────────────────────────────────────────────────────────────

def get_next_factura_numero(punto_venta, tipo):
    """Devuelve el próximo número correlativo para tipo+punto_venta."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(numero) FROM facturas WHERE punto_venta=? AND tipo=?",
            (punto_venta, tipo),
        ).fetchone()
        return (row[0] or 0) + 1


def create_factura(tipo, punto_venta, numero, fecha, cliente_cuit, cliente_razon,
                   cliente_iva_cond, items, subtotal, iva_amount, total,
                   concepto=1, cae="", cae_vto="", observaciones="", pdf_path="",
                   cliente_domicilio="", fch_serv_desde="", fch_serv_hasta="",
                   fch_vto_pago="", cbte_asoc_tipo=0, cbte_asoc_pv=0, cbte_asoc_nro=0,
                   condicion_venta="", usuario_id=None):
    """Crea una nueva factura electrónica."""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO facturas
               (tipo, punto_venta, numero, fecha, cliente_cuit, cliente_razon,
                cliente_iva_cond, items, subtotal, iva_amount, total, concepto,
                cae, cae_vto, observaciones, pdf_path, cliente_domicilio,
                fch_serv_desde, fch_serv_hasta, fch_vto_pago,
                cbte_asoc_tipo, cbte_asoc_pv, cbte_asoc_nro, condicion_venta, usuario_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tipo, punto_venta, numero, fecha, cliente_cuit, cliente_razon,
             cliente_iva_cond, json.dumps(items, ensure_ascii=False), subtotal,
             iva_amount, total, concepto, cae, cae_vto, observaciones, pdf_path,
             cliente_domicilio, fch_serv_desde, fch_serv_hasta, fch_vto_pago,
             cbte_asoc_tipo, cbte_asoc_pv, cbte_asoc_nro, condicion_venta, usuario_id),
        )
        return cur.lastrowid


_TIPOS_FACTURA = (1, 6, 11)
_TIPOS_NC      = (3, 8, 13)
_TIPOS_ND      = (2, 7, 12)

_VISTA_TIPOS = {
    "facturas": _TIPOS_FACTURA,
    "nc":       _TIPOS_NC,
    "nd":       _TIPOS_ND,
}


def get_all_facturas(limit=100, vista="facturas"):
    """Obtiene facturas, notas de crédito o notas de débito (últimas primero)."""
    tipos = _VISTA_TIPOS.get(vista, _TIPOS_FACTURA)
    placeholders = ",".join("?" * len(tipos))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM facturas WHERE tipo IN ({placeholders}) ORDER BY id DESC LIMIT ?",
            (*tipos, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


def get_facturas_filtradas(desde="", hasta="", q="", vista="facturas", limit=50, offset=0):
    """Listado de facturas con filtros de fecha, búsqueda y paginación."""
    solo_sin_cobrar = (vista == "sin_cobrar")
    tipos = _VISTA_TIPOS.get("facturas" if solo_sin_cobrar else vista, _TIPOS_FACTURA)
    ph = ",".join("?" * len(tipos))
    conds = [f"f.tipo IN ({ph})"]
    params = list(tipos)
    if desde:
        conds.append("f.fecha >= ?"); params.append(desde)
    if hasta:
        conds.append("f.fecha <= ?"); params.append(hasta)
    if q:
        conds.append("(CAST(f.numero AS TEXT) LIKE ? OR f.cliente_razon LIKE ? OR f.observaciones LIKE ?)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    _cc_excl = "AND LOWER(cm.medio_pago) NOT IN ('cuenta corriente','cuenta_corriente')"
    if solo_sin_cobrar:
        conds.append("f.cae != '' AND f.cae IS NOT NULL AND f.cae != 'PENDIENTE'")
        conds.append(f"""
            COALESCE((SELECT SUM(cm.monto) FROM caja_movimientos cm
                      WHERE cm.factura_id=f.id AND cm.tipo='ingreso' {_cc_excl}), 0) < f.total
        """)
    where = " AND ".join(conds)
    cobrada_col = f"""
        COALESCE((SELECT SUM(cm.monto) FROM caja_movimientos cm
                  WHERE cm.factura_id=f.id AND cm.tipo='ingreso' {_cc_excl}), 0) AS total_cobrado
    """
    with get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM facturas f WHERE {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT f.*, {cobrada_col} FROM facturas f WHERE {where} ORDER BY f.id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["items"] = json.loads(d["items"])
        result.append(d)
    return {"items": result, "total": total}


def get_factura(factura_id):
    """Obtiene una factura por ID."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM facturas WHERE id=?", (factura_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["items"] = json.loads(d["items"])
        return d


def update_factura_cae(factura_id, cae, cae_vto):
    """Actualiza CAE de una factura después de obtenerlo de ARCA."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE facturas SET cae=?, cae_vto=? WHERE id=?",
            (cae, cae_vto, factura_id)
        )


def update_factura_pdf_path(factura_id, pdf_path):
    """Actualiza el path del PDF de la factura."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE facturas SET pdf_path=? WHERE id=?",
            (pdf_path, factura_id)
        )


def search_facturas(query, vista="facturas"):
    """Busca facturas por número, cliente u observaciones."""
    tipos = _VISTA_TIPOS.get(vista, _TIPOS_FACTURA)
    placeholders = ",".join("?" * len(tipos))
    q = f"%{query}%"
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT * FROM facturas
               WHERE tipo IN ({placeholders})
                 AND (numero LIKE ? OR cliente_razon LIKE ? OR observaciones LIKE ?)
               ORDER BY id DESC""",
            (*tipos, q, q, q),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


def get_notas_de_factura(tipo, punto_venta, numero, tipos_nota):
    """Devuelve notas (NC o ND) que referencian un comprobante."""
    placeholders = ",".join("?" * len(tipos_nota))
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT * FROM facturas
               WHERE tipo IN ({placeholders})
                 AND cbte_asoc_tipo=? AND cbte_asoc_pv=? AND cbte_asoc_nro=?
               ORDER BY id DESC""",
            (*tipos_nota, tipo, punto_venta, numero),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d["items"])
            result.append(d)
        return result


def get_nc_de_factura(tipo, punto_venta, numero):
    """Devuelve las notas de crédito que anulan un comprobante."""
    return get_notas_de_factura(tipo, punto_venta, numero, _TIPOS_NC)


def get_nd_de_factura(tipo, punto_venta, numero):
    """Devuelve las notas de débito asociadas a un comprobante."""
    return get_notas_de_factura(tipo, punto_venta, numero, _TIPOS_ND)


def get_factura_por_tipo_pv_nro(tipo, punto_venta, numero):
    """Busca un comprobante por tipo + punto de venta + número."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM facturas WHERE tipo=? AND punto_venta=? AND numero=?",
            (tipo, punto_venta, numero),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["items"] = json.loads(d["items"])
        return d


def delete_factura(factura_id):
    """Elimina una factura."""
    with get_connection() as conn:
        conn.execute("DELETE FROM facturas WHERE id=?", (factura_id,))


# ── Cajas (configuración de cajas) ────────────────────────────────────────────

MEDIOS_PAGO_LABELS = {
    "efectivo":         "Efectivo",
    "transferencia":    "Transferencia",
    "mercadopago":      "Mercado Pago",
    "cuenta_dni":       "Cuenta DNI",
    "billetera":        "Otras billeteras",
    "cuenta_corriente": "Cuenta corriente",
}


def get_all_cajas() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM cajas ORDER BY es_default DESC, nombre"
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["medios_pago"] = json.loads(d["medios_pago"] or "[]")
        result.append(d)
    return result


def get_caja_config(cid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM cajas WHERE id=?", (cid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["medios_pago"] = json.loads(d["medios_pago"] or "[]")
    return d


def get_default_caja_id() -> int | None:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM cajas WHERE es_default=1 LIMIT 1").fetchone()
        if not row:
            row = conn.execute("SELECT id FROM cajas ORDER BY id LIMIT 1").fetchone()
    return row[0] if row else None


def create_caja_config(nombre: str, descripcion: str, medios_pago: list) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO cajas (nombre, descripcion, medios_pago) VALUES (?,?,?)",
            (nombre, descripcion, json.dumps(medios_pago)),
        )
        return cur.lastrowid


def update_caja_config(cid: int, nombre: str, descripcion: str, medios_pago: list, activo: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE cajas SET nombre=?, descripcion=?, medios_pago=?, activo=? WHERE id=?",
            (nombre, descripcion, json.dumps(medios_pago), activo, cid),
        )


def set_default_caja(cid: int):
    with get_connection() as conn:
        conn.execute("UPDATE cajas SET es_default=0")
        conn.execute("UPDATE cajas SET es_default=1 WHERE id=?", (cid,))


def delete_caja_config(cid: int):
    with get_connection() as conn:
        tiene = conn.execute(
            "SELECT COUNT(*) FROM caja_movimientos WHERE caja_id=?", (cid,)
        ).fetchone()[0]
        if tiene:
            raise ValueError("No se puede eliminar una caja con movimientos registrados.")
        if conn.execute("SELECT es_default FROM cajas WHERE id=?", (cid,)).fetchone()[0]:
            raise ValueError("No se puede eliminar la caja por defecto.")
        conn.execute("DELETE FROM cajas WHERE id=?", (cid,))


# ── Caja ───────────────────────────────────────────────────────────────────────

def create_caja_movimiento(fecha, tipo, concepto, monto, referencia="", factura_id=None,
                           usuario_id=None, caja_id=None, medio_pago=""):
    with get_connection() as conn:
        # Idempotencia: si ya existe un movimiento con la misma referencia, no duplicar
        if referencia:
            exists = conn.execute(
                "SELECT id FROM caja_movimientos WHERE referencia=? LIMIT 1", (referencia,)
            ).fetchone()
            if exists:
                return exists[0]
        _caja_id = caja_id or get_default_caja_id()
        cur = conn.execute(
            """INSERT INTO caja_movimientos
               (fecha, tipo, concepto, monto, referencia, factura_id, usuario_id, caja_id, medio_pago)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (fecha, tipo, concepto, float(monto), referencia, factura_id, usuario_id, _caja_id, medio_pago),
        )
        return cur.lastrowid


def get_caja_movimientos(desde=None, hasta=None, limit=500, caja_id=None):
    with get_connection() as conn:
        where, params = [], []
        if desde and hasta:
            where.append("cm.fecha BETWEEN ? AND ?"); params += [desde, hasta]
        if caja_id:
            where.append("cm.caja_id = ?"); params.append(caja_id)
        sql = """SELECT cm.*, c.nombre AS caja_nombre, u.nombre AS usuario_nombre
                 FROM caja_movimientos cm
                 LEFT JOIN cajas c ON c.id = cm.caja_id
                 LEFT JOIN usuarios u ON u.id = cm.usuario_id"""
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY cm.fecha DESC, cm.id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_caja_resumen(desde=None, hasta=None, caja_id=None):
    """Devuelve {ingresos, egresos, saldo_periodo, saldo_total}."""
    with get_connection() as conn:
        where, params = [], []
        if desde and hasta:
            where.append("fecha BETWEEN ? AND ?"); params += [desde, hasta]
        if caja_id:
            where.append("caja_id = ?"); params.append(caja_id)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        row = conn.execute(
            f"""SELECT
                  COALESCE(SUM(CASE WHEN tipo='ingreso' THEN monto ELSE 0 END), 0) AS ingresos,
                  COALESCE(SUM(CASE WHEN tipo='egreso'  THEN monto ELSE 0 END), 0) AS egresos
                FROM caja_movimientos {w}""",
            params,
        ).fetchone()
        ingresos = row["ingresos"]
        egresos  = row["egresos"]

        total = conn.execute(
            """SELECT COALESCE(SUM(CASE WHEN tipo='ingreso' THEN monto ELSE -monto END), 0)
               FROM caja_movimientos"""
        ).fetchone()[0]

        return {
            "ingresos":     ingresos,
            "egresos":      egresos,
            "saldo_periodo": ingresos - egresos,
            "saldo_total":  total,
        }


def get_cobro_factura(factura_id):
    """Devuelve el último movimiento de cobro de una factura, o None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM caja_movimientos WHERE factura_id=? AND tipo='ingreso'"
            " AND LOWER(medio_pago) NOT IN ('cuenta corriente','cuenta_corriente')"
            " ORDER BY id DESC LIMIT 1",
            (factura_id,),
        ).fetchone()
        return dict(row) if row else None


def get_cobros_factura(factura_id) -> list[dict]:
    """Devuelve todos los movimientos de cobro de una factura."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM caja_movimientos WHERE factura_id=? AND tipo='ingreso'"
            " AND LOWER(medio_pago) NOT IN ('cuenta corriente','cuenta_corriente')"
            " ORDER BY id",
            (factura_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_caja_movimiento(mov_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM caja_movimientos WHERE id=?", (mov_id,))


# ── MercadoPago pagos ──────────────────────────────────────────────────────────

def get_mp_pago(mp_payment_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mp_pagos WHERE mp_payment_id=?", (str(mp_payment_id),)
        ).fetchone()
        return dict(row) if row else None


def create_mp_pago(mp_payment_id: str, status: str, monto: float,
                   payer_email: str, payer_name: str, factura_id=None,
                   estado_factura: str = None, payment_type: str = None,
                   payment_method: str = None, descripcion_mp: str = None,
                   payer_id_type: str = None, payer_id_number: str = None):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO mp_pagos
               (mp_payment_id, status, monto, payer_email, payer_name, factura_id,
                estado_factura, payment_type, payment_method, descripcion_mp,
                payer_id_type, payer_id_number)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(mp_payment_id), status, float(monto), payer_email, payer_name, factura_id,
             estado_factura, payment_type, payment_method, descripcion_mp,
             payer_id_type, payer_id_number),
        )
        return cur.lastrowid


def get_mp_pago_by_id(id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM mp_pagos WHERE id=?", (id,)).fetchone()
        return dict(row) if row else None


def get_mp_pagos_by_estado(estado: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM mp_pagos WHERE estado_factura=? ORDER BY created_at DESC",
            (estado,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_mp_pagos_historial(limit: int = 50):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM mp_pagos
               WHERE estado_factura IN ('facturado', 'ignorado')
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_mp_pago_estado(id: int, estado: str, factura_id=None):
    with get_connection() as conn:
        if factura_id is not None:
            conn.execute(
                "UPDATE mp_pagos SET estado_factura=?, factura_id=? WHERE id=?",
                (estado, factura_id, id),
            )
        else:
            conn.execute(
                "UPDATE mp_pagos SET estado_factura=? WHERE id=?",
                (estado, id),
            )


def get_client_by_email(email: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE email=? LIMIT 1", (email,)
        ).fetchone()
        return dict(row) if row else None


def get_client_by_cuit(cuit: str):
    """Busca cliente por CUIT normalizando guiones (ej: 20317819162 == 20-31781916-2)."""
    normalized = (cuit or "").replace("-", "").strip()
    if not normalized:
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE REPLACE(cuit_dni, '-', '') = ? LIMIT 1",
            (normalized,),
        ).fetchone()
    return dict(row) if row else None


# ── MercadoPago movimientos (transferencias bancarias entrantes) ───────────────

def get_mp_movimiento_by_mp_id(mp_movement_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mp_movimientos WHERE mp_movement_id=?", (str(mp_movement_id),)
        ).fetchone()
        return dict(row) if row else None


def create_mp_movimiento(mp_movement_id: str, tipo: str, monto: float, fecha: str,
                         descripcion: str = "", origen_nombre: str = "",
                         origen_banco: str = "", origen_cbu: str = "",
                         payer_email: str = "", payer_name: str = "",
                         payer_id_type: str = "", payer_id_number: str = "",
                         estado_factura: str = "pendiente"):
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO mp_movimientos
               (mp_movement_id, tipo, monto, fecha, descripcion, origen_nombre, origen_banco,
                origen_cbu, payer_email, payer_name, payer_id_type, payer_id_number, estado_factura)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(mp_movement_id), tipo, float(monto), fecha, descripcion,
             origen_nombre, origen_banco, origen_cbu,
             payer_email, payer_name, payer_id_type, payer_id_number, estado_factura),
        )
        return cur.lastrowid


def get_mp_movimiento_by_id(id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM mp_movimientos WHERE id=?", (id,)).fetchone()
        return dict(row) if row else None


def get_mp_movimientos_by_estado(estado: str):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM mp_movimientos WHERE estado_factura=? ORDER BY fecha DESC, created_at DESC",
            (estado,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_mp_movimientos_historial(limit: int = 50):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM mp_movimientos
               WHERE estado_factura IN ('facturado', 'ignorado')
               ORDER BY fecha DESC, created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_mp_movimiento_datos(id: int, payer_email: str = None, payer_name: str = None,
                               payer_id_type: str = None, payer_id_number: str = None):
    fields = {}
    if payer_email is not None:
        fields["payer_email"] = payer_email
    if payer_name is not None:
        fields["payer_name"] = payer_name
    if payer_id_type is not None:
        fields["payer_id_type"] = payer_id_type
    if payer_id_number is not None:
        fields["payer_id_number"] = payer_id_number
    if not fields:
        return
    set_clause = ", ".join(f"{k}=?" for k in fields)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE mp_movimientos SET {set_clause} WHERE id=?",
            (*fields.values(), id),
        )


def update_mp_movimiento_estado(id: int, estado: str, factura_id=None):
    with get_connection() as conn:
        if factura_id is not None:
            conn.execute(
                "UPDATE mp_movimientos SET estado_factura=?, factura_id=? WHERE id=?",
                (estado, factura_id, id),
            )
        else:
            conn.execute(
                "UPDATE mp_movimientos SET estado_factura=? WHERE id=?",
                (estado, id),
            )


def get_mp_pending_count() -> int:
    with get_connection() as conn:
        return conn.execute(
            """SELECT
               (SELECT COUNT(*) FROM mp_pagos WHERE estado_factura='pendiente') +
               (SELECT COUNT(*) FROM mp_movimientos WHERE estado_factura='pendiente')"""
        ).fetchone()[0]


def vincular_mp_pago_cliente(mp_pago_id: int, payer_email: str, payer_name: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE mp_pagos SET payer_email=?, payer_name=? WHERE id=?",
            (payer_email, payer_name, mp_pago_id),
        )


# ── Dashboard ──────────────────────────────────────────────────────────────────

def get_dashboard_data(mes_desde: str, mes_hasta: str) -> dict:
    """Devuelve todos los datos necesarios para el dashboard en una sola llamada."""
    _TIPOS_FACTURA = (1, 6, 11)
    with get_connection() as conn:
        # KPI 1: total facturado en el mes (solo facturas, no NC/ND)
        row = conn.execute(
            "SELECT COALESCE(SUM(total), 0) FROM facturas WHERE tipo IN (1,6,11) AND fecha BETWEEN ? AND ?",
            (mes_desde, mes_hasta),
        ).fetchone()
        facturado_mes = row[0]

        # KPI 2/3: ingresos y egresos de caja del mes
        row = conn.execute(
            """SELECT
                 COALESCE(SUM(CASE WHEN tipo='ingreso' THEN monto ELSE 0 END), 0),
                 COALESCE(SUM(CASE WHEN tipo='egreso'  THEN monto ELSE 0 END), 0)
               FROM caja_movimientos WHERE fecha BETWEEN ? AND ?""",
            (mes_desde, mes_hasta),
        ).fetchone()
        cobrado_mes = row[0]
        egresos_mes = row[1]

        # KPI 4: saldo total de caja (histórico)
        saldo_total = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN tipo='ingreso' THEN monto ELSE -monto END), 0) FROM caja_movimientos"
        ).fetchone()[0]

        # Cantidad de facturas emitidas en el mes
        cant_facturas_mes = conn.execute(
            "SELECT COUNT(*) FROM facturas WHERE tipo IN (1,6,11) AND fecha BETWEEN ? AND ?",
            (mes_desde, mes_hasta),
        ).fetchone()[0]

        # Facturas sin cobrar (tipo factura, sin ingreso en caja)
        rows = conn.execute(
            """SELECT f.id, f.tipo, f.punto_venta, f.numero, f.fecha, f.cliente_razon, f.total
               FROM facturas f
               LEFT JOIN caja_movimientos c ON c.factura_id = f.id AND c.tipo = 'ingreso'
               WHERE f.tipo IN (1,6,11) AND c.id IS NULL
               ORDER BY f.id DESC LIMIT 8""",
        ).fetchall()
        facturas_sin_cobrar = [dict(r) for r in rows]

        # Presupuestos pendientes de respuesta
        rows = conn.execute(
            "SELECT id, number, date, client_name, total FROM presupuestos WHERE status IN ('borrador','enviado','pendiente') ORDER BY id DESC LIMIT 8"
        ).fetchall()
        presupuestos_pendientes = [dict(r) for r in rows]

        # Últimos 6 movimientos de caja
        rows = conn.execute(
            "SELECT * FROM caja_movimientos ORDER BY fecha DESC, id DESC LIMIT 6"
        ).fetchall()
        ultimos_movimientos = [dict(r) for r in rows]

    return {
        "facturado_mes":        facturado_mes,
        "cobrado_mes":          cobrado_mes,
        "egresos_mes":          egresos_mes,
        "saldo_total":          saldo_total,
        "cant_facturas_mes":    cant_facturas_mes,
        "facturas_sin_cobrar":  facturas_sin_cobrar,
        "presupuestos_pendientes": presupuestos_pendientes,
        "ultimos_movimientos":  ultimos_movimientos,
    }


# ── Usuarios ──────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(32)
    dk   = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"pbkdf2:sha256:{salt}:{dk.hex()}"


def _verify_password(stored: str, provided: str) -> bool:
    try:
        _, algo, salt, stored_hash = stored.split(":")
        dk = hashlib.pbkdf2_hmac(algo, provided.encode(), salt.encode(), 260_000)
        return dk.hex() == stored_hash
    except Exception:
        return False


def create_usuario(username: str, nombre: str, email: str,
                   password: str, role: str = "operador") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO usuarios (username, nombre, email, password_hash, role) VALUES (?,?,?,?,?)",
            (username.strip(), nombre.strip(), email.strip(),
             _hash_password(password), role),
        )
        return cur.lastrowid


def get_usuario_by_username(username: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE username=? AND activo=1", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_usuario_by_id(uid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        return dict(row) if row else None


def get_all_usuarios() -> list:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM usuarios ORDER BY role DESC, username"
        ).fetchall()]


def update_usuario(uid: int, nombre: str, email: str, role: str, activo: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE usuarios SET nombre=?, email=?, role=?, activo=? WHERE id=?",
            (nombre.strip(), email.strip(), role, activo, uid),
        )


def update_usuario_password(uid: int, new_password: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE usuarios SET password_hash=? WHERE id=?",
            (_hash_password(new_password), uid),
        )


def delete_usuario(uid: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM usuarios WHERE id=?", (uid,))


def check_usuario_credentials(username: str, password: str) -> dict | None:
    """Devuelve el usuario si las credenciales son válidas, None si no."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE username=? AND activo=1", (username,)
        ).fetchone()
    if not row:
        return None
    user = dict(row)
    return user if _verify_password(user["password_hash"], password) else None


def ensure_admin_user():
    """Crea el usuario admin por defecto si no existe ningún usuario."""
    if get_all_usuarios():
        return
    username = os.environ.get("ADMIN_USER", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "")
    nombre   = os.environ.get("ADMIN_NOMBRE", "Administrador")
    if not password:
        password = secrets.token_urlsafe(12)
        print(f"[WARN] ADMIN_PASSWORD no configurado. Contraseña generada: {password}")
    create_usuario(username=username, nombre=nombre, email="", password=password, role="admin")
    print(f"[INFO] Usuario admin '{username}' creado.")


# ── Depósitos ─────────────────────────────────────────────────────────────────

def get_all_depositos() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM depositos ORDER BY es_default DESC, nombre"
        ).fetchall()
    return [dict(r) for r in rows]


def get_deposito(did: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM depositos WHERE id=?", (did,)).fetchone()
    return dict(row) if row else None


def get_default_deposito_id() -> int | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM depositos WHERE es_default=1 LIMIT 1"
        ).fetchone()
        if not row:
            row = conn.execute("SELECT id FROM depositos ORDER BY id LIMIT 1").fetchone()
    return row[0] if row else None


def create_deposito(nombre: str, descripcion: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO depositos (nombre, descripcion) VALUES (?,?)",
            (nombre, descripcion),
        )
        return cur.lastrowid


def update_deposito(did: int, nombre: str, descripcion: str, activo: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE depositos SET nombre=?, descripcion=?, activo=? WHERE id=?",
            (nombre, descripcion, activo, did),
        )


def set_default_deposito(did: int):
    with get_connection() as conn:
        conn.execute("UPDATE depositos SET es_default=0")
        conn.execute("UPDATE depositos SET es_default=1 WHERE id=?", (did,))


def delete_deposito(did: int):
    with get_connection() as conn:
        tiene = conn.execute(
            "SELECT COUNT(*) FROM movimientos_stock WHERE deposito_id=?", (did,)
        ).fetchone()[0]
        if tiene:
            raise ValueError("No se puede eliminar un depósito con movimientos de stock.")
        es_default = conn.execute(
            "SELECT es_default FROM depositos WHERE id=?", (did,)
        ).fetchone()
        if es_default and es_default[0]:
            raise ValueError("No se puede eliminar el depósito por defecto.")
        conn.execute("DELETE FROM depositos WHERE id=?", (did,))


def get_stock_por_deposito(deposito_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.id, p.codigo, p.nombre, p.unidad, p.categoria,
                   p.stock_minimo, p.activo,
                   COALESCE(SUM(m.cantidad), 0) AS stock_actual
            FROM productos p
            LEFT JOIN movimientos_stock m ON m.producto_id = p.id AND m.deposito_id = ?
            WHERE p.activo = 1
            GROUP BY p.id
            HAVING stock_actual != 0 OR p.stock_minimo > 0
            ORDER BY p.nombre
        """, (deposito_id,)).fetchall()
    return [dict(r) for r in rows]


def get_stock_producto_todos_depositos(producto_id: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT d.id, d.nombre, d.es_default,
                   COALESCE(SUM(m.cantidad), 0) AS stock_actual
            FROM depositos d
            LEFT JOIN movimientos_stock m ON m.deposito_id = d.id AND m.producto_id = ?
            WHERE d.activo = 1
            GROUP BY d.id
            ORDER BY d.es_default DESC, d.nombre
        """, (producto_id,)).fetchall()
    return [dict(r) for r in rows]


def transferir_stock(producto_id: int, origen_id: int, destino_id: int,
                     cantidad: float, usuario_id: int | None = None,
                     fecha: str = "", observaciones: str = ""):
    from datetime import date as _date
    _fecha = fecha or _date.today().isoformat()
    stock_origen = 0.0
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(cantidad),0) FROM movimientos_stock WHERE producto_id=? AND deposito_id=?",
            (producto_id, origen_id),
        ).fetchone()
        stock_origen = float(row[0])
    if cantidad > stock_origen:
        raise ValueError(f"Stock insuficiente en depósito origen (disponible: {stock_origen}).")
    ref = observaciones or "Transferencia entre depósitos"
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO movimientos_stock (producto_id, tipo, cantidad, referencia, usuario_id, fecha, deposito_id)
               VALUES (?,?,?,?,?,?,?)""",
            (producto_id, "transferencia_salida", -cantidad, ref, usuario_id, _fecha, origen_id),
        )
        conn.execute(
            """INSERT INTO movimientos_stock (producto_id, tipo, cantidad, referencia, usuario_id, fecha, deposito_id)
               VALUES (?,?,?,?,?,?,?)""",
            (producto_id, "transferencia_entrada", cantidad, ref, usuario_id, _fecha, destino_id),
        )


# ── Categorías de producto ────────────────────────────────────────────────────

def get_categorias_producto() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT id, nombre FROM categorias_producto ORDER BY nombre").fetchall()
    return [dict(r) for r in rows]


def create_categoria_producto(nombre: str) -> int:
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO categorias_producto (nombre) VALUES (?)", (nombre,))
        return cur.lastrowid


def delete_categoria_producto(cid: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM categorias_producto WHERE id=?", (cid,))


# ── Productos ─────────────────────────────────────────────────────────────────

def create_producto(nombre: str, codigo: str = "", descripcion: str = "",
                    precio_venta: float = 0, precio_costo: float = 0,
                    unidad: str = "u", categoria: str = "",
                    stock_minimo: float = 0, estacion: str = "",
                    vendible: int = 1) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO productos
               (codigo, nombre, descripcion, precio_venta, precio_costo,
                unidad, categoria, stock_minimo, estacion, vendible)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (codigo or None, nombre, descripcion, precio_venta, precio_costo,
             unidad, categoria, stock_minimo, estacion or "", vendible),
        )
        return cur.lastrowid


def generar_codigo_producto(categoria: str = "") -> str:
    """Genera un código único para un producto: prefijo según la categoría
    (3 primeras letras/dígitos en mayúscula, o 'PRD' si no hay) + secuencia
    correlativa dentro de ese prefijo. Ej.: categoría 'Bebidas' -> 'BEB-0001'."""
    import re
    base = re.sub(r"[^A-Za-z0-9]", "", (categoria or ""))[:3].upper() or "PRD"
    pat = re.compile(r"^" + re.escape(base) + r"-(\d+)$")
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT codigo FROM productos WHERE codigo LIKE ?", (base + "-%",)
        ).fetchall()
    maxn = 0
    for r in rows:
        m = pat.match(r["codigo"] or "")
        if m:
            maxn = max(maxn, int(m.group(1)))
    return f"{base}-{maxn + 1:04d}"


def get_all_productos(solo_activos: bool = False, q: str = "",
                      solo_vendibles: bool = False) -> list[dict]:
    with get_connection() as conn:
        where = []
        params = []
        if solo_activos:
            where.append("activo=1")
        if solo_vendibles:
            where.append("vendible=1")
        if q:
            where.append("(nombre LIKE ? OR codigo LIKE ? OR categoria LIKE ?)")
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]
        sql = "SELECT * FROM productos"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY nombre"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_producto(pid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM productos WHERE id=?", (pid,)).fetchone()
        return dict(row) if row else None


def get_producto_by_codigo(codigo: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM productos WHERE codigo=? AND activo=1", (codigo,)
        ).fetchone()
        return dict(row) if row else None


def update_producto(pid: int, nombre: str, codigo: str, descripcion: str,
                    precio_venta: float, precio_costo: float,
                    unidad: str, categoria: str, activo: int,
                    stock_minimo: float = 0, estacion: str = "",
                    vendible: int = 1):
    with get_connection() as conn:
        conn.execute(
            """UPDATE productos SET nombre=?, codigo=?, descripcion=?,
               precio_venta=?, precio_costo=?, unidad=?, categoria=?,
               activo=?, stock_minimo=?, estacion=?, vendible=?
               WHERE id=?""",
            (nombre, codigo or None, descripcion, precio_venta, precio_costo,
             unidad, categoria, activo, stock_minimo, estacion or "", vendible, pid),
        )


def delete_producto(pid: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM productos WHERE id=?", (pid,))


# ── Recetas / fichas técnicas ─────────────────────────────────────────────────

def get_receta(producto_id: int) -> dict | None:
    """Receta de un producto con sus ítems (ingrediente + cantidad + costo unitario)."""
    with get_connection() as conn:
        receta = conn.execute(
            "SELECT * FROM recetas WHERE producto_id=?", (producto_id,)
        ).fetchone()
        if not receta:
            return None
        items = conn.execute(
            """SELECT ri.id, ri.ingrediente_id, ri.cantidad,
                      p.nombre AS ingrediente_nombre, p.unidad AS ingrediente_unidad,
                      p.precio_costo AS ingrediente_precio_costo
               FROM receta_items ri
               JOIN productos p ON p.id = ri.ingrediente_id
               WHERE ri.receta_id=?
               ORDER BY p.nombre""",
            (receta["id"],),
        ).fetchall()
    data = dict(receta)
    # clave "ingredientes" (no "items"): dict.items() es un método builtin y
    # Jinja resolvería receta.items a ese método en vez de esta clave.
    data["ingredientes"] = [dict(r) for r in items]
    return data


def guardar_receta(producto_id: int, items: list[dict], notas: str = "",
                   rinde: float = 1, rinde_unidad: str = "u",
                   rendimiento_pct: float = 100) -> int:
    """Crea o reemplaza la receta de un producto. `items` es una lista de
    {"ingrediente_id": int, "cantidad": float}. Reemplaza todos los ítems
    existentes (delete + insert) dentro de la misma transacción.

    `rinde`/`rinde_unidad`: cuánto produce un lote de esta receta (para
    elaborados que se producen antes de venderse, ej. una salsa). `rendimiento_pct`:
    merma de proceso (ej. pelar papas). Con los valores por defecto (1/u/100) la
    receta es "plana": 1 lote = 1 unidad del producto, sin ajuste de costeo."""
    rinde = rinde or 1
    rendimiento_pct = rendimiento_pct or 100
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM recetas WHERE producto_id=?", (producto_id,)
        ).fetchone()
        if row:
            receta_id = row["id"]
            conn.execute(
                """UPDATE recetas SET notas=?, rinde=?, rinde_unidad=?,
                   rendimiento_pct=?, updated_at=? WHERE id=?""",
                (notas, rinde, rinde_unidad, rendimiento_pct, _ar_now(), receta_id),
            )
            conn.execute("DELETE FROM receta_items WHERE receta_id=?", (receta_id,))
        else:
            cur = conn.execute(
                """INSERT INTO recetas (producto_id, notas, rinde, rinde_unidad, rendimiento_pct)
                   VALUES (?,?,?,?,?)""",
                (producto_id, notas, rinde, rinde_unidad, rendimiento_pct),
            )
            receta_id = cur.lastrowid
        for it in items:
            cantidad = float(it.get("cantidad") or 0)
            ingrediente_id = int(it["ingrediente_id"])
            if ingrediente_id == producto_id or cantidad <= 0:
                continue
            conn.execute(
                "INSERT INTO receta_items (receta_id, ingrediente_id, cantidad) VALUES (?,?,?)",
                (receta_id, ingrediente_id, cantidad),
            )
    # Sincroniza productos.precio_costo con el costo calculado de la receta, para
    # que si este producto se usa a su vez como ingrediente de otra receta (ej. un
    # combo que incluye una hamburguesa ya armada), tome un costo real y no 0.
    # No es recursivo: usa el precio_costo *guardado* de cada ingrediente, no vuelve
    # a recalcular la cadena completa.
    costo = costo_receta(producto_id)
    with get_connection() as conn:
        conn.execute("UPDATE productos SET precio_costo=? WHERE id=?", (costo, producto_id))
    return receta_id


def eliminar_receta(producto_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM recetas WHERE producto_id=?", (producto_id,))


def producir_receta(producto_id: int, cantidad_producida: float,
                    usuario_id: int | None = None, fecha: str = "") -> None:
    """Produce un lote de un elaborado: descuenta cada insumo de la receta
    (ajustado por rendimiento y proporcional a `cantidad_producida / rinde`) y
    suma esa cantidad al stock del producto elaborado. No es recursivo: si un
    insumo tiene a su vez receta propia, no se "produce" automáticamente."""
    if cantidad_producida <= 0:
        raise ValueError("La cantidad a producir debe ser mayor a 0.")
    receta = get_receta(producto_id)
    if not receta or not receta["ingredientes"]:
        raise ValueError("El producto no tiene una receta con ingredientes.")
    rinde = receta["rinde"] or 1
    rendimiento = receta["rendimiento_pct"] or 100
    factor = (cantidad_producida / rinde) / (rendimiento / 100)
    ref = f"Producción de {cantidad_producida:g} {receta['rinde_unidad']} (receta)"
    for ri in receta["ingredientes"]:
        add_movimiento_stock(
            producto_id=ri["ingrediente_id"], tipo="produccion",
            cantidad=-(ri["cantidad"] * factor),
            referencia=ref, usuario_id=usuario_id, fecha=fecha,
        )
    add_movimiento_stock(
        producto_id=producto_id, tipo="produccion",
        cantidad=cantidad_producida,
        referencia="Producción de lote (receta)",
        usuario_id=usuario_id, fecha=fecha,
    )


def costo_receta(producto_id: int) -> float:
    """Costo total de la receta de un producto (0 si no tiene receta o está vacía)."""
    receta = get_receta(producto_id)
    if not receta or not receta["ingredientes"]:
        return 0.0
    total = sum(
        it["cantidad"] * it["ingrediente_precio_costo"] for it in receta["ingredientes"]
    )
    rendimiento = receta["rendimiento_pct"] or 100
    rinde = receta["rinde"] or 1
    return (total / (rendimiento / 100)) / rinde


def food_cost_pct(producto_id: int, precio_venta: float, costo: float | None = None) -> float | None:
    """Food cost % = costo de la receta / precio de venta. None si no hay precio de venta."""
    if not precio_venta:
        return None
    if costo is None:
        costo = costo_receta(producto_id)
    return costo / precio_venta * 100


def get_reporte_food_cost() -> list[dict]:
    """Food cost / margen de todos los productos vendibles con receta."""
    productos = get_all_productos(solo_activos=True, solo_vendibles=True)
    reporte = []
    for p in productos:
        receta = get_receta(p["id"])
        if not receta or not receta["ingredientes"]:
            continue
        costo = costo_receta(p["id"])
        pv = float(p["precio_venta"] or 0)
        fc = food_cost_pct(p["id"], pv, costo)
        reporte.append({
            "id": p["id"], "nombre": p["nombre"], "categoria": p["categoria"],
            "precio_venta": pv, "costo": costo,
            "margen": pv - costo, "food_cost_pct": fc,
        })
    reporte.sort(key=lambda r: (r["food_cost_pct"] is None, -(r["food_cost_pct"] or 0)))
    return reporte


def get_consumo_insumos(desde: str = "", hasta: str = "") -> list[dict]:
    """Consumo real de insumos (ventas + mermas, en negativo) por producto en un
    rango de fechas, para comparar contra el consumo teórico de las recetas."""
    where = ["m.tipo IN ('venta','merma')"]
    params: list = []
    if desde:
        where.append("m.fecha >= ?"); params.append(desde)
    if hasta:
        where.append("m.fecha <= ?"); params.append(hasta)
    sql = f"""
        SELECT p.id, p.nombre, p.unidad,
               SUM(CASE WHEN m.tipo='venta' THEN -m.cantidad ELSE 0 END) AS consumido_venta,
               SUM(CASE WHEN m.tipo='merma' THEN -m.cantidad ELSE 0 END) AS consumido_merma
        FROM movimientos_stock m
        JOIN productos p ON p.id = m.producto_id
        WHERE {' AND '.join(where)}
        GROUP BY p.id
        ORDER BY (consumido_venta + consumido_merma) DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ── Turnos de caja ────────────────────────────────────────────────────────────

def create_turno(usuario_id: int, monto_inicial: float, notas: str = "") -> int:
    apertura = _ar_now()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO turnos_caja (usuario_id, apertura, monto_inicial, notas)
               VALUES (?,?,?,?)""",
            (usuario_id, apertura, monto_inicial, notas),
        )
        return cur.lastrowid


def get_turno_activo(usuario_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT t.*, u.nombre AS usuario_nombre
               FROM turnos_caja t JOIN usuarios u ON u.id = t.usuario_id
               WHERE t.usuario_id=? AND t.estado='abierto'
               ORDER BY t.id DESC LIMIT 1""",
            (usuario_id,),
        ).fetchone()
    return dict(row) if row else None


def get_turno_activo_any() -> dict | None:
    """Devuelve el primer turno abierto (para cajero sin usuario_id explícito)."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT t.*, u.nombre AS usuario_nombre
               FROM turnos_caja t JOIN usuarios u ON u.id = t.usuario_id
               WHERE t.estado='abierto' ORDER BY t.id DESC LIMIT 1"""
        ).fetchone()
    return dict(row) if row else None


def get_all_turnos(usuario_id: int | None = None, limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        if usuario_id:
            rows = conn.execute(
                """SELECT t.*, u.nombre AS usuario_nombre
                   FROM turnos_caja t JOIN usuarios u ON u.id = t.usuario_id
                   WHERE t.usuario_id=? ORDER BY t.id DESC LIMIT ?""",
                (usuario_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT t.*, u.nombre AS usuario_nombre
                   FROM turnos_caja t JOIN usuarios u ON u.id = t.usuario_id
                   ORDER BY t.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_turno(tid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT t.*, u.nombre AS usuario_nombre
               FROM turnos_caja t JOIN usuarios u ON u.id = t.usuario_id
               WHERE t.id=?""",
            (tid,),
        ).fetchone()
    return dict(row) if row else None


def get_resumen_turno(tid: int) -> dict:
    """Devuelve ventas y totales por medio de pago del turno."""
    with get_connection() as conn:
        ventas = conn.execute(
            """SELECT v.id, v.numero, v.fecha, v.cliente_nombre, v.total, v.estado
               FROM ventas v WHERE v.turno_id=? ORDER BY v.id""",
            (tid,),
        ).fetchall()
        pagos = conn.execute(
            """SELECT vp.medio, SUM(vp.monto) AS total
               FROM ventas_pagos vp
               JOIN ventas v ON v.id = vp.venta_id
               WHERE v.turno_id=? AND v.estado='cobrada'
               GROUP BY vp.medio""",
            (tid,),
        ).fetchall()
    return {
        "ventas": [dict(v) for v in ventas],
        "pagos_por_medio": {r["medio"]: r["total"] for r in pagos},
        "total_ventas": sum(r["total"] for r in pagos),
        "efectivo_ventas": next((r["total"] for r in pagos if r["medio"] == "efectivo"), 0.0),
    }


def cerrar_turno(tid: int, monto_declarado: float, notas: str = ""):
    turno = get_turno(tid)
    if not turno:
        return
    resumen = get_resumen_turno(tid)
    monto_esperado = round(turno["monto_inicial"] + resumen["efectivo_ventas"], 2)
    cierre = _ar_now()
    with get_connection() as conn:
        conn.execute(
            """UPDATE turnos_caja
               SET estado='cerrado', cierre=?, monto_declarado_cierre=?,
                   monto_esperado_cierre=?, notas=?
               WHERE id=?""",
            (cierre, monto_declarado, monto_esperado, notas, tid),
        )


def vincular_venta_turno(venta_id: int, turno_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE ventas SET turno_id=? WHERE id=?", (turno_id, venta_id))


# ── Stock ─────────────────────────────────────────────────────────────────────

def add_movimiento_stock(producto_id: int, tipo: str, cantidad: float,
                         referencia: str = "", fecha: str = "",
                         venta_id: int | None = None,
                         usuario_id: int | None = None,
                         deposito_id: int | None = None):
    """Agrega un movimiento de stock. cantidad positiva=entrada, negativa=salida."""
    from datetime import date as _date
    _fecha = fecha or _date.today().isoformat()
    _deposito = deposito_id or get_default_deposito_id()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO movimientos_stock
               (producto_id, tipo, cantidad, referencia, venta_id, usuario_id, fecha, deposito_id)
               VALUES (?,?,?,?,?,?,?,?)""",
            (producto_id, tipo, cantidad, referencia, venta_id, usuario_id, _fecha, _deposito),
        )


def get_stock_actual(producto_id: int) -> float:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(cantidad),0) FROM movimientos_stock WHERE producto_id=?",
            (producto_id,),
        ).fetchone()
    return float(row[0])


def get_stock_todos() -> list[dict]:
    """Devuelve todos los productos con su stock actual."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.id, p.codigo, p.nombre, p.unidad, p.categoria,
                   p.stock_minimo, p.activo,
                   COALESCE(SUM(m.cantidad), 0) AS stock_actual
            FROM productos p
            LEFT JOIN movimientos_stock m ON m.producto_id = p.id
            WHERE p.activo = 1
            GROUP BY p.id
            ORDER BY p.nombre
        """).fetchall()
    return [dict(r) for r in rows]


def get_movimientos_stock(producto_id: int | None = None,
                          desde: str = "", hasta: str = "",
                          limit: int = 200) -> list[dict]:
    with get_connection() as conn:
        where, params = [], []
        if producto_id:
            where.append("m.producto_id = ?"); params.append(producto_id)
        if desde:
            where.append("m.fecha >= ?"); params.append(desde)
        if hasta:
            where.append("m.fecha <= ?"); params.append(hasta)
        sql = """SELECT m.*, p.nombre AS producto_nombre, p.unidad
                 FROM movimientos_stock m
                 JOIN productos p ON p.id = m.producto_id"""
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY m.fecha DESC, m.id DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def ajustar_stock(producto_id: int, stock_nuevo: float, referencia: str,
                  usuario_id: int | None = None, fecha: str = ""):
    """Crea un movimiento de ajuste para llevar el stock al valor indicado."""
    actual = get_stock_actual(producto_id)
    delta  = round(stock_nuevo - actual, 4)
    if delta == 0:
        return
    add_movimiento_stock(
        producto_id=producto_id, tipo="ajuste",
        cantidad=delta, referencia=referencia,
        usuario_id=usuario_id, fecha=fecha,
    )


def descontar_stock_venta(venta_id: int, items: list, fecha: str = "",
                           usuario_id: int | None = None):
    """Descuenta stock por cada ítem de la venta que tenga producto_id.

    Si el producto tiene una receta activa, descuenta cada insumo de la
    receta (cantidad × cantidad vendida) en vez del propio producto — no es
    recursivo, los elaborados se stockean aparte por "producción" (Fase 2).
    Si no tiene receta, se mantiene el comportamiento anterior (descuenta el
    propio producto — sirve para reventa, ej. bebidas embotelladas).

    Si el ítem trae `modificadores` (JSON de `add_pedido_item`, Fase 3), se
    ajusta la cantidad de cada insumo: "quitar" -> no se descuenta, "doble"
    -> se descuenta el doble. Sin modificadores, receta normal.
    """
    for item in items:
        pid = item.get("producto_id")
        if not pid:
            continue
        qty = abs(float(item.get("qty", 0)))
        receta = get_receta(pid)
        if receta and receta["ingredientes"]:
            modos = _parse_modificadores(item.get("modificadores"))
            for ri in receta["ingredientes"]:
                modo = modos.get(ri["ingrediente_id"])
                if modo == "quitar":
                    continue
                multiplicador = 2 if modo == "doble" else 1
                add_movimiento_stock(
                    producto_id=ri["ingrediente_id"], tipo="venta",
                    cantidad=-(ri["cantidad"] * qty * multiplicador),
                    referencia=f"Venta ID {venta_id} (receta)",
                    venta_id=venta_id, usuario_id=usuario_id, fecha=fecha,
                )
        else:
            add_movimiento_stock(
                producto_id=pid, tipo="venta",
                cantidad=-qty,
                referencia=f"Venta ID {venta_id}",
                venta_id=venta_id, usuario_id=usuario_id, fecha=fecha,
            )


def _parse_modificadores(modificadores) -> dict:
    """Convierte el JSON de modificadores de un pedido_item en un dict
    {ingrediente_id: "quitar"|"doble"} para uso interno."""
    if not modificadores:
        return {}
    try:
        lista = json.loads(modificadores)
    except (ValueError, TypeError):
        return {}
    return {int(m["ingrediente_id"]): m.get("modo") for m in lista if m.get("ingrediente_id")}


def _resumen_modificadores(modificadores) -> str:
    """Texto corto para mostrar en el pedido/comanda, ej. 'Sin Cheddar, Doble Medallón'."""
    if not modificadores:
        return ""
    try:
        lista = json.loads(modificadores)
    except (ValueError, TypeError):
        return ""
    etiquetas = {"quitar": "Sin", "doble": "Doble"}
    partes = [f"{etiquetas.get(m.get('modo'), m.get('modo'))} {m.get('ingrediente_nombre', '')}".strip()
              for m in lista if m.get("ingrediente_nombre")]
    return ", ".join(partes)


# ── Ventas ────────────────────────────────────────────────────────────────────

def get_next_venta_numero() -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT numero FROM ventas ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row:
        try:
            n = int(row["numero"].split("-")[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    else:
        n = 1
    return f"V-{n:05d}"


def create_venta(numero: str, fecha: str, items: list, subtotal: float,
                 descuento: float, total: float, cliente_id: int | None,
                 cliente_nombre: str, usuario_id: int | None,
                 observaciones: str = "", estado: str = "cobrada") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO ventas
               (numero, fecha, items, subtotal, descuento, total,
                cliente_id, cliente_nombre, usuario_id, observaciones, estado)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, fecha, json.dumps(items, ensure_ascii=False),
             subtotal, descuento, total,
             cliente_id, cliente_nombre, usuario_id, observaciones, estado),
        )
        return cur.lastrowid


def add_venta_pago(venta_id: int, medio: str, monto: float, referencia: str = ""):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO ventas_pagos (venta_id, medio, monto, referencia) VALUES (?,?,?,?)",
            (venta_id, medio, monto, referencia),
        )


def get_all_ventas(desde: str = "", hasta: str = "", q: str = "",
                   tab: str = "todas", limit: int = 100, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        where, params = [], []
        if desde:
            where.append("v.fecha >= ?"); params.append(desde)
        if hasta:
            where.append("v.fecha <= ?"); params.append(hasta)
        if q:
            where.append("(v.numero LIKE ? OR v.cliente_nombre LIKE ?)")
            params += [f"%{q}%", f"%{q}%"]
        if tab == "sin_facturar":
            where.append("v.factura_id IS NULL AND v.estado != 'anulada'")
        elif tab == "facturadas":
            where.append("v.factura_id IS NOT NULL")
        sql = """SELECT v.*,
                        GROUP_CONCAT(p.medio || ':' || p.monto, '|') AS pagos_raw,
                        f.tipo    AS fac_tipo,
                        f.punto_venta AS fac_pv,
                        f.numero  AS fac_numero
                 FROM ventas v
                 LEFT JOIN ventas_pagos p ON p.venta_id = v.id
                 LEFT JOIN facturas f ON f.id = v.factura_id"""
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " GROUP BY v.id ORDER BY v.fecha DESC, v.id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["items"] = json.loads(d["items"])
        d["pagos"] = _parse_pagos_raw(d.pop("pagos_raw", "") or "")
        if d.get("fac_tipo") and d.get("fac_numero"):
            pv  = str(d.get("fac_pv") or 0).zfill(4)
            num = str(d["fac_numero"]).zfill(8)
            d["factura_display"] = f"{d['fac_tipo']} {pv}-{num}"
        else:
            d["factura_display"] = None
        result.append(d)
    return result


def get_venta(vid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM ventas WHERE id=?", (vid,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["items"] = json.loads(d["items"])
        pagos = conn.execute(
            "SELECT * FROM ventas_pagos WHERE venta_id=? ORDER BY id", (vid,)
        ).fetchall()
        d["pagos"] = [dict(p) for p in pagos]
    return d


def _parse_pagos_raw(raw: str) -> list[dict]:
    pagos = []
    for part in raw.split("|"):
        if ":" in part:
            medio, monto = part.split(":", 1)
            try:
                pagos.append({"medio": medio, "monto": float(monto)})
            except ValueError:
                pass
    return pagos


def anular_venta(vid: int):
    with get_connection() as conn:
        conn.execute("UPDATE ventas SET estado='anulada' WHERE id=?", (vid,))


def vincular_venta_factura(vid: int, factura_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE ventas SET factura_id=? WHERE id=?", (factura_id, vid))


def vincular_venta_remito(vid: int, remito_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE ventas SET remito_id=? WHERE id=?", (remito_id, vid))


# ── Log de actividad ──────────────────────────────────────────────────────────

_LOG_TIPOS = ("venta", "caja", "stock", "factura", "turno", "remito", "presupuesto")

def get_actividad_log(tipos=None, usuario_id=None, turno_id=None,
                      desde="", hasta="", limit=200, offset=0) -> list[dict]:
    """
    Devuelve una línea de tiempo unificada de todos los movimientos del sistema.
    Cada fila: {fecha, tipo, descripcion, monto, usuario, turno_id, ref_id, ref_tabla}
    """
    partes = []

    # — Ventas —
    partes.append("""
        SELECT
            v.created_at AS ts,
            v.fecha,
            'venta'       AS tipo,
            'Venta ' || v.numero ||
              CASE WHEN v.cliente_nombre != '' THEN ' — ' || v.cliente_nombre ELSE '' END
              || ' (' || v.estado || ')'  AS descripcion,
            v.total       AS monto,
            COALESCE(u.nombre, '')        AS usuario,
            v.turno_id,
            v.id          AS ref_id,
            'ventas'      AS ref_tabla
        FROM ventas v
        LEFT JOIN usuarios u ON u.id = v.usuario_id
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

    # — Stock —
    partes.append("""
        SELECT
            ms.created_at AS ts,
            ms.fecha,
            'stock'       AS tipo,
            ms.tipo || ' ' || p.nombre ||
              ' (' || CAST(ms.cantidad AS TEXT) || ' ' || p.unidad || ')'
              || CASE WHEN ms.referencia != '' THEN ' — ' || ms.referencia ELSE '' END
              AS descripcion,
            ABS(ms.cantidad) AS monto,
            COALESCE(u.nombre, '') AS usuario,
            NULL          AS turno_id,
            ms.id         AS ref_id,
            'movimientos_stock' AS ref_tabla
        FROM movimientos_stock ms
        JOIN productos p ON p.id = ms.producto_id
        LEFT JOIN usuarios u ON u.id = ms.usuario_id
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
            DATE(t.apertura) AS fecha,
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

    if usuario_id:
        # usuario solo está en ventas, stock, turnos; el resto da ''
        where.append("usuario_id_filter = ?")
        # se resuelve diferente — usamos subquery wrapper
    if desde:
        where.append("fecha >= ?"); params.append(desde)
    if hasta:
        where.append("fecha <= ?"); params.append(hasta)
    if turno_id:
        where.append("turno_id = ?"); params.append(turno_id)

    union_sql = "\nUNION ALL\n".join(partes)

    # Para filtrar por usuario necesitamos un wrapper con un JOIN auxiliar
    if usuario_id:
        # Re-construir solo las tablas que tienen usuario
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


# ── Log de autenticación ───────────────────────────────────────────────────────

def registrar_auth_event(evento: str, username: str, ip: str = "", detalle: str = ""):
    """Registra un evento de login, logout o intento fallido."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO auth_log (evento, username, ip, detalle) VALUES (?,?,?,?)",
            (evento, username, ip or "", detalle or ""),
        )
        conn.commit()


def get_auth_log(limit: int = 200, offset: int = 0) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM auth_log ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Módulos ────────────────────────────────────────────────────────────────────

def get_modulos() -> dict[str, bool]:
    """Devuelve {modulo: habilitado} para todos los módulos registrados."""
    with get_connection() as conn:
        rows = conn.execute("SELECT modulo, habilitado FROM modulos").fetchall()
    return {r["modulo"]: bool(r["habilitado"]) for r in rows}


def apply_plan(plan: str):
    """Habilita/deshabilita módulos según el plan elegido.

    El mapeo plan→módulos vive en plans.py (fuente de verdad compartida con el
    backoffice), para que lo que se habilita coincida con lo que se vende.
    """
    import plans
    activos = plans.modulos_de_plan(plan)
    with get_connection() as conn:
        rows = conn.execute("SELECT modulo FROM modulos").fetchall()
        for r in rows:
            conn.execute(
                "UPDATE modulos SET habilitado=?, plan=? WHERE modulo=?",
                (1 if r["modulo"] in activos else 0, plan, r["modulo"]),
            )


# ── Reportes ───────────────────────────────────────────────────────────────────

def get_reporte_ventas(desde: str = "", hasta: str = "", agrupacion: str = "dia") -> list[dict]:
    """Ventas agrupadas por día, semana o mes."""
    fmt = {"dia": "%Y-%m-%d", "semana": "%Y-W%W", "mes": "%Y-%m"}.get(agrupacion, "%Y-%m-%d")
    where, params = [], []
    if desde:
        where.append("fecha >= ?"); params.append(desde)
    if hasta:
        where.append("fecha <= ?"); params.append(hasta)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT strftime('{fmt}', fecha) AS periodo,
               COUNT(*) AS cantidad,
               ROUND(SUM(total), 2) AS total
        FROM ventas {w}
        GROUP BY periodo ORDER BY periodo
    """
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_reporte_medios_pago(desde: str = "", hasta: str = "") -> list[dict]:
    """Totales por medio de pago en el período."""
    where, params = [], []
    if desde:
        where.append("v.fecha >= ?"); params.append(desde)
    if hasta:
        where.append("v.fecha <= ?"); params.append(hasta)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT vp.medio, COUNT(DISTINCT vp.venta_id) AS operaciones,
               ROUND(SUM(vp.monto), 2) AS total
        FROM ventas_pagos vp
        JOIN ventas v ON v.id = vp.venta_id {w}
        GROUP BY vp.medio ORDER BY total DESC
    """
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_reporte_productos_top(desde: str = "", hasta: str = "", limit: int = 20) -> list[dict]:
    """Productos más vendidos (por cantidad y por monto) en el período."""
    where, params = [], []
    if desde:
        where.append("v.fecha >= ?"); params.append(desde)
    if hasta:
        where.append("v.fecha <= ?"); params.append(hasta)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT ji.value->>'$.nombre' AS nombre,
               ROUND(SUM(CAST(ji.value->>'$.qty' AS REAL)), 2) AS cantidad,
               ROUND(SUM(CAST(ji.value->>'$.qty' AS REAL) *
                         CAST(ji.value->>'$.precio' AS REAL)), 2) AS total
        FROM ventas v, json_each(v.items) ji {w}
        GROUP BY nombre ORDER BY cantidad DESC LIMIT ?
    """
    params.append(limit)
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_reporte_caja(desde: str = "", hasta: str = "") -> list[dict]:
    """Movimientos de caja por tipo en el período."""
    where, params = [], []
    if desde:
        where.append("fecha >= ?"); params.append(desde)
    if hasta:
        where.append("fecha <= ?"); params.append(hasta)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT tipo, COUNT(*) AS cantidad, ROUND(SUM(monto), 2) AS total
        FROM caja_movimientos {w}
        GROUP BY tipo ORDER BY total DESC
    """
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_reporte_caja_medios(desde: str = "", hasta: str = "", caja_id: int = 0) -> list[dict]:
    """Movimientos de caja agrupados por caja y medio de pago."""
    where, params = ["cm.fecha BETWEEN ? AND ?"], [desde or "1900-01-01", hasta or "2999-12-31"]
    if caja_id:
        where.append("cm.caja_id = ?"); params.append(caja_id)
    sql = f"""
        SELECT
            COALESCE(c.nombre, 'Sin caja')  AS caja_nombre,
            COALESCE(cm.caja_id, 0)         AS caja_id,
            LOWER(COALESCE(NULLIF(cm.medio_pago,''), 'sin_especificar')) AS medio,
            cm.tipo,
            COUNT(*)                         AS operaciones,
            ROUND(SUM(cm.monto), 2)          AS total
        FROM caja_movimientos cm
        LEFT JOIN cajas c ON c.id = cm.caja_id
        WHERE {" AND ".join(where)}
        GROUP BY cm.caja_id, c.nombre, LOWER(COALESCE(NULLIF(cm.medio_pago,''), 'sin_especificar')), cm.tipo
        ORDER BY caja_nombre, cm.tipo DESC, medio
    """
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_reporte_stock_bajo() -> list[dict]:
    """Productos con stock actual por debajo del mínimo."""
    sql = """
        SELECT p.id, p.nombre, p.codigo, p.stock_minimo,
               ROUND(COALESCE(SUM(ms.cantidad), 0), 3) AS stock_actual
        FROM productos p
        LEFT JOIN movimientos_stock ms ON ms.producto_id = p.id
        GROUP BY p.id
        HAVING stock_actual < p.stock_minimo
        ORDER BY (p.stock_minimo - stock_actual) DESC
    """
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def get_reporte_resumen(desde: str = "", hasta: str = "") -> dict:
    """KPIs rápidos para el período."""
    where, params = [], []
    if desde:
        where.append("fecha >= ?"); params.append(desde)
    if hasta:
        where.append("fecha <= ?"); params.append(hasta)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    with get_connection() as conn:
        v = conn.execute(
            f"SELECT COUNT(*) cnt, ROUND(SUM(total),2) total FROM ventas {w}", params
        ).fetchone()
        f_row = conn.execute(
            f"SELECT COUNT(*) cnt FROM facturas {w}", params
        ).fetchone()
        caja = conn.execute(
            f"SELECT ROUND(SUM(CASE WHEN tipo='ingreso' THEN monto ELSE -monto END),2) saldo FROM caja_movimientos {w}", params
        ).fetchone()
    return {
        "ventas_cantidad": v["cnt"] or 0,
        "ventas_total":    v["total"] or 0.0,
        "facturas_cantidad": f_row["cnt"] or 0,
        "caja_saldo":      caja["saldo"] or 0.0,
    }


def set_venta_mp_order(venta_id: int, mp_order_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE ventas SET mp_order_id=? WHERE id=?",
            (mp_order_id, venta_id),
        )
        conn.commit()


def set_venta_mp_payment(venta_id: int, mp_payment_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE ventas SET mp_payment_id=? WHERE id=?",
            (mp_payment_id, venta_id),
        )
        conn.commit()


def get_venta_by_mp_order(mp_order_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ventas WHERE mp_order_id=?", (mp_order_id,)
        ).fetchone()
        return dict(row) if row else None


def add_venta_pago_referencia_mp(venta_id: int, payment_id: str) -> None:
    """Actualiza la referencia del pago MP/billetera de la venta con el payment_id."""
    with get_connection() as conn:
        # Actualizar referencia en el pago existente de medio mercadopago/billetera/cuenta_dni
        conn.execute(
            """UPDATE ventas_pagos SET referencia=?
               WHERE venta_id=? AND medio IN ('mercadopago','billetera','cuenta_dni','qr')
               AND (referencia IS NULL OR referencia='')""",
            (f"MP#{payment_id}", venta_id),
        )
        conn.commit()


# ── Categorías de egreso ───────────────────────────────────────────────────────

def get_categorias_egreso() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM categorias_egreso ORDER BY nombre").fetchall()
    return [dict(r) for r in rows]


def create_categoria_egreso(nombre: str) -> int:
    with get_connection() as conn:
        cur = conn.execute("INSERT INTO categorias_egreso (nombre) VALUES (?)", (nombre.strip(),))
        return cur.lastrowid


def delete_categoria_egreso(cid: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM categorias_egreso WHERE id=?", (cid,))


# ── Proveedores ────────────────────────────────────────────────────────────────

def get_all_proveedores(limit: int = 500) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM proveedores ORDER BY nombre LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_proveedor(pid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM proveedores WHERE id=?", (pid,)).fetchone()
    return dict(row) if row else None


def search_proveedores(q: str) -> list[dict]:
    pat = f"%{q}%"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM proveedores WHERE nombre LIKE ? OR cuit_dni LIKE ? ORDER BY nombre LIMIT 50",
            (pat, pat),
        ).fetchall()
    return [dict(r) for r in rows]


def create_proveedor(nombre: str, cuit_dni: str = "", email: str = "",
                     phone: str = "", address: str = "", iva_condition: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO proveedores (nombre, cuit_dni, email, phone, address, iva_condition) VALUES (?,?,?,?,?,?)",
            (nombre, cuit_dni, email, phone, address, iva_condition),
        )
        return cur.lastrowid


def update_proveedor(pid: int, nombre: str, cuit_dni: str = "", email: str = "",
                     phone: str = "", address: str = "", iva_condition: str = ""):
    with get_connection() as conn:
        conn.execute(
            "UPDATE proveedores SET nombre=?, cuit_dni=?, email=?, phone=?, address=?, iva_condition=? WHERE id=?",
            (nombre, cuit_dni, email, phone, address, iva_condition, pid),
        )


def delete_proveedor(pid: int):
    with get_connection() as conn:
        tiene = conn.execute("SELECT COUNT(*) FROM egresos WHERE proveedor_id=?", (pid,)).fetchone()[0]
        if tiene:
            raise ValueError("No se puede eliminar un proveedor con egresos asociados.")
        conn.execute("DELETE FROM proveedores WHERE id=?", (pid,))


# ── Egresos ────────────────────────────────────────────────────────────────────

def create_egreso(fecha: str, concepto: str, total: float, proveedor_id=None,
                  proveedor_nombre: str = "", tipo_comprobante: str = "otro",
                  numero: str = "", categoria: str = "", monto_neto: float = 0,
                  iva_pct: float = 0, iva_monto: float = 0,
                  observaciones: str = "", usuario_id=None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO egresos
               (fecha, proveedor_id, proveedor_nombre, tipo_comprobante, numero,
                categoria, concepto, monto_neto, iva_pct, iva_monto, total,
                estado, observaciones, usuario_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'pendiente',?,?)""",
            (fecha, proveedor_id, proveedor_nombre, tipo_comprobante, numero,
             categoria, concepto, monto_neto, iva_pct, iva_monto, total,
             observaciones, usuario_id),
        )
        return cur.lastrowid


def get_egreso(eid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM egresos WHERE id=?", (eid,)).fetchone()
    return dict(row) if row else None


def get_all_egresos(desde: str = "", hasta: str = "", categoria: str = "",
                    estado: str = "", proveedor_id: int = 0, limit: int = 200) -> list[dict]:
    conds = []
    params: list = []
    if desde:
        conds.append("e.fecha >= ?"); params.append(desde)
    if hasta:
        conds.append("e.fecha <= ?"); params.append(hasta)
    if categoria:
        conds.append("e.categoria = ?"); params.append(categoria)
    if estado:
        conds.append("e.estado = ?"); params.append(estado)
    if proveedor_id:
        conds.append("e.proveedor_id = ?"); params.append(proveedor_id)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT e.*, p.nombre AS prov_nombre_lookup
                FROM egresos e
                LEFT JOIN proveedores p ON p.id = e.proveedor_id
                {where} ORDER BY e.fecha DESC, e.id DESC LIMIT ?""",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def get_resumen_egresos(desde: str = "", hasta: str = "") -> dict:
    conds = []
    params: list = []
    if desde:
        conds.append("fecha >= ?"); params.append(desde)
    if hasta:
        conds.append("fecha <= ?"); params.append(hasta)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_connection() as conn:
        row = conn.execute(
            f"""SELECT
                COALESCE(SUM(total), 0)                              AS total_periodo,
                COALESCE(SUM(CASE WHEN estado='pagado'   THEN total ELSE 0 END), 0) AS pagado,
                COALESCE(SUM(CASE WHEN estado!='pagado'  THEN total ELSE 0 END), 0) AS pendiente
                FROM egresos {where}""",
            params,
        ).fetchone()
    return dict(row)


def delete_egreso(eid: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM egresos WHERE id=?", (eid,))


# ── Pagos de egresos ───────────────────────────────────────────────────────────

def get_pagos_egreso(eid: int) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM egresos_pagos WHERE egreso_id=? ORDER BY id",
            (eid,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_pago_egreso(egreso_id: int, fecha: str, monto: float,
                       caja_id=None, medio_pago: str = "",
                       referencia: str = "", usuario_id=None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO egresos_pagos (egreso_id, fecha, monto, caja_id, medio_pago, referencia, usuario_id)
               VALUES (?,?,?,?,?,?,?)""",
            (egreso_id, fecha, monto, caja_id or get_default_caja_id(),
             medio_pago, referencia, usuario_id),
        )
        pago_id = cur.lastrowid

        # Recalcular estado del egreso
        total = conn.execute("SELECT total FROM egresos WHERE id=?", (egreso_id,)).fetchone()[0]
        pagado = conn.execute(
            "SELECT COALESCE(SUM(monto),0) FROM egresos_pagos WHERE egreso_id=?", (egreso_id,)
        ).fetchone()[0]

        if pagado >= total:
            nuevo_estado = "pagado"
        elif pagado > 0:
            nuevo_estado = "parcial"
        else:
            nuevo_estado = "pendiente"

        conn.execute("UPDATE egresos SET estado=? WHERE id=?", (nuevo_estado, egreso_id))
        return pago_id


# ── Tesorería ──────────────────────────────────────────────────────────────────

_TIPOS_CUENTA = {
    "efectivo": "Efectivo",
    "banco":    "Banco",
    "digital":  "Billetera digital",
    "otro":     "Otro",
}

def get_all_cuentas_tesoreria() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT c.*,
                c.saldo_inicial
                + COALESCE(SUM(CASE WHEN m.tipo IN ('ingreso','transferencia_entrada') THEN m.monto ELSE 0 END),0)
                - COALESCE(SUM(CASE WHEN m.tipo IN ('egreso', 'transferencia_salida')  THEN m.monto ELSE 0 END),0)
                AS saldo
            FROM cuentas_tesoreria c
            LEFT JOIN movimientos_tesoreria m ON m.cuenta_id = c.id
            WHERE c.activa = 1
            GROUP BY c.id
            ORDER BY c.orden, c.nombre
        """).fetchall()
    return [dict(r) for r in rows]


def get_cuenta_tesoreria(cid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT c.*,
                c.saldo_inicial
                + COALESCE(SUM(CASE WHEN m.tipo IN ('ingreso','transferencia_entrada') THEN m.monto ELSE 0 END),0)
                - COALESCE(SUM(CASE WHEN m.tipo IN ('egreso', 'transferencia_salida')  THEN m.monto ELSE 0 END),0)
                AS saldo
            FROM cuentas_tesoreria c
            LEFT JOIN movimientos_tesoreria m ON m.cuenta_id = c.id
            WHERE c.id = ?
            GROUP BY c.id
        """, (cid,)).fetchone()
    return dict(row) if row else None


def create_cuenta_tesoreria(nombre, tipo, banco="", numero="", descripcion="", saldo_inicial=0) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO cuentas_tesoreria (nombre, tipo, banco, numero, descripcion, saldo_inicial)
               VALUES (?,?,?,?,?,?)""",
            (nombre, tipo, banco, numero, descripcion, float(saldo_inicial)),
        )
        return cur.lastrowid


def update_cuenta_tesoreria(cid, nombre, tipo, banco="", numero="", descripcion="", saldo_inicial=0):
    with get_connection() as conn:
        conn.execute(
            """UPDATE cuentas_tesoreria
               SET nombre=?, tipo=?, banco=?, numero=?, descripcion=?, saldo_inicial=?
               WHERE id=?""",
            (nombre, tipo, banco, numero, descripcion, float(saldo_inicial), cid),
        )


def delete_cuenta_tesoreria(cid: int):
    with get_connection() as conn:
        conn.execute("UPDATE cuentas_tesoreria SET activa=0 WHERE id=?", (cid,))


def get_movimientos_tesoreria(cuenta_id: int | None = None, limit: int = 200,
                               desde: str = "", hasta: str = "") -> list[dict]:
    conds, params = [], []
    if cuenta_id:
        conds.append("(m.cuenta_id=? OR m.cuenta_destino_id=?)")
        params += [cuenta_id, cuenta_id]
    if desde:
        conds.append("m.fecha >= ?"); params.append(desde)
    if hasta:
        conds.append("m.fecha <= ?"); params.append(hasta + " 23:59:59")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    with get_connection() as conn:
        rows = conn.execute(f"""
            SELECT m.*,
                   co.nombre AS cuenta_nombre,
                   cd.nombre AS cuenta_destino_nombre,
                   u.nombre AS usuario_nombre
            FROM movimientos_tesoreria m
            JOIN cuentas_tesoreria co ON co.id = m.cuenta_id
            LEFT JOIN cuentas_tesoreria cd ON cd.id = m.cuenta_destino_id
            LEFT JOIN usuarios u ON u.id = m.usuario_id
            {where}
            ORDER BY m.fecha DESC, m.id DESC
            LIMIT ?
        """, params + [limit]).fetchall()
    return [dict(r) for r in rows]


def create_movimiento_tesoreria(fecha, cuenta_id, tipo, monto, concepto="",
                                 referencia="", cuenta_destino_id=None,
                                 transferencia_id=None, usuario_id=None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO movimientos_tesoreria
               (fecha, cuenta_id, tipo, monto, concepto, referencia,
                cuenta_destino_id, transferencia_id, usuario_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (fecha, cuenta_id, tipo, float(monto), concepto, referencia or "",
             cuenta_destino_id, transferencia_id, usuario_id),
        )
        return cur.lastrowid


def create_transferencia_tesoreria(fecha, cuenta_origen_id, cuenta_destino_id,
                                    monto, concepto="", referencia="", usuario_id=None):
    """Crea dos movimientos enlazados: salida del origen, entrada al destino."""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO movimientos_tesoreria
               (fecha, cuenta_id, tipo, monto, concepto, referencia,
                cuenta_destino_id, usuario_id)
               VALUES (?,?,'transferencia_salida',?,?,?,?,?)""",
            (fecha, cuenta_origen_id, float(monto), concepto, referencia or "",
             cuenta_destino_id, usuario_id),
        )
        salida_id = cur.lastrowid
        conn.execute(
            """INSERT INTO movimientos_tesoreria
               (fecha, cuenta_id, tipo, monto, concepto, referencia,
                cuenta_destino_id, transferencia_id, usuario_id)
               VALUES (?,?,'transferencia_entrada',?,?,?,?,?,?)""",
            (fecha, cuenta_destino_id, float(monto), concepto, referencia or "",
             cuenta_origen_id, salida_id, usuario_id),
        )
        conn.execute(
            "UPDATE movimientos_tesoreria SET transferencia_id=? WHERE id=?",
            (salida_id, salida_id),
        )


def delete_movimiento_tesoreria(mid: int):
    with get_connection() as conn:
        mov = conn.execute(
            "SELECT tipo, transferencia_id FROM movimientos_tesoreria WHERE id=?", (mid,)
        ).fetchone()
        if not mov:
            return
        # Si es parte de una transferencia, eliminar ambos lados
        if mov["transferencia_id"]:
            conn.execute(
                "DELETE FROM movimientos_tesoreria WHERE transferencia_id=?",
                (mov["transferencia_id"],),
            )
        else:
            conn.execute("DELETE FROM movimientos_tesoreria WHERE id=?", (mid,))


def get_resumen_tesoreria() -> dict:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(c.saldo_inicial
                    + COALESCE(ing.monto,0) - COALESCE(egr.monto,0)), 0) AS total
            FROM cuentas_tesoreria c
            LEFT JOIN (
                SELECT cuenta_id, SUM(monto) AS monto
                FROM movimientos_tesoreria
                WHERE tipo IN ('ingreso','transferencia_entrada')
                GROUP BY cuenta_id
            ) ing ON ing.cuenta_id = c.id
            LEFT JOIN (
                SELECT cuenta_id, SUM(monto) AS monto
                FROM movimientos_tesoreria
                WHERE tipo IN ('egreso','transferencia_salida')
                GROUP BY cuenta_id
            ) egr ON egr.cuenta_id = c.id
            WHERE c.activa = 1
        """).fetchone()
    return {"total": row["total"] if row else 0}


# ── Cuenta corriente por cliente ───────────────────────────────────────────────

def get_cc_saldo(cliente_id: int) -> float:
    with get_connection() as conn:
        _row = conn.execute("SELECT cuit_dni FROM clients WHERE id=?", (cliente_id,)).fetchone()
        cuit = (_row["cuit_dni"] if _row else "") or ""
        debitos_venta = conn.execute("""
            SELECT COALESCE(SUM(vp.monto), 0)
            FROM ventas_pagos vp
            JOIN ventas v ON vp.venta_id = v.id
            WHERE v.cliente_id = ? AND vp.medio = 'cuenta_corriente'
        """, (cliente_id,)).fetchone()[0]
        debitos_factura = 0.0
        if cuit:
            debitos_factura = conn.execute("""
                SELECT COALESCE(SUM(cm.monto), 0)
                FROM caja_movimientos cm
                JOIN facturas f ON cm.factura_id = f.id
                WHERE f.cliente_cuit = ? AND cm.tipo = 'ingreso'
                  AND LOWER(cm.medio_pago) IN ('cuenta corriente','cuenta_corriente')
            """, (cuit,)).fetchone()[0]
        abonos = conn.execute(
            "SELECT COALESCE(SUM(monto), 0) FROM cc_pagos WHERE cliente_id = ?",
            (cliente_id,),
        ).fetchone()[0]
    return float(debitos_venta) + float(debitos_factura) - float(abonos)


def get_cc_movimientos(cliente_id: int) -> list[dict]:
    with get_connection() as conn:
        _row = conn.execute("SELECT cuit_dni FROM clients WHERE id=?", (cliente_id,)).fetchone()
        cuit = (_row["cuit_dni"] if _row else "") or ""
        movs = []

        rows = conn.execute("""
            SELECT v.fecha, v.numero, vp.monto, v.id AS venta_id
            FROM ventas_pagos vp
            JOIN ventas v ON vp.venta_id = v.id
            WHERE v.cliente_id = ? AND vp.medio = 'cuenta_corriente'
        """, (cliente_id,)).fetchall()
        for r in rows:
            movs.append({
                "fecha": (r["fecha"] or "")[:10], "tipo": "debito",
                "concepto": f"Venta #{r['numero']}",
                "monto": r["monto"], "referencia": "", "medio": "",
                "venta_id": r["venta_id"], "factura_id": None, "cc_pago_id": None,
                "usuario_nombre": None,
            })

        if cuit:
            rows = conn.execute("""
                SELECT cm.fecha, f.tipo AS ftipo, f.punto_venta, f.numero,
                       cm.monto, f.id AS factura_id, cm.referencia, u.nombre AS usuario_nombre
                FROM caja_movimientos cm
                JOIN facturas f ON cm.factura_id = f.id
                LEFT JOIN usuarios u ON u.id = cm.usuario_id
                WHERE f.cliente_cuit = ? AND cm.tipo = 'ingreso'
                  AND LOWER(cm.medio_pago) IN ('cuenta corriente','cuenta_corriente')
            """, (cuit,)).fetchall()
            _TIPO_LABEL = {
                1:"FACTURA A", 6:"FACTURA B", 11:"FACTURA C",
                2:"ND A", 3:"NC A", 7:"ND B", 8:"NC B", 12:"ND C", 13:"NC C",
            }
            for r in rows:
                lbl = _TIPO_LABEL.get(r["ftipo"], "COMP")
                pv  = str(r["punto_venta"]).zfill(4)
                num = str(r["numero"]).zfill(8)
                movs.append({
                    "fecha": (r["fecha"] or "")[:10], "tipo": "debito",
                    "concepto": f"{lbl} {pv}-{num}",
                    "monto": r["monto"], "referencia": r["referencia"] or "",
                    "medio": "", "venta_id": None,
                    "factura_id": r["factura_id"], "cc_pago_id": None,
                    "usuario_nombre": r["usuario_nombre"],
                })

        rows = conn.execute("""
            SELECT cc_pagos.id, fecha, concepto, monto, referencia, medio_pago, u.nombre AS usuario_nombre
            FROM cc_pagos
            LEFT JOIN usuarios u ON u.id = cc_pagos.usuario_id
            WHERE cc_pagos.cliente_id = ? ORDER BY fecha, cc_pagos.id
        """, (cliente_id,)).fetchall()
        for r in rows:
            movs.append({
                "fecha": (r["fecha"] or "")[:10], "tipo": "credito",
                "concepto": r["concepto"] or "Pago a cuenta",
                "monto": r["monto"], "referencia": r["referencia"] or "",
                "medio": r["medio_pago"] or "",
                "venta_id": None, "factura_id": None, "cc_pago_id": r["id"],
                "usuario_nombre": r["usuario_nombre"],
            })

    return sorted(movs, key=lambda x: x["fecha"])


def get_clientes_con_saldo_cc() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            WITH dv AS (
                SELECT v.cliente_id AS cid, SUM(vp.monto) AS total
                FROM ventas_pagos vp JOIN ventas v ON vp.venta_id = v.id
                WHERE vp.medio = 'cuenta_corriente' AND v.cliente_id IS NOT NULL
                GROUP BY v.cliente_id
            ),
            df AS (
                SELECT c.id AS cid, SUM(cm.monto) AS total
                FROM caja_movimientos cm
                JOIN facturas f ON cm.factura_id = f.id
                JOIN clients c ON c.cuit_dni = f.cliente_cuit
                WHERE cm.tipo = 'ingreso'
                  AND LOWER(cm.medio_pago) IN ('cuenta corriente','cuenta_corriente')
                GROUP BY c.id
            ),
            cr AS (
                SELECT cliente_id AS cid, SUM(monto) AS total
                FROM cc_pagos GROUP BY cliente_id
            )
            SELECT c.id, c.name, c.cuit_dni,
                   COALESCE(dv.total,0) + COALESCE(df.total,0) - COALESCE(cr.total,0) AS saldo
            FROM clients c
            LEFT JOIN dv ON dv.cid = c.id
            LEFT JOIN df ON df.cid = c.id
            LEFT JOIN cr ON cr.cid = c.id
            WHERE dv.cid IS NOT NULL OR df.cid IS NOT NULL OR cr.cid IS NOT NULL
            ORDER BY saldo DESC, c.name
        """).fetchall()
    return [dict(r) for r in rows]


def create_cc_pago(cliente_id: int, monto: float, fecha: str, concepto: str,
                   referencia: str, medio_pago: str, caja_id, usuario_id) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO cc_pagos
               (cliente_id, monto, fecha, concepto, referencia, medio_pago, caja_id, usuario_id)
               VALUES (?,?,?,?,?,?,?,?)""",
            (cliente_id, float(monto), fecha, concepto, referencia, medio_pago, caja_id, usuario_id),
        )
        return cur.lastrowid


def delete_cc_pago(pago_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM cc_pagos WHERE id=?", (pago_id,))


# ── Listas de precios ──────────────────────────────────────────────────────────

def get_all_listas_precio(solo_activas: bool = False) -> list[dict]:
    with get_connection() as conn:
        where = "WHERE activa=1" if solo_activas else ""
        rows = conn.execute(
            f"SELECT * FROM listas_precio {where} ORDER BY es_default DESC, nombre"
        ).fetchall()
    return [dict(r) for r in rows]


def get_lista_precio(lista_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM listas_precio WHERE id=?", (lista_id,)).fetchone()
    return dict(row) if row else None


def create_lista_precio(nombre: str, descripcion: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO listas_precio (nombre, descripcion) VALUES (?,?)",
            (nombre, descripcion),
        )
        return cur.lastrowid


def update_lista_precio(lista_id: int, nombre: str, descripcion: str, activa: int):
    with get_connection() as conn:
        conn.execute(
            "UPDATE listas_precio SET nombre=?, descripcion=?, activa=? WHERE id=?",
            (nombre, descripcion, activa, lista_id),
        )


def delete_lista_precio(lista_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM listas_precio WHERE id=?", (lista_id,))


def get_lista_precio_items(lista_id: int, categoria: str = "") -> list[dict]:
    """Devuelve todos los productos activos con su precio en la lista dada."""
    with get_connection() as conn:
        where = "AND p.categoria=?" if categoria else ""
        params = [lista_id]
        if categoria:
            params.append(categoria)
        rows = conn.execute(f"""
            SELECT p.id, p.codigo, p.nombre, p.unidad, p.categoria,
                   p.precio_venta, p.precio_costo,
                   COALESCE(lpi.precio, 0) AS precio_lista,
                   CASE WHEN lpi.producto_id IS NOT NULL THEN 1 ELSE 0 END AS en_lista
            FROM productos p
            LEFT JOIN lista_precio_items lpi
                   ON lpi.lista_id=? AND lpi.producto_id=p.id
            WHERE p.activo=1 {where}
            ORDER BY p.categoria, p.nombre
        """, params).fetchall()
    return [dict(r) for r in rows]


def get_precio_en_lista(lista_id: int, producto_id: int) -> float | None:
    """Devuelve el precio del producto en la lista, o None si no está definido."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT precio FROM lista_precio_items WHERE lista_id=? AND producto_id=?",
            (lista_id, producto_id),
        ).fetchone()
    return float(row["precio"]) if row else None


def get_precios_lista_dict(lista_id: int) -> dict[int, float]:
    """Devuelve {producto_id: precio} para toda la lista (para el endpoint JSON)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT producto_id, precio FROM lista_precio_items WHERE lista_id=?",
            (lista_id,),
        ).fetchall()
    return {r["producto_id"]: r["precio"] for r in rows}


def save_lista_precio_items(lista_id: int, precios: dict):
    """Guarda o actualiza los precios de los productos en la lista.
    precios: {producto_id: precio}. Precio 0 elimina el ítem de la lista.
    """
    with get_connection() as conn:
        for pid_s, precio_s in precios.items():
            pid   = int(pid_s)
            precio = float(precio_s)
            if precio <= 0:
                conn.execute(
                    "DELETE FROM lista_precio_items WHERE lista_id=? AND producto_id=?",
                    (lista_id, pid),
                )
            else:
                conn.execute(
                    """INSERT INTO lista_precio_items (lista_id, producto_id, precio)
                       VALUES (?,?,?)
                       ON CONFLICT(lista_id, producto_id) DO UPDATE SET precio=excluded.precio""",
                    (lista_id, pid, precio),
                )


def apply_porcentaje_lista(lista_id: int, porcentaje: float,
                            base: str = "lista", categoria: str = "") -> int:
    """Aplica un ajuste porcentual a los precios de la lista.

    base: 'lista' (sobre precio actual), 'venta' (sobre precio_venta), 'costo' (sobre precio_costo).
    Devuelve la cantidad de productos actualizados.
    """
    factor = 1 + porcentaje / 100
    with get_connection() as conn:
        cat_where = "AND p.categoria=?" if categoria else ""
        cat_param = [categoria] if categoria else []

        if base == "lista":
            # Actualiza solo los que ya tienen precio en la lista
            rows = conn.execute(f"""
                SELECT lpi.producto_id, lpi.precio
                FROM lista_precio_items lpi
                JOIN productos p ON p.id = lpi.producto_id
                WHERE lpi.lista_id=? AND p.activo=1 {cat_where}
            """, [lista_id] + cat_param).fetchall()
            for r in rows:
                nuevo = round(r["precio"] * factor, 2)
                conn.execute(
                    "UPDATE lista_precio_items SET precio=? WHERE lista_id=? AND producto_id=?",
                    (nuevo, lista_id, r["producto_id"]),
                )
            return len(rows)
        else:
            col = "precio_venta" if base == "venta" else "precio_costo"
            rows = conn.execute(f"""
                SELECT id, {col} AS base_precio
                FROM productos WHERE activo=1 {cat_where}
            """, cat_param).fetchall()
            for r in rows:
                nuevo = round(r["base_precio"] * factor, 2)
                conn.execute(
                    """INSERT INTO lista_precio_items (lista_id, producto_id, precio)
                       VALUES (?,?,?)
                       ON CONFLICT(lista_id, producto_id) DO UPDATE SET precio=excluded.precio""",
                    (lista_id, r["id"], nuevo),
                )
            return len(rows)


def importar_precios_lista(lista_id: int, fuente: str, fuente_lista_id: int | None = None):
    """Importa precios a la lista desde otra fuente.

    fuente: 'venta', 'costo', 'lista' (requiere fuente_lista_id).
    """
    with get_connection() as conn:
        if fuente == "lista" and fuente_lista_id:
            rows = conn.execute(
                "SELECT producto_id, precio FROM lista_precio_items WHERE lista_id=?",
                (fuente_lista_id,),
            ).fetchall()
            for r in rows:
                conn.execute(
                    """INSERT INTO lista_precio_items (lista_id, producto_id, precio)
                       VALUES (?,?,?)
                       ON CONFLICT(lista_id, producto_id) DO UPDATE SET precio=excluded.precio""",
                    (lista_id, r["producto_id"], r["precio"]),
                )
        else:
            col = "precio_venta" if fuente == "venta" else "precio_costo"
            rows = conn.execute(
                f"SELECT id, {col} AS precio FROM productos WHERE activo=1"
            ).fetchall()
            for r in rows:
                conn.execute(
                    """INSERT INTO lista_precio_items (lista_id, producto_id, precio)
                       VALUES (?,?,?)
                       ON CONFLICT(lista_id, producto_id) DO UPDATE SET precio=excluded.precio""",
                    (lista_id, r["id"], r["precio"]),
                )


# ── Libros IVA ────────────────────────────────────────────────────────────────

def get_facturas_para_iva(desde: str, hasta: str) -> list[dict]:
    """Todas las facturas del período para Libro IVA Ventas."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM facturas
               WHERE fecha >= ? AND fecha <= ?
               ORDER BY fecha, punto_venta, numero""",
            (desde, hasta),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["items"] = json.loads(d.get("items") or "[]")
            result.append(d)
        return result


def get_egresos_para_iva(desde: str, hasta: str) -> list[dict]:
    """Egresos tipo factura del período para Libro IVA Compras, con CUIT proveedor."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT e.*, p.cuit_dni AS proveedor_cuit, p.iva_condition AS proveedor_iva_cond
               FROM egresos e
               LEFT JOIN proveedores p ON e.proveedor_id = p.id
               WHERE e.fecha >= ? AND e.fecha <= ?
               AND e.tipo_comprobante = 'factura'
               ORDER BY e.fecha, e.id""",
            (desde, hasta),
        ).fetchall()
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# Módulo Restaurant — salones, mesas, pedidos, comandas
# ═══════════════════════════════════════════════════════════════════════════════

ESTACIONES = ["cocina", "barra"]
COMANDA_ESTADOS = ["pendiente", "preparacion", "listo", "entregado"]
_COMANDA_NEXT = {"pendiente": "preparacion", "preparacion": "listo", "listo": "entregado"}


# ── Salones ─────────────────────────────────────────────────────────────────

def get_salones(solo_activos: bool = True) -> list[dict]:
    with get_connection() as conn:
        sql = "SELECT * FROM salones"
        if solo_activos:
            sql += " WHERE activo=1"
        sql += " ORDER BY orden, id"
        return [dict(r) for r in conn.execute(sql).fetchall()]


def get_salon(sid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM salones WHERE id=?", (sid,)).fetchone()
        return dict(row) if row else None


def create_salon(nombre: str, orden: int = 0) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO salones (nombre, orden) VALUES (?,?)", (nombre.strip(), orden)
        )
        return cur.lastrowid


def update_salon(sid: int, nombre: str, orden: int = 0, activo: int = 1):
    with get_connection() as conn:
        conn.execute(
            "UPDATE salones SET nombre=?, orden=?, activo=? WHERE id=?",
            (nombre.strip(), orden, 1 if activo else 0, sid),
        )


# ── Mesas ───────────────────────────────────────────────────────────────────

def get_mesas(salon_id: int | None = None, solo_activas: bool = True) -> list[dict]:
    """Mesas con el id y total del pedido abierto (si lo hay)."""
    with get_connection() as conn:
        sql = """
            SELECT m.*, s.nombre AS salon_nombre,
                   p.id AS pedido_id, p.numero AS pedido_numero, p.created_at AS pedido_creado_at
            FROM mesas m
            JOIN salones s ON s.id = m.salon_id
            LEFT JOIN pedidos p ON p.mesa_id = m.id AND p.estado = 'abierto'
        """
        where, params = [], []
        if salon_id:
            where.append("m.salon_id=?"); params.append(salon_id)
        if solo_activas:
            where.append("m.activo=1")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY s.orden, m.orden, m.id"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for r in rows:
        r["pedido_total"] = pedido_total(r["pedido_id"]) if r.get("pedido_id") else 0.0
        r["mins_ocupada"] = minutos_desde(r["pedido_creado_at"]) if r.get("pedido_creado_at") else 0
    return rows


def get_mesa(mid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT m.*, s.nombre AS salon_nombre
               FROM mesas m JOIN salones s ON s.id=m.salon_id WHERE m.id=?""",
            (mid,),
        ).fetchone()
        return dict(row) if row else None


def create_mesa(salon_id: int, nombre: str, capacidad: int = 4, orden: int = 0) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO mesas (salon_id, nombre, capacidad, orden) VALUES (?,?,?,?)",
            (salon_id, nombre.strip(), capacidad, orden),
        )
        return cur.lastrowid


def update_mesa(mid: int, nombre: str, capacidad: int = 4, orden: int = 0, activo: int = 1):
    with get_connection() as conn:
        conn.execute(
            "UPDATE mesas SET nombre=?, capacidad=?, orden=?, activo=? WHERE id=?",
            (nombre.strip(), capacidad, orden, 1 if activo else 0, mid),
        )


def set_mesa_estado(mid: int, estado: str):
    with get_connection() as conn:
        conn.execute("UPDATE mesas SET estado=? WHERE id=?", (estado, mid))


def delete_mesa(mid: int) -> bool:
    """Elimina una mesa. Bloquea si tiene un pedido abierto (no dejar pedidos huérfanos)."""
    with get_connection() as conn:
        c = conn.execute(
            "SELECT COUNT(*) AS c FROM pedidos WHERE mesa_id=? AND estado='abierto'", (mid,)
        ).fetchone()["c"]
        if c:
            return False
        conn.execute("DELETE FROM mesas WHERE id=?", (mid,))
    return True


def resumen_salon_ahora() -> dict:
    """Foto en vivo del salón: cantidad de mesas activas por estado."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN estado='libre'   THEN 1 ELSE 0 END) AS libres,
                 SUM(CASE WHEN estado='ocupada' THEN 1 ELSE 0 END) AS ocupadas,
                 SUM(CASE WHEN estado='cuenta'  THEN 1 ELSE 0 END) AS cuenta
               FROM mesas WHERE activo=1"""
        ).fetchone()
    return {
        "total": row["total"] or 0,
        "libres": row["libres"] or 0,
        "ocupadas": row["ocupadas"] or 0,
        "cuenta": row["cuenta"] or 0,
    }


def delete_salon(sid: int) -> bool:
    """Elimina un salón y sus mesas (cascade). Bloquea si alguna mesa tiene pedido abierto."""
    with get_connection() as conn:
        c = conn.execute(
            """SELECT COUNT(*) AS c FROM pedidos p JOIN mesas m ON m.id = p.mesa_id
               WHERE m.salon_id=? AND p.estado='abierto'""", (sid,)
        ).fetchone()["c"]
        if c:
            return False
        conn.execute("DELETE FROM salones WHERE id=?", (sid,))
    return True


# ── Reservas ────────────────────────────────────────────────────────────────

def get_reservas(fecha: str, estado: str | None = None) -> list[dict]:
    """Reservas de una fecha (todas o filtradas por estado), con datos de mesa/salón."""
    with get_connection() as conn:
        sql = """SELECT r.*, m.nombre AS mesa_nombre, s.nombre AS salon_nombre
                 FROM reservas r
                 JOIN mesas m ON m.id = r.mesa_id
                 JOIN salones s ON s.id = m.salon_id
                 WHERE r.fecha = ?"""
        params: list = [fecha]
        if estado:
            sql += " AND r.estado = ?"
            params.append(estado)
        sql += " ORDER BY r.hora, s.orden, m.orden"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def get_reserva(rid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT r.*, m.nombre AS mesa_nombre, m.salon_id AS salon_id, s.nombre AS salon_nombre
               FROM reservas r JOIN mesas m ON m.id=r.mesa_id JOIN salones s ON s.id=m.salon_id
               WHERE r.id=?""",
            (rid,),
        ).fetchone()
        return dict(row) if row else None


def get_proximas_reservas_por_mesa(fecha: str) -> dict[int, dict]:
    """Próxima reserva pendiente de cada mesa para la fecha dada (mesa_id -> reserva)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reservas WHERE fecha=? AND estado='pendiente' ORDER BY hora",
            (fecha,),
        ).fetchall()
    out: dict[int, dict] = {}
    for r in rows:
        d = dict(r)
        out.setdefault(d["mesa_id"], d)
    return out


def crear_reserva(mesa_id: int, fecha: str, hora: str, cliente_nombre: str,
                   comensales: int = 1, telefono: str = "", notas: str = "") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO reservas (mesa_id, fecha, hora, cliente_nombre, telefono, comensales, notas)
               VALUES (?,?,?,?,?,?,?)""",
            (mesa_id, fecha, hora, cliente_nombre.strip(), telefono.strip(),
             max(1, int(comensales or 1)), notas.strip()),
        )
        return cur.lastrowid


def cancelar_reserva(rid: int):
    with get_connection() as conn:
        conn.execute("UPDATE reservas SET estado='cancelada' WHERE id=? AND estado='pendiente'", (rid,))


def cumplir_reserva(rid: int):
    with get_connection() as conn:
        conn.execute("UPDATE reservas SET estado='cumplida' WHERE id=? AND estado='pendiente'", (rid,))


# ── Pedidos ─────────────────────────────────────────────────────────────────

def get_next_pedido_numero() -> str:
    with get_connection() as conn:
        row = conn.execute("SELECT numero FROM pedidos ORDER BY id DESC LIMIT 1").fetchone()
    n = 1
    if row:
        try:
            n = int(str(row["numero"]).split("-")[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    return f"P-{n:05d}"


def crear_pedido(canal: str = "salon", mesa_id: int | None = None, comensales: int = 1,
                 usuario_id: int | None = None, cliente_id: int | None = None,
                 cliente_nombre: str = "", observaciones: str = "",
                 telefono: str = "", direccion: str = "", repartidor: str = "",
                 costo_envio: float = 0.0, hora_retiro: str = "") -> int:
    numero = get_next_pedido_numero()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO pedidos
               (numero, canal, mesa_id, comensales, usuario_id, cliente_id,
                cliente_nombre, observaciones, telefono, direccion, repartidor,
                costo_envio, hora_retiro, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (numero, canal, mesa_id, comensales, usuario_id, cliente_id,
             cliente_nombre, observaciones, telefono, direccion, repartidor,
             float(costo_envio or 0), hora_retiro, _ar_now(), _ar_now()),
        )
        pid = cur.lastrowid
        if mesa_id:
            conn.execute("UPDATE mesas SET estado='ocupada' WHERE id=?", (mesa_id,))
    return pid


def get_pedidos_activos(canales: list[str] | None = None) -> list[dict]:
    """Pedidos abiertos (opcionalmente filtrados por canal), con su total.
    Usado por el board de mostrador/delivery (canales sin mesa)."""
    with get_connection() as conn:
        sql = """SELECT p.*, m.nombre AS mesa_nombre, u.username AS mozo
                 FROM pedidos p
                 LEFT JOIN mesas m ON m.id = p.mesa_id
                 LEFT JOIN usuarios u ON u.id = p.usuario_id
                 WHERE p.estado = 'abierto'"""
        params: list = []
        if canales:
            ph = ",".join("?" for _ in canales)
            sql += f" AND p.canal IN ({ph})"
            params += list(canales)
        sql += " ORDER BY p.created_at DESC"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    for r in rows:
        r["total"] = pedido_total(r["id"])
        r["n_items"] = len([1 for _ in get_pedido_items(r["id"])])
    return rows


def get_pedido_items(pedido_id: int) -> list[dict]:
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM pedido_items WHERE pedido_id=? AND estado!='anulado' ORDER BY id",
            (pedido_id,),
        ).fetchall()]


def pedido_total(pedido_id: int) -> float:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(subtotal),0) AS t FROM pedido_items "
            "WHERE pedido_id=? AND estado!='anulado'", (pedido_id,)
        ).fetchone()
        row2 = conn.execute(
            "SELECT costo_envio FROM pedidos WHERE id=?", (pedido_id,)
        ).fetchone()
    envio = float(row2["costo_envio"]) if row2 else 0.0
    return round(float(row["t"]) + envio, 2)


def get_pedido(pid: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT p.*, m.nombre AS mesa_nombre, m.salon_id AS salon_id,
                      s.nombre AS salon_nombre, u.username AS mozo
               FROM pedidos p
               LEFT JOIN mesas m ON m.id = p.mesa_id
               LEFT JOIN salones s ON s.id = m.salon_id
               LEFT JOIN usuarios u ON u.id = p.usuario_id
               WHERE p.id=?""",
            (pid,),
        ).fetchone()
        if not row:
            return None
        pedido = dict(row)
        pedido["items"] = [dict(r) for r in conn.execute(
            "SELECT * FROM pedido_items WHERE pedido_id=? AND estado!='anulado' ORDER BY id",
            (pid,),
        ).fetchall()]
        for it in pedido["items"]:
            it["modificadores_resumen"] = _resumen_modificadores(it.get("modificadores"))
        pedido["comandas"] = [dict(r) for r in conn.execute(
            "SELECT * FROM comandas WHERE pedido_id=? ORDER BY id", (pid,)
        ).fetchall()]
    pedido["total"] = pedido_total(pid)
    return pedido


def get_pedido_abierto_de_mesa(mesa_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM pedidos WHERE mesa_id=? AND estado='abierto' ORDER BY id DESC LIMIT 1",
            (mesa_id,),
        ).fetchone()
    return get_pedido(row["id"]) if row else None


def add_pedido_item(pedido_id: int, nombre: str, qty: float, precio: float,
                    producto_id: int | None = None, estacion: str = "",
                    nota: str = "", modificadores: str = "") -> int:
    """`modificadores` es un JSON (string) con la lista de ajustes a la receta
    del producto para este ítem puntual, ej.: [{"ingrediente_id":5,
    "ingrediente_nombre":"Cheddar","modo":"quitar"}]. `modo` es "quitar" (no
    descuenta ese insumo) o "doble" (descuenta el doble). Vacío = receta normal."""
    subtotal = round(qty * precio, 2)
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO pedido_items
               (pedido_id, producto_id, nombre, qty, precio, subtotal, estacion, nota, modificadores)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (pedido_id, producto_id, nombre.strip(), qty, precio, subtotal,
             estacion or "", nota.strip(), modificadores or ""),
        )
        conn.execute("UPDATE pedidos SET updated_at=? WHERE id=?", (_ar_now(), pedido_id))
        return cur.lastrowid


def delete_pedido_item(item_id: int) -> bool:
    """Sólo se puede quitar un ítem que todavía no fue enviado a una estación."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT estado FROM pedido_items WHERE id=?", (item_id,)
        ).fetchone()
        if not row or row["estado"] != "nuevo":
            return False
        conn.execute("DELETE FROM pedido_items WHERE id=?", (item_id,))
        return True


def set_pedido_item_nota(item_id: int, nota: str) -> bool:
    """Observación del ítem (ej.: 'sin aderezo', 'agregar queso'). Llega a la comanda/KDS.
    Editable mientras el ítem no esté anulado (el KDS lee la nota en vivo por polling)."""
    with get_connection() as conn:
        row = conn.execute("SELECT estado FROM pedido_items WHERE id=?", (item_id,)).fetchone()
        if not row or row["estado"] == "anulado":
            return False
        conn.execute("UPDATE pedido_items SET nota=? WHERE id=?", ((nota or "").strip(), item_id))
    return True


# ── Comandas ────────────────────────────────────────────────────────────────

def enviar_a_estaciones(pedido_id: int) -> list[int]:
    """Toma los ítems 'nuevo' del pedido, crea una comanda por estación (cocina/barra)
    con los ítems de esa estación, y marca todos los ítems como 'enviado'. Devuelve los
    ids de comanda creados (para imprimir). Ítems sin estación se marcan enviado sin comanda."""
    with get_connection() as conn:
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM pedido_items WHERE pedido_id=? AND estado='nuevo'", (pedido_id,)
        ).fetchall()]
        if not items:
            return []
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
            cur = conn.execute(
                "INSERT INTO comandas (pedido_id, estacion, numero, estado, created_at, updated_at) "
                "VALUES (?,?,?,'pendiente',?,?)",
                (pedido_id, estacion, ronda, _now, _now),
            )
            cid = cur.lastrowid
            for it in grupo:
                conn.execute(
                    "UPDATE pedido_items SET comanda_id=?, estado='enviado' WHERE id=?",
                    (cid, it["id"]),
                )
            creadas.append(cid)
        conn.execute(
            "UPDATE pedido_items SET estado='enviado' WHERE pedido_id=? AND estado='nuevo' "
            "AND (estacion IS NULL OR estacion='')", (pedido_id,)
        )
        conn.execute("UPDATE pedidos SET updated_at=? WHERE id=?", (_ar_now(), pedido_id))
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
    descontando stock y vinculando al turno. Devuelve el venta_id."""
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

    numero = get_next_venta_numero()
    venta_id = create_venta(
        numero=numero, fecha=fecha, items=items,
        subtotal=subtotal, descuento=descuento, total=total,
        cliente_id=cliente_id, cliente_nombre=cliente_nombre,
        usuario_id=usuario_id, observaciones=obs, estado=estado,
    )
    for p in pagos:
        add_venta_pago(venta_id, p["medio"], float(p["monto"]), p.get("referencia", ""))
        create_caja_movimiento(
            fecha=fecha, tipo="ingreso",
            concepto=f"Venta {numero} (pedido {pedido['numero']}) — {p['medio']}",
            monto=float(p["monto"]), referencia=p.get("referencia", ""),
            medio_pago=p["medio"],
        )

    try:
        if get_modulos().get("stock"):
            descontar_stock_venta(venta_id, items, fecha=fecha, usuario_id=usuario_id)
    except Exception:
        pass

    if usuario_id:
        turno = get_turno_activo(usuario_id)
        if turno:
            vincular_venta_turno(venta_id, turno["id"])

    with get_connection() as conn:
        conn.execute(
            "UPDATE pedidos SET estado='cobrado', venta_id=?, updated_at=? WHERE id=?",
            (venta_id, _ar_now(), pedido_id),
        )
        if pedido.get("mesa_id"):
            conn.execute("UPDATE mesas SET estado='libre' WHERE id=?", (pedido["mesa_id"],))
    return venta_id


# ── Reportes gastronómicos + tiempos ─────────────────────────────────────────

def minutos_desde(ts: str) -> int:
    """Minutos transcurridos (en hora AR) desde un timestamp 'YYYY-MM-DD HH:MM:SS'."""
    if not ts:
        return 0
    try:
        t = _datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
        now = _datetime.strptime(_ar_now(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return 0
    return max(0, int((now - t).total_seconds() // 60))


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
