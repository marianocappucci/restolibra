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

# Pasa por `log`, linea por linea, lo que le entra por stdin: la salida de los
# comandos del motor termina en el log del cron con el mismo formato que el resto.
log_lineas() {
  local linea
  while IFS= read -r linea; do
    [ -n "$linea" ] && log "$linea"
  done
  return 0
}

# --- LibraEdge: que la demo conserve sus nodos -----------------------------
# El reset borra la base entera, `node_identity` incluida: la PC que alguien vinculo a la demo amanecia con 401 todos
# los dias, y aunque se la volviera a vincular, el changelog nuevo numera desde 1 y un nodo con cursor 500 no baja nada
# nunca mas. `libraedge-central nodo conservar` guarda los nodos (con el HASH de su secreto, nunca el secreto) y el
# cursor maximo del changelog ANTES de borrar; `restaurar` los devuelve DESPUES de sembrar, deja la numeracion del
# changelog por encima de ese cursor y vuelve a publicar la referencia, asi el nodo baja el estado nuevo entero
# (libraedge ADR-022, v0.19.0).
#
# 🔴 **La demo es mas importante que el nodo:** nada de esto aborta el reset. Si falla --o si el libraedge del
# contenedor es de un pin anterior a v0.19.0 y no tiene los subcomandos-- se registra en el log y el reset sigue
# igual que antes.
#
# El archivo tiene hashes de secretos: permisos 600, bajo /root, y se borra al restaurar. Si una corrida no llega a
# restaurarlo (el seed fallo), queda: la proxima lo usa en vez de conservar de nuevo, porque la base de esa noche ya no
# tiene los nodos y conservar escribiria una lista vacia.
NODOS_DUMP="/root/libraedge-nodos-$CONTENEDOR.json"
NODOS_EN_CONTENEDOR=/tmp/libraedge-nodos.json
NODOS_PARA_RESTAURAR=0

# `libraedge-central nodo ...` ADENTRO del contenedor, con el aprovisionamiento del producto. La base va por
# RESTOLIBRA_DATABASE_URL: el contenedor no define LIBRAEDGE_DATABASE_URL.
edge_central() {
  docker exec "$CONTENEDOR" sh -c '
    LIBRAEDGE_APROVISIONAMIENTO=app.offline:aprovisionamiento \
    LIBRAEDGE_DATABASE_URL="$RESTOLIBRA_DATABASE_URL" \
    libraedge-central nodo "$@"
  ' sh "$@"
}

conservar_nodos() {
  # Uno vacio (una corrida cortada a mitad de la copia) no sirve y no tiene que trabar la conservacion de hoy.
  [ -s "$NODOS_DUMP" ] || rm -f "$NODOS_DUMP"
  if [ -e "$NODOS_DUMP" ]; then
    log "OJO: quedo $NODOS_DUMP de una corrida que no llego a restaurar los nodos: se usa ese (borrarlo si ya no sirve)."
    NODOS_PARA_RESTAURAR=1
    return 0
  fi
  if ! edge_central conservar --help >/dev/null 2>&1; then
    log "OJO: el libraedge de $CONTENEDOR no tiene \`nodo conservar\` (pin anterior a v0.19.0): los nodos no se conservan."
    return 0
  fi
  docker exec --user root "$CONTENEDOR" rm -f "$NODOS_EN_CONTENEDOR" || true
  if ! edge_central conservar --a "$NODOS_EN_CONTENEDOR" 2>&1 | log_lineas; then
    log "OJO: no se pudieron conservar los nodos: fallo \`conservar\`. El reset sigue."
    return 0
  fi
  # `umask 077` para que el archivo nazca 600: sale del contenedor por la redireccion, no por `docker cp`.
  if (umask 077; docker exec --user root "$CONTENEDOR" cat "$NODOS_EN_CONTENEDOR" > "$NODOS_DUMP") && [ -s "$NODOS_DUMP" ]; then
    NODOS_PARA_RESTAURAR=1
  else
    log "OJO: no se pudo sacar el archivo de nodos del contenedor. El reset sigue."
    rm -f "$NODOS_DUMP"
  fi
  docker exec --user root "$CONTENEDOR" rm -f "$NODOS_EN_CONTENEDOR" || true
}

