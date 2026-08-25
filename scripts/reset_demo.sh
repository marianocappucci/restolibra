#!/usr/bin/env bash
# Reset diario de la demo publica de Restolibra.
#
# Deja la base de cero, el arranque reconstruye el esquema y despues se siembra.
# **El estado limpio es codigo, no un backup guardado a mano**: eso es lo que
# hace que sea reproducible, y que agregar un dato de ejemplo sea un commit y no
# una operacion manual sobre el servidor.
#
# 🔴 **Solo toca la instancia demo.** El contenedor esta escrito aca, no viene
# por argumento: un reset apuntado al contenedor equivocado le borra la base a un
# cliente, y no hay confirmacion que valga a las cuatro de la manana.
#
# 🔴 **Este archivo es el unico lugar donde vive la logica.** Hasta el
# 2026-08-10 habia una copia suelta en `/root/scripts-demo/reset_restolibra.sh`
# que el cron llamaba, y esa copia tenia defensas que este archivo no tenia.
# Ahora el cron llama a este y la suelta es un envoltorio de una linea.
set -euo pipefail

CONTENEDOR="restolibra-demo"
#: La raiz del checkout en el VPS. El script ya la usaba literal en los
#: `git -C` de mas abajo; ahora tambien la necesitan el compose de la
#: instancia y el venv del panel, asi que se nombra una sola vez.
REPO="/root/restolibra"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# --- La guarda ------------------------------------------------------------
case "$CONTENEDOR" in
  *-demo|*-publica) ;;
  *) log "ABORTA: '$CONTENEDOR' no parece una instancia demo."; exit 2 ;;
esac

# 🔴 La guarda del nombre no alcanza, y esto no es teorico: hasta el 2026-08-07
# el contenedor llamado `restolibra-demo` era el que servia
# sistema.restolibra.com.ar. El nombre decia demo y no lo era. Por eso se
# verifica una propiedad real de la instancia -DEMO_MODE, lo unico que enciende
# el auto-login publico- y no como se llama.
if ! docker exec "$CONTENEDOR" printenv DEMO_MODE 2>/dev/null | grep -qx 1; then
  log "ABORTA: $CONTENEDOR no tiene DEMO_MODE=1. El nombre no alcanza."
  exit 4
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
  log "ABORTA: el contenedor $CONTENEDOR no esta corriendo."
  exit 3
fi

log "=== reset de $CONTENEDOR ==="

# --- 0. El seed, ANTES de tocar la base -----------------------------------
# 🔴 El 2026-08-06 este script borro la base y recien despues descubrio que no
# podia sembrar: `scripts/seed_demo.py` vive en `develop` y el checkout del VPS
# esta en `main`. Cinco demos quedaron vacias. El orden correcto es conseguir el
# seed primero: si no esta, no se borra nada.
SEED_LOCAL=/tmp/seed-restolibra.py
git -C /root/restolibra fetch -q origin || { log "ABORTA: no se pudo hacer fetch de restolibra."; exit 5; }
git -C /root/restolibra show origin/develop:scripts/seed_demo.py > "$SEED_LOCAL" || { log "ABORTA: no esta scripts/seed_demo.py en origin/develop."; exit 6; }
[ -s "$SEED_LOCAL" ] || { log "ABORTA: el seed salio vacio."; exit 7; }
log "seed listo desde origin/develop ($(wc -l < "$SEED_LOCAL") lineas)"

# --- 1. Base de cero ------------------------------------------------------
# 🔴 Que sea "borrar el .db" depende del motor, y desde el corte a PostgreSQL ya
# no da igual: con la base en PostgreSQL, un `rm /app/data/*.db` borra archivos
# que no usa nadie, el contenedor reinicia contra los datos de ayer y el seed se
# apila encima. El reset seguiria diciendo "listo" todas las noches sin resetear
# nada. Por eso el motor se DETECTA, y si no se puede detectar se aborta.
URL_BASE=$(docker exec "$CONTENEDOR" printenv RESTOLIBRA_DATABASE_URL 2>/dev/null || true)

es_postgres() {
  case "$1" in postgres://*|postgresql://*|postgresql+*://*) return 0 ;; *) return 1 ;; esac
}

