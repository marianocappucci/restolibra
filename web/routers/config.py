import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import datetime
import shutil
import sqlite3
import tempfile
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from typing import Annotated

import config_manager
import database as db
from web.auth import require_auth
from web.templates_config import templates

router = APIRouter()

Auth = Annotated[str, Depends(require_auth)]

LOGO_DIR    = os.path.join(os.path.dirname(db.DB_PATH), "logos")
CERTS_DIR   = os.path.join(os.path.dirname(db.DB_PATH), "arca_certs")
BACKUPS_DIR = os.path.join(os.path.dirname(db.DB_PATH), "backups")


def _arca_cfg():
    configs = db.obtener_todas_arca_configs()
    return configs[0] if configs else {}


@router.get("/config/empresa/logo", include_in_schema=False)
def config_logo(user: Auth):
    cfg = config_manager.load()
    path = config_manager.resolve_logo_path(cfg)
    if not path or not os.path.exists(path):
        raise HTTPException(404)
    ext = os.path.splitext(path)[1].lower()
    media = "image/png" if ext == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media)


@router.get("/config")
def config_get(request: Request, user: Auth, tab: str = "empresa", seccion: str = "mp"):
    return templates.TemplateResponse(request, "config.html", {
        "cfg":           config_manager.load(),
        "arca":          _arca_cfg(),
        "active":        "config",
        "tab":           tab,
        "seccion":       seccion,
        "saved":         None,
        "restore_error": None,
        "backups":       _listar_backups() if tab == "datos" else [],
    })


@router.post("/config/empresa")
async def config_empresa_post(request: Request, user: Auth):
    form = await request.form()
    existing = config_manager.load()
    cfg = {
        "empresa_nombre":    str(form.get("empresa_nombre", "")).strip(),
        "empresa_direccion": str(form.get("empresa_direccion", "")).strip(),
        "empresa_cuit":      str(form.get("empresa_cuit", "")).strip(),
        "empresa_telefono":  str(form.get("empresa_telefono", "")).strip(),
        "empresa_email":     str(form.get("empresa_email", "")).strip(),
        "empresa_iibb":           str(form.get("empresa_iibb", "")).strip(),
        "empresa_iva_condition":       str(form.get("empresa_iva_condition", "")).strip(),
        "empresa_inicio_actividades":  str(form.get("empresa_inicio_actividades", "")).strip(),
        "logo_path":                   existing.get("logo_path", ""),
    }
    logo_file = form.get("logo")
    if logo_file and hasattr(logo_file, "filename") and logo_file.filename:
        ext = os.path.splitext(logo_file.filename)[1].lower()
        if ext in (".png", ".jpg", ".jpeg"):
            os.makedirs(LOGO_DIR, exist_ok=True)
            logo_path = os.path.join(LOGO_DIR, f"logo{ext}")
            content = await logo_file.read()
            with open(logo_path, "wb") as f:
                f.write(content)
            cfg["logo_path"] = logo_path
    config_manager.save(cfg)
    return templates.TemplateResponse(request, "config.html", {
        "cfg": cfg, "arca": _arca_cfg(),
        "active": "config", "tab": "empresa", "saved": "empresa",
    })


# Mantener compatibilidad con el POST anterior
@router.post("/config")
async def config_post_compat(request: Request, user: Auth):
    return await config_empresa_post(request, user)


@router.post("/config/mp")
async def config_mp_post(request: Request, user: Auth):
    form = await request.form()
    cfg = config_manager.load()
    cfg["mp_access_token"]         = str(form.get("mp_access_token", "")).strip()
    cfg["mp_webhook_secret"]       = str(form.get("mp_webhook_secret", "")).strip()
    cfg["mp_concepto_descripcion"] = str(form.get("mp_concepto_descripcion", "")).strip()
    cfg["mp_iva_rate"]             = str(form.get("mp_iva_rate", "0")).strip()
    cfg["mp_user_id"]              = str(form.get("mp_user_id", "")).strip()
    cfg["mp_pos_id"]               = str(form.get("mp_pos_id", "")).strip()
    config_manager.save(cfg)
    return templates.TemplateResponse(request, "config.html", {
        "cfg": cfg, "arca": _arca_cfg(), "active": "config",
        "tab": "integraciones", "seccion": "mp", "saved": "mp",
        "restore_error": None, "backups": [],
    })