restaurar_nodos() {
  [ "$NODOS_PARA_RESTAURAR" = 1 ] || return 0
  log "LibraEdge: restaurando los nodos de la demo"
  if docker exec -i "$CONTENEDOR" sh -c 'umask 077; cat > "$1"' sh "$NODOS_EN_CONTENEDOR" < "$NODOS_DUMP" \
      && edge_central restaurar --de "$NODOS_EN_CONTENEDOR" 2>&1 | log_lineas; then
    rm -f "$NODOS_DUMP"
    log "LibraEdge: nodos restaurados, archivo borrado"
  else
    log "OJO: no se pudieron restaurar los nodos; el archivo queda en $NODOS_DUMP y la proxima corrida lo usa."
  fi
  docker exec --user root "$CONTENEDOR" rm -f "$NODOS_EN_CONTENEDOR" || true
}

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

  # --- Los codigos de acceso: guardarlos ---------------------------------------
  # Antes el reset borraba los codigos de acceso entregados a clientes
  # potenciales: `demo_codigos` vive en la misma base que vacia el `DROP SCHEMA`.
  # Ahora se guardan ANTES de borrar y se devuelven despues del arranque; la
  # logica vive en el motor, `libracore.provisioning.demo_codigos` (ADR-039).
  # Si falla NO se aborta: la demo igual tiene que quedar limpia.
  CODIGOS_DUMP=/tmp/demo-codigos-$CONTENEDOR.sql
  DEMO_CODIGOS="$REPO/.venv-scripts/bin/libracore-demo-codigos"
  rm -f "$CODIGOS_DUMP"
  if [ -x "$DEMO_CODIGOS" ]; then
    "$DEMO_CODIGOS" guardar --sidecar "$SIDECAR" --archivo "$CODIGOS_DUMP" 2>&1 | log_lineas \
      || { log "OJO: no se pudieron guardar los codigos de acceso: fallo \`guardar\`."; rm -f "$CODIGOS_DUMP"; }
  else
    log "OJO: no se pudieron guardar los codigos de acceso: no existe $DEMO_CODIGOS"
  fi

  # --- LibraEdge: guardar los nodos ---------------------------------------------
  # Con la app todavia arriba (el CLI corre adentro del contenedor) y ANTES de pararla y borrar. Si falla NO se aborta.
  conservar_nodos || log "OJO: fallo la conservacion de los nodos de LibraEdge. El reset sigue."

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
  COMPOSE="${CLIENTES_DIR:-${LIBRA_CLIENTES_DIR:-$REPO/clientes}}/demo/docker-compose.yml"
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
  log "sin sidecar (SQLite): los codigos de acceso no se preservan"
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

# --- Los codigos de acceso: devolverlos ---------------------------------------
# La tabla ya existe: la crea `libraauth` al arrancar. Si falla no aborta: la
# demo ya quedo usable y se puede emitir un codigo nuevo (el comando dice OJO y
# deja el archivo en su lugar).
if [ -n "${SIDECAR:-}" ] && [ -x "$DEMO_CODIGOS" ]; then
  "$DEMO_CODIGOS" devolver --sidecar "$SIDECAR" --archivo "$CODIGOS_DUMP" 2>&1 | log_lineas \
    || log "OJO: fallo \`devolver\`; los codigos siguen en $CODIGOS_DUMP."
fi

# ⚠️ Este producto usa `ADMIN_USER`/`ADMIN_PASSWORD`, **sin prefijo**: es la
# variante `ensure_admin_user` de libraauth, la de los server-rendered. Los
# otros cuatro productos usan `<PRODUCTO>_ADMIN_*`. Las dos variables existen en
# el compose de la demo con contrasenas distintas, asi que usar la equivocada da
# un 401 que no dice por que.
# --- 2. Sembrar -----------------------------------------------------------
# El seed entra resolviendo el captcha ALTCHA (libraauth v0.40.0) y para eso
# importa `altcha`. Corre ADENTRO del contenedor, donde `python3` es el de
# /opt/venv (el Dockerfile lo pone primero en el PATH): el venv de la app, que
# trae `altcha` con libraauth. No es el python3 del sistema del VPS ni el de
# `.venv-scripts`, que no lo tienen: no cambiar este `python3` por ellos.
docker cp "$SEED_LOCAL" "$CONTENEDOR:/tmp/seed.py"
docker exec -i "$CONTENEDOR" sh -c '
  python3 /tmp/seed.py \
    --url https://demo.restolibra.com.ar \
    --usuario "${ADMIN_USER:-admin}" \
    --password "$ADMIN_PASSWORD"
'
# 🔴 `--user root` y `|| true`. `docker cp` deja el archivo como root y el contenedor corre
# sin privilegios (uid 10001) desde el 2026-10-15: `/tmp` es sticky, así que sin `--user root`
# este `rm` falla con "Operation not permitted" y, con `set -e`, el script sale 1 DESPUÉS de
# haber sembrado bien (mismo defecto que se corrigió en LibraCargo).
docker exec --user root "$CONTENEDOR" rm -f /tmp/seed.py || true

# --- LibraEdge: devolver los nodos --------------------------------------------
# DESPUES de sembrar: `restaurar` vuelve a publicar la referencia y siembra el changelog con la demo ya cargada, con
# cursores mayores a los que el nodo ya tiene. Si falla NO se aborta: la demo ya quedo sembrada.
restaurar_nodos || log "OJO: fallo la restauracion de los nodos de LibraEdge."

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