sidecar_de() {
  local sin_usuario=${1#*@}
  local host=${sin_usuario%%:*}
  echo "${host%%/*}"
}

base_de() {
  local sin_query=${1%%\?*}
  echo "${sin_query##*/}"
}

# Cuantas filas hay en tres tablas del dominio. Es la unica forma de que este
# script pueda DECIR que reseteo: se mide antes y despues, y si despues no dio
# cero, se aborta sin sembrar.
filas_del_dominio() {
  if es_postgres "$URL_BASE"; then
    docker exec -e BASE="$(base_de "$URL_BASE")" "$(sidecar_de "$URL_BASE")" sh -c '
      psql -tA -U "$POSTGRES_USER" -d "$BASE" -c "
        SELECT COALESCE((SELECT COUNT(*) FROM clients), 0)
             + COALESCE((SELECT COUNT(*) FROM facturas), 0)
             + COALESCE((SELECT COUNT(*) FROM catalog_items), 0)"
    ' 2>/dev/null || echo "?"
  else
    docker exec "$CONTENEDOR" python3 -c "
import sqlite3
try:
    c = sqlite3.connect('/app/data/restolibra.db')
    print(sum(c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
              for t in ('clients', 'facturas', 'catalog_items')))
except Exception:
    print('?')
" 2>/dev/null || echo "?"
  fi
}

ANTES=$(filas_del_dominio)
log "filas del dominio antes del reset: $ANTES"

if es_postgres "$URL_BASE"; then
  SIDECAR=$(sidecar_de "$URL_BASE")
  if ! docker ps --format '{{.Names}}' | grep -qx "$SIDECAR"; then
    log "ABORTA: el sidecar '$SIDECAR' no esta corriendo."
    exit 9
  fi
  log "motor: PostgreSQL (sidecar $SIDECAR)"

  # Se para la app ANTES de tocar el schema: con sus conexiones abiertas el
  # `DROP SCHEMA` no falla, se cuelga -- ya paso, veinte minutos en silencio.
  docker stop "$CONTENEDOR" >/dev/null
  log "app parada para soltar las conexiones"

  docker exec -e BASE="$(base_de "$URL_BASE")" "$SIDECAR" sh -c '
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$BASE" \
      -c "DROP SCHEMA IF EXISTS public CASCADE" \
      -c "CREATE SCHEMA public" \
      -c "GRANT ALL ON SCHEMA public TO \"$POSTGRES_USER\""
  ' >/dev/null || { log "ABORTA: no se pudo recrear el schema."; docker start "$CONTENEDOR" >/dev/null; exit 10; }
  log "schema recreado, vacio"

  # --- Las cadenas de migracion, ANTES de que arranque la app --------------
  #
  # 🔴 **Hasta el 2026-08-25 esto no existia, y por eso la demo amanecia sin
  # `alembic_version`.** El `DROP SCHEMA` de arriba se la lleva, y el arranque
  # de la app reconstruye las tablas con `create_all()`, que no deja marca. La
  # demo andaba igual, asi que no se veia: el sintoma aparecio del lado del
  # DEPLOY. Desde que `panel_admin.py actualizar` corre las migraciones, el
  # primer comando se encuentra un esquema ya creado y sin version.
  #
  # Con la cadena de LibraCore no se nota, porque su baseline es idempotente.
  # La de LibraGenda hace `CREATE TABLE` crudo y aborta el deploy con
  # `relation "resources" already exists` -- paso el 2026-08-25 en las demos de
  # Gestiolibra y MedLibra, que quedaron sin poder actualizarse.
  #
  # 🔑 **Los comandos NO se escriben aca.** Salen de `migraciones` del propio
  # `configure()` del producto, que es la misma fuente que lee el deploy. Una
  # cuarta copia de la cadena es exactamente como se llega a que el reset y el
  # deploy hagan cosas distintas.
  #
  # Corren con la app PARADA y en un contenedor efimero, igual que
  # `cmd_actualizar`: si la app arrancara antes, su `create_all()` dejaria las
  # tablas puestas y la cadena de LibraGenda volveria a chocar.
  COMPOSE="$REPO/clientes/demo/docker-compose.yml"
  [ -f "$COMPOSE" ] || { log "ABORTA: no encontre $COMPOSE."; docker start "$CONTENEDOR" >/dev/null; exit 11; }

  CADENAS=$("$REPO/.venv-scripts/bin/python" - <<PY || true
import sys
sys.path.insert(0, "$REPO")
import scripts.panel_admin  # su configure() deja la ProductConfig del producto
from libracore.provisioning import get_config
for comando in get_config().migraciones:
    print(" ".join(comando))
PY
)
  if [ -z "${CADENAS:-}" ]; then
    # Que no haya migraciones declaradas no es "no hay nada que hacer": es que
    # el reset dejaria la base a merced del `create_all()` otra vez.
    log "ABORTA: el producto no declara migraciones en su configure()."
    docker start "$CONTENEDOR" >/dev/null
    exit 11
  fi

  while IFS= read -r cmd; do
    [ -z "$cmd" ] && continue
    log "migraciones: $cmd"
    # shellcheck disable=SC2086 -- $cmd va sin comillas a proposito: es la
    # linea de comando completa y tiene que splitearse en argumentos.
    # 🔴 `-T` y `</dev/null` no son adorno: sin ellos `docker compose run`
    # abre una TTY y **se come el resto del heredoc** que alimenta este
    # `while read`. Medido corriendo el script de verdad: de las tres cadenas
    # corria SOLO la primera y el reset terminaba "bien" con dos migraciones
    # sin aplicar. Es el mismo filo que `docker exec` sin `-i`.
    docker compose -p "$CONTENEDOR" -f "$COMPOSE" run --rm -T "$CONTENEDOR" $cmd >/dev/null 2>&1 </dev/null \
      || { log "ABORTA: fallo \`$cmd\`."; docker start "$CONTENEDOR" >/dev/null; exit 11; }
  done <<CADENAS_EOF
$CADENAS
CADENAS_EOF

  docker start "$CONTENEDOR" >/dev/null
else
  log "motor: SQLite"
  # Se borran tambien los `-wal` y `-shm`: sin eso SQLite puede reconstruir
  # parte de lo borrado desde el journal, y el reset queda a medias.
  docker exec "$CONTENEDOR" sh -c 'rm -f /app/data/*.db /app/data/*.db-wal /app/data/*.db-shm'
  log "base borrada"
  docker restart "$CONTENEDOR" >/dev/null
fi

for _ in $(seq 1 40); do
  estado=$(docker inspect -f '{{.State.Health.Status}}' "$CONTENEDOR" 2>/dev/null || echo starting)
  [ "$estado" = "healthy" ] && break
  sleep 3
done
estado=$(docker inspect -f '{{.State.Health.Status}}' "$CONTENEDOR" 2>/dev/null || echo desconocido)
log "contenedor: $estado"
if [ "$estado" != "healthy" ]; then
  log "ABORTA: no levanto sano; no se siembra sobre una instancia rota."
  exit 4
fi

# --- 1b. Que de verdad haya reseteado -------------------------------------
DESPUES=$(filas_del_dominio)
log "filas del dominio despues del reset: $DESPUES"
if [ "$DESPUES" = "?" ]; then
  log "ABORTA: no pude contar las filas -- puede que una tabla haya cambiado de"
  log "        nombre. Sin poder medir, no se siembra."
  exit 11
fi
if [ "$DESPUES" != "0" ]; then
  log "ABORTA: la base no quedo vacia (antes $ANTES, despues $DESPUES)."
  log "        No se siembra encima: quedaria la demo de ayer mas la de hoy."
  exit 11
fi
if [ "$ANTES" = "0" ]; then
  log "OJO: antes tambien habia 0 filas -- el chequeo no probo nada esta vez."
fi

# ⚠️ Este producto usa `ADMIN_USER`/`ADMIN_PASSWORD`, **sin prefijo**: es la
# variante `ensure_admin_user` de libraauth, la de los server-rendered. Los
# otros cuatro productos usan `<PRODUCTO>_ADMIN_*`. Las dos variables existen en
# el compose de la demo con contrasenas distintas, asi que usar la equivocada da
# un 401 que no dice por que.
# --- 2. Sembrar -----------------------------------------------------------
docker cp "$SEED_LOCAL" "$CONTENEDOR:/tmp/seed.py"
docker exec -i "$CONTENEDOR" sh -c '
  python3 /tmp/seed.py \
    --url https://demo.restolibra.com.ar \
    --usuario "${ADMIN_USER:-admin}" \
    --password "$ADMIN_PASSWORD"
'
docker exec "$CONTENEDOR" rm -f /tmp/seed.py

# --- Un backup, para que esa pantalla no se abra vacia --------------------
# La demo se borra todas las noches, asi que nunca acumula backups sola.
#
# Desde el 2026-08-12 sale del motor (`libracore.respaldo`), igual que la
# pantalla: los helpers propios `_hacer_backup_automatico`/`_listar_backups`
# se removieron. El ZIP que deja aca es el mismo que el cliente puede bajar y
# restaurar, y lleva tambien el logo y los certificados de ARCA.
log "backup de cortesia para la pantalla de backups"
docker exec "$CONTENEDOR" python -c "
from app import database as db
from app.web.routers.config import BACKUPS_DIR, CERTS_DIR, LOGO_DIR
from libracore.respaldo import Instancia, crear_backup, listar_backups

instancia = Instancia(
    nombre=\"restolibra\",
    bases=([] if db.ES_POSTGRES else [db.DB_PATH]),
    postgres_url=(db.DB_PATH if db.ES_POSTGRES else None),
    directorios=[LOGO_DIR, CERTS_DIR],
)
crear_backup(instancia, BACKUPS_DIR, motivo=\"demo\")
print(\"  backups en la pantalla:\", len(listar_backups(BACKUPS_DIR)))
" 2>&1 | tail -2

log "=== listo ==="