@router.post("/config/email")
async def config_email_post(request: Request, user: Auth):
    form = await request.form()
    cfg = config_manager.load()
    cfg["email_smtp_host"] = str(form.get("email_smtp_host", "")).strip()
    cfg["email_smtp_port"] = str(form.get("email_smtp_port", "587")).strip()
    cfg["email_smtp_user"] = str(form.get("email_smtp_user", "")).strip()
    cfg["email_from"]      = str(form.get("email_from", "")).strip()
    cfg["email_from_name"] = str(form.get("email_from_name", "")).strip()
    new_pass = str(form.get("email_smtp_password", "")).strip()
    if new_pass:
        cfg["email_smtp_password"] = new_pass
    config_manager.save(cfg)
    return templates.TemplateResponse(request, "config.html", {
        "cfg": cfg, "arca": _arca_cfg(), "active": "config",
        "tab": "integraciones", "seccion": "mail", "saved": "mail",
        "restore_error": None, "backups": [],
    })


# Compatibilidad con el form anterior (si quedara algún link)
@router.post("/config/integraciones")
async def config_integraciones_compat(request: Request, user: Auth):
    return await config_mp_post(request, user)


@router.post("/config/arca")
async def config_arca_post(request: Request, user: Auth):
    form = await request.form()
    empresa     = str(form.get("empresa", "")).strip() or "default"
    cuit        = str(form.get("cuit", "")).strip()
    punto_venta = int(form.get("punto_venta", "1") or "1")
    ambiente    = str(form.get("ambiente", "homologacion")).strip()
    alias       = str(form.get("alias", "")).strip()

    os.makedirs(CERTS_DIR, exist_ok=True)

    existing = db.obtener_arca_config(empresa) or {}
    clave_path = existing.get("clave_path", "")
    cert_path  = existing.get("certificado_path", "")

    # Guardar clave privada si se subió
    clave_file = form.get("clave_privada")
    if clave_file and hasattr(clave_file, "filename") and clave_file.filename:
        clave_path = os.path.join(CERTS_DIR, "clave_privada.key")
        with open(clave_path, "wb") as f:
            f.write(await clave_file.read())

    # Guardar certificado si se subió
    cert_file = form.get("certificado")
    if cert_file and hasattr(cert_file, "filename") and cert_file.filename:
        cert_path = os.path.join(CERTS_DIR, "certificado.crt")
        with open(cert_path, "wb") as f:
            f.write(await cert_file.read())

    if existing:
        db.actualizar_arca_config(
            empresa, cuit=cuit, punto_venta=punto_venta,
            clave_path=clave_path, certificado_path=cert_path,
            ambiente=ambiente, alias=alias,
        )
    else:
        db.crear_arca_config(
            empresa=empresa, cuit=cuit, punto_venta=punto_venta,
            clave_path=clave_path, certificado_path=cert_path,
            ambiente=ambiente, alias=alias,
        )

    return templates.TemplateResponse(request, "config.html", {
        "cfg": config_manager.load(), "arca": _arca_cfg(),
        "active": "config", "tab": "integraciones", "seccion": "arca",
        "saved": "arca", "restore_error": None, "backups": [],
    })


@router.post("/config/servicio")
async def config_servicio_post(request: Request, user: Auth):
    form    = await request.form()
    estado  = str(form.get("servicio_estado", "activo"))
    mensaje = str(form.get("servicio_mensaje", "")).strip()
    if estado not in ("activo", "pausado", "suspendido"):
        estado = "activo"
    existing = config_manager.load()
    existing["servicio_estado"]  = estado
    existing["servicio_mensaje"] = mensaje
    config_manager.save(existing)
    return templates.TemplateResponse(request, "config.html", {
        "cfg": config_manager.load(), "arca": _arca_cfg(),
        "active": "config", "tab": "servicio", "saved": "servicio",
    })


