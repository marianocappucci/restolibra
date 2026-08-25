"""El schema **propio** de Restolibra: lo que no es de ningún motor.

De las 67 tablas de una instancia, **9 son de este producto**: `venta_links`,
`recetas`, `receta_items`, `salones`, `mesas`, `pedidos`, `comandas`,
`pedido_items` y `reservas`. Las otras 58 las declaran los motores, y cada uno
las mantiene por su cuenta:

| Quién | Tablas | Cómo evoluciona su schema |
|---|---|---|
| `libracore` | 33 | cadena de Alembic (`alembic_version`), vía `libracore-migrar` |
| `libracommerce` | 19 + `schema_migrations` | runner numerado propio, dentro de `init_schema()` |
| `libraauth` | 6 (`usuarios`, `auth_log`, `demo_codigos`, `password_reset_tokens`, `smtp_settings`, `aceptaciones_terminos`) | `Base.metadata.create_all()` al arrancar |
| **Restolibra** | **las 9 de arriba** | **esta función + `migrations/versions/`** |

Este módulo existe para que esas 9 tengan **una sola fuente de verdad**. Antes el
DDL vivía suelto adentro de `init_db()`, mezclado con seeds y con las llamadas a
los motores: la baseline de Alembic habría tenido que re-expresarlo y desde el
primer cambio habrían sido dos fuentes que se desincronizan. Acá la baseline
**llama a esta función**, igual que la `0001` de LibraCore llama a
`init_core_schema()`.

🔴 **Desde la revisión `0001`, esta función es de sólo lectura.** Todo cambio de
schema va como revisión nueva en `migrations/versions/`, no como línea agregada
acá. El motivo es el de siempre: `CREATE TABLE IF NOT EXISTS` crea lo que no está
y **no altera lo que sí**, así que una columna agregada acá llega a las
instancias nuevas y deja las viejas atrás, en silencio. Lo sostiene
`tests/test_schema_propio_congelado.py`.

Los tres `ALTER` guardados por introspección del final —`hora_retiro`,
`preparacion_at`/`listo_at`/`entregado_at`, `modificadores`— son el mecanismo de
migraciones **hecho a mano** que esta cadena viene a reemplazar. Se congelan tal
cual: ya corrieron en las tres instancias vivas, y sacarlos ahora dejaría sin
esas columnas a cualquier base que todavía no los haya visto. Los que vengan
después van como revisión.

Es idempotente a propósito, que es lo que permite correr la baseline sobre una
instancia viva: hace lo mismo que ya hace cada arranque, más registrar la
versión.
"""
# Desde `app.db_core` y no desde `libracore.db.core`: importarlo es lo que
# garantiza que `configure()` ya corrió con el destino de ESTA instancia. Es la
# convención del resto de los `db_*.py` de acá.
from app.db_core import _ar_now


def init_schema_propio(conn) -> None:
    """Las 9 tablas propias de Restolibra, sus índices y sus ALTER. Idempotente.

    La llaman `init_db()` (en cada arranque) y la baseline `0001` (en el
    deploy). Las dos con una conexión de `libracore.db.core`, que es la que
    traduce los `PRAGMA` y las excepciones entre SQLite y PostgreSQL.
    """
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
            -- catalog_items (LibraCommerce) y no `productos`: el catálogo
            -- se migró en P8 y esta FK quedó apuntando a la tabla vieja.
            -- Las instancias existentes ya se repuntaron en la migración
            -- de P8, pero este CREATE seguía naciendo con la FK vieja, así
            -- que una instancia NUEVA no podía cargar un ítem a un pedido
            -- (FOREIGN KEY constraint failed). Lo encontró la suite el
            -- 2026-07-30. Ver `recetas` más arriba, ya repuntada entonces.
            producto_id INTEGER REFERENCES catalog_items(id) ON DELETE SET NULL,
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

