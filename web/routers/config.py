import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import datetime
import shutil
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Annotated

import config_manager
import database as db
from web.auth import require_auth, require_role

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

LOGO_DIR    = os.path.join(os.path.dirname(db.DB_PATH), "logos")
CERTS_DIR   = os.path.join(os.path.dirname(db.DB_PATH), "arca_certs")
BACKUPS_DIR = os.path.join(os.path.dirname(db.DB_PATH), "backups")


def _listar_backups() -> list[dict]:
    """Devuelve los backups automáticos disponibles, ordenados del más reciente al más antiguo."""
    if not os.path.exists(BACKUPS_DIR):
        return []
    result = []
    for f in sorted(os.listdir(BACKUPS_DIR), reverse=True):
        if not f.endswith(".db"):
            continue
        path = os.path.join(BACKUPS_DIR, f)
        stat = os.stat(path)
        result.append({
            "filename": f,
            "size_mb":  round(stat.st_size / 1_048_576, 2),
            "mtime":    datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return result


def _hacer_backup_automatico(motivo: str = "auto") -> str:
    """Hace checkpoint WAL y guarda copia de la DB actual. Retorna la ruta del backup."""
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    # Eliminar backups automáticos que superen los 10 más recientes
    backups = sorted(
        [f for f in os.listdir(BACKUPS_DIR) if f.endswith(".db")],
        reverse=True,
    )
    for old in backups[9:]:
        try:
            os.unlink(os.path.join(BACKUPS_DIR, old))
        except OSError:
            pass
    # Checkpoint WAL antes de copiar
    try:
        with db.get_connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(FULL)")
    except Exception:
        pass
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(BACKUPS_DIR, f"backup_{motivo}_{ts}.db")
    shutil.copy2(db.DB_PATH, dest)
    return dest


@router.get("/config/empresa/logo", include_in_schema=False)
def config_logo(user: Auth):
    cfg = config_manager.load()
    path = config_manager.resolve_logo_path(cfg)
    if not path or not os.path.exists(path):
        raise HTTPException(404)
    ext = os.path.splitext(path)[1].lower()
    media = "image/png" if ext == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media)


@router.get("/config/backup-db")
def config_backup_db(user: Auth):
    hoy      = datetime.date.today().strftime("%Y%m%d")
    filename = f"restolibra_backup_{hoy}.db"
    # Checkpoint WAL antes de servir el archivo
    try:
        with db.get_connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(FULL)")
    except Exception:
        pass
    return FileResponse(db.DB_PATH, media_type="application/octet-stream",
                        filename=filename)


@router.get("/config/backup-db/{filename}")
def config_download_autobackup(filename: str, user: Auth):
    """Descarga un backup automático específico."""
    if ".." in filename or "/" in filename:
        raise HTTPException(400)
    path = os.path.join(BACKUPS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path, media_type="application/octet-stream", filename=filename)