@router.post("/config/ticket")
async def config_ticket_post(request: Request, user: Auth):
    form = await request.form()
    existing = config_manager.load()
    existing["ticket_ancho_mm"]    = str(form.get("ticket_ancho_mm", "80")).strip()
    existing["ticket_fuente_size"] = str(form.get("ticket_fuente_size", "9")).strip()
    existing["ticket_mostrar_logo"]= "1" if form.get("ticket_mostrar_logo") else "0"
    existing["ticket_linea_corte"] = "1" if form.get("ticket_linea_corte") else "0"
    existing["ticket_pie"]         = str(form.get("ticket_pie", "")).strip()[:80]
    config_manager.save(existing)
    return templates.TemplateResponse(request, "config.html", {
        "cfg": existing, "arca": _arca_cfg(),
        "active": "config", "tab": "ticket", "saved": "ticket",
    })


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
        from fastapi import HTTPException
        raise HTTPException(400)
    path = os.path.join(BACKUPS_DIR, filename)
    if not os.path.exists(path):
        from fastapi import HTTPException
        raise HTTPException(404)
    return FileResponse(path, media_type="application/octet-stream", filename=filename)


@router.post("/config/restore-db")
async def config_restore_db(request: Request, user: Auth):
    form    = await request.form()
    archivo = form.get("backup_file")

    def _err(msg):
        return templates.TemplateResponse(request, "config.html", {
            "cfg": config_manager.load(), "arca": _arca_cfg(),
            "active": "config", "tab": "datos",
            "saved": None, "restore_error": msg,
            "backups": _listar_backups(),
        }, status_code=422)

    if not archivo or not hasattr(archivo, "filename") or not archivo.filename:
        return _err("Seleccioná un archivo .db para restaurar.")

    content = await archivo.read()

    # Validar magic bytes SQLite
    if not content.startswith(b"SQLite format 3\x00"):
        return _err("El archivo no es una base de datos SQLite válida.")

    # Escribir a archivo temporal y verificar integridad
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    try:
        os.write(tmp_fd, content)
        os.close(tmp_fd)
        test = sqlite3.connect(tmp_path)
        result = test.execute("PRAGMA integrity_check").fetchone()[0]
        test.close()
        if result != "ok":
            return _err(f"La base de datos tiene errores de integridad: {result}")
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return _err(f"No se pudo validar el archivo: {e}")

    # Backup automático de la DB actual antes de reemplazar
    try:
        _hacer_backup_automatico("antes_restore")
    except Exception:
        pass

    # Reemplazar DB y limpiar WAL de la DB vieja
    shutil.move(tmp_path, db.DB_PATH)
    for ext in ("-wal", "-shm"):
        wal = db.DB_PATH + ext
        if os.path.exists(wal):
            try:
                os.unlink(wal)
            except OSError:
                pass

    return templates.TemplateResponse(request, "config.html", {
        "cfg": config_manager.load(), "arca": _arca_cfg(),
        "active": "config", "tab": "datos",
        "saved": "restore", "restore_error": None,
        "backups": _listar_backups(),
    })


@router.get("/config/categorias-producto")
def categorias_producto_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "config/categorias_producto.html", {
        "categorias": db.get_categorias_producto(),
        "active": "config",
    })


@router.post("/config/categorias-producto")
async def categorias_producto_post(request: Request, user: Auth):
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if nombre:
        try:
            db.create_categoria_producto(nombre)
        except Exception:
            pass
    return RedirectResponse("/config/categorias-producto", status_code=303)


@router.post("/config/categorias-producto/{cid}/eliminar")
def categorias_producto_eliminar(cid: int, user: Auth):
    db.delete_categoria_producto(cid)
    return RedirectResponse("/config/categorias-producto", status_code=303)


@router.get("/config/categorias-egreso")
def categorias_egreso_get(request: Request, user: Auth):
    return templates.TemplateResponse(request, "config/categorias_egreso.html", {
        "categorias": db.get_categorias_egreso(),
        "active": "config",
    })


@router.post("/config/categorias-egreso")
async def categorias_egreso_post(request: Request, user: Auth):
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    if nombre:
        try:
            db.create_categoria_egreso(nombre)
        except Exception:
            pass
    return RedirectResponse("/config/categorias-egreso", status_code=303)


@router.post("/config/categorias-egreso/{cid}/eliminar")
def categorias_egreso_eliminar(cid: int, user: Auth):
    db.delete_categoria_egreso(cid)
    return RedirectResponse("/config/categorias-egreso", status_code=303)
