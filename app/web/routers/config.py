import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Annotated

from app import config_manager
from app import database as db
from app.web.auth import require_auth, require_role

# Configuración del sistema (credenciales MercadoPago/ARCA, backup/restore de la
# DB completa) — solo admin. Antes solo exigía estar logueado: cualquier
# cajero/operador podía descargar la base entera o cambiar esas credenciales
# (ver wiki/analyses/restolibra-auditoria-produccion).
#
# Las paginas y acciones Jinja2 de gestion general (list de tabs, empresa,
# mp, email, arca, servicio, ticket, restore-db, categorias-producto,
# categorias-egreso) se removieron en el corte de la migracion a React --
# ver wiki/entities/restolibra.md, Etapas D y E; ahora viven en
# web/api/config.py + frontend/src/pages/Config.tsx, CategoriasProducto.tsx
# y CategoriasEgreso.tsx (esta ultima, gap real encontrado durante el corte
# de la Etapa E, cerrado en la misma pasada).
#
# Sobreviven: el logo (servido por esta misma URL vieja, ver <img> en
# Config.tsx) y el backup rápido/backups automáticos (linkeados directo
# desde Config.tsx, nunca se reimplementaron como JSON).
#
# `CERTS_DIR`/`LOGO_DIR`/`BACKUPS_DIR`/`_hacer_backup_automatico`/
# `_listar_backups` NO se borran pese a que las rutas Jinja2 que los usaban
# (arca, empresa, restore-db) se removieron: web/api/config.py los importa
# tal cual (sin duplicarlos) para los endpoints JSON equivalentes
# (PUT /arca, POST /arca/certificados, POST /empresa/logo, GET /backups,
# POST /restore-db).
router = APIRouter(dependencies=[Depends(require_role("admin"))])

Auth = Annotated[str, Depends(require_auth)]

# 🔴 De `DATA_DIR` y NO de `os.path.dirname(db.DB_PATH)`, que es como estaba.
# Con la base en PostgreSQL `db.DB_PATH` es una URL, y `dirname()` de
# `postgresql://usuario:clave@host:5432/base` devuelve
# `postgresql://usuario:clave@host:5432`: las tres carpetas quedaban colgando de
# una ruta inventada **con la contrasena en el nombre**. Y no son carpetas
# cualquiera -- ahi viven el logo de la empresa y los **certificados de ARCA**,
# que son los que dejan facturar.
#
# La carpeta de datos siempre fue esta; la ruta de la base era una forma
# indirecta de llegar que funcionaba solo mientras la base fuera un archivo.
_DATA_DIR = os.environ.get("DATA_DIR") or os.path.dirname(os.path.abspath(db.__file__))

LOGO_DIR    = os.path.join(_DATA_DIR, "logos")
CERTS_DIR   = os.path.join(_DATA_DIR, "arca_certs")
BACKUPS_DIR = os.path.join(_DATA_DIR, "backups")



@router.get("/config/empresa/logo", include_in_schema=False)
def config_logo(user: Auth):
    cfg = config_manager.load()
    path = config_manager.resolve_logo_path(cfg)
    if not path or not os.path.exists(path):
        raise HTTPException(404)
    ext = os.path.splitext(path)[1].lower()
    media = "image/png" if ext == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media)



# 🔴 Acá vivían `_listar_backups()`, `_hacer_backup_automatico()` y las rutas
# `/config/backup-db[/{filename}]`. Se removieron el 2026-08-12: la pantalla de
# Datos / Backup pasa a salir de `libracore.respaldo`, igual que en los otros
# cinco productos. El router del motor se monta en `web/app.py`, y `BACKUPS_DIR`
# de acá arriba es el directorio que recibe.
#
# **No fue una normalización de prolijidad: lo propio estaba roto.** Desde el
# corte a PostgreSQL, los dos caminos fallaban escribiendo la URL de la base
# —con la contraseña— en el mensaje de error: `FileResponse(db.DB_PATH)` sobre
# una URL, y un restore que exigía `SQLite format 3` —rechazando el `.dump` que
# el propio producto generaba— para después hacer `shutil.move()` sobre esa
# misma URL.
#
# Y aun andando, el backup propio se llevaba **sólo la base**: los logos y los
# certificados de ARCA quedaban afuera. El del motor toma la instancia entera.
#
# Se migró primero en Contalibra, que es el upstream del motor contable, y de
# ahí acá — pero **aplicado a mano y no por `git merge`**: el merge del fork ya
# no converge (conflictos `add/add` en casi todo el árbol, medido el 2026-08-12).
