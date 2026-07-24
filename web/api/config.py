"""API JSON de Configuracion para la SPA (ver wiki/entities/restolibra.md,
migracion a React). Reusa `config_manager`/`db_arca_config.py` tal cual --
mismo patron que Contalibra (ver wiki/entities/contalibra.md, Etapa B).
Admin-only en su totalidad (gateado en web/app.py con require_admin_json).

Los backups de la DB (`GET /config/backup-db[/{filename}]`, descargas de
archivo autenticadas por cookie) y el logo de empresa
(`GET /config/empresa/logo`) siguen sirviendose desde
`web/routers/config.py` sin tocar -- la SPA los linkea directo (misma
cookie, mismo origen), no hace falta una version JSON de un download.
`_listar_backups`/`BACKUPS_DIR`/`_hacer_backup_automatico` tambien se
reusan de ahi en vez de duplicar la logica.

Nota: las categorías de producto/egreso (`/config/categorias-producto`,
`/config/categorias-egreso`) siguen siendo páginas Jinja2 propias, linkeadas
directo desde el sidebar (ver Layout.tsx) -- no forman parte de este router
ni del Config.tsx de esta etapa (a diferencia de Contalibra, que las expone
como tab "Categorías" dentro de /config). Quedan fuera del alcance de este
módulo; portarlas es tarea de los módulos Productos/Egresos, no de Config.
"""
import os
import shutil
import sqlite3
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

import config_manager
import database as db
from web.routers.config import BACKUPS_DIR, CERTS_DIR, LOGO_DIR, _hacer_backup_automatico, _listar_backups

router = APIRouter(prefix="/api/config", tags=["config"])


def _arca_cfg() -> dict:
    configs = db.obtener_todas_arca_configs()
    return configs[0] if configs else {}


@router.get("")
def obtener():
    return {"cfg": config_manager.load(), "arca": _arca_cfg()}


class EmpresaPayload(BaseModel):
    empresa_nombre: str = ""
    empresa_direccion: str = ""
    empresa_cuit: str = ""
    empresa_telefono: str = ""
    empresa_email: str = ""
    empresa_iibb: str = ""
    empresa_iva_condition: str = ""
    empresa_inicio_actividades: str = ""


@router.put("/empresa")
def actualizar_empresa(payload: EmpresaPayload):
    existing = config_manager.load()
    cfg = {**payload.model_dump(), "logo_path": existing.get("logo_path", "")}
    config_manager.save(cfg)
    return config_manager.load()


@router.post("/empresa/logo")
async def subir_logo(logo: UploadFile = File(...)):
    ext = os.path.splitext(logo.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(422, "El logo debe ser PNG o JPG.")
    os.makedirs(LOGO_DIR, exist_ok=True)
    logo_path = os.path.join(LOGO_DIR, f"logo{ext}")
    with open(logo_path, "wb") as f:
        f.write(await logo.read())
    cfg = config_manager.load()
    cfg["logo_path"] = logo_path
    config_manager.save(cfg)
    return config_manager.load()


class MercadoPagoPayload(BaseModel):
    mp_access_token: str = ""
    mp_webhook_secret: str = ""
    mp_concepto_descripcion: str = ""
    mp_iva_rate: str = "0"
    mp_user_id: str = ""
    mp_pos_id: str = ""


@router.put("/mp")
def actualizar_mp(payload: MercadoPagoPayload):
    cfg = config_manager.load()
    cfg.update(payload.model_dump())
    config_manager.save(cfg)
    return config_manager.load()


class EmailPayload(BaseModel):
    email_smtp_host: str = ""
    email_smtp_port: str = "587"
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    email_from: str = ""
    email_from_name: str = ""


@router.put("/email")
def actualizar_email(payload: EmailPayload):
    cfg = config_manager.load()
    cfg["email_smtp_host"] = payload.email_smtp_host
    cfg["email_smtp_port"] = payload.email_smtp_port
    cfg["email_smtp_user"] = payload.email_smtp_user
    cfg["email_from"] = payload.email_from
    cfg["email_from_name"] = payload.email_from_name
    if payload.email_smtp_password:
        cfg["email_smtp_password"] = payload.email_smtp_password
    config_manager.save(cfg)
    return config_manager.load()


class ArcaPayload(BaseModel):
    empresa: str = "default"
    cuit: str = ""
    punto_venta: int = 1
    ambiente: str = "homologacion"
    alias: str = ""


@router.put("/arca")
def actualizar_arca(payload: ArcaPayload):
    empresa = payload.empresa.strip() or "default"
    existing = db.obtener_arca_config(empresa)
    if existing:
        db.actualizar_arca_config(
            empresa, cuit=payload.cuit, punto_venta=payload.punto_venta,
            ambiente=payload.ambiente, alias=payload.alias,
        )
    else:
        db.crear_arca_config(
            empresa=empresa, cuit=payload.cuit, punto_venta=payload.punto_venta,
            clave_path="", certificado_path="", ambiente=payload.ambiente, alias=payload.alias,
        )
    return _arca_cfg()


@router.post("/arca/certificados")
async def subir_certificados_arca(
    empresa: str = "default",
    clave_privada: UploadFile | None = File(None),
    certificado: UploadFile | None = File(None),
):
    empresa = empresa.strip() or "default"
    os.makedirs(CERTS_DIR, exist_ok=True)
    existing = db.obtener_arca_config(empresa) or {}
    clave_path = existing.get("clave_path", "")
    cert_path = existing.get("certificado_path", "")

    if clave_privada is not None and clave_privada.filename:
        clave_path = os.path.join(CERTS_DIR, "clave_privada.key")
        with open(clave_path, "wb") as f:
            f.write(await clave_privada.read())

    if certificado is not None and certificado.filename:
        cert_path = os.path.join(CERTS_DIR, "certificado.crt")
        with open(cert_path, "wb") as f:
            f.write(await certificado.read())

    if existing:
        db.actualizar_arca_config(empresa, clave_path=clave_path, certificado_path=cert_path)
    else:
        db.crear_arca_config(empresa=empresa, cuit="", punto_venta=1,
                              clave_path=clave_path, certificado_path=cert_path)
    return _arca_cfg()


class ServicioPayload(BaseModel):
    servicio_estado: str = "activo"
    servicio_mensaje: str = ""


@router.put("/servicio")
def actualizar_servicio(payload: ServicioPayload):
    estado = payload.servicio_estado if payload.servicio_estado in ("activo", "pausado", "suspendido") else "activo"
    cfg = config_manager.load()
    cfg["servicio_estado"] = estado
    cfg["servicio_mensaje"] = payload.servicio_mensaje
    config_manager.save(cfg)
    return config_manager.load()


class TicketPayload(BaseModel):
    ticket_ancho_mm: str = "80"
    ticket_fuente_size: str = "9"
    ticket_mostrar_logo: bool = False
    ticket_linea_corte: bool = True
    ticket_pie: str = ""


@router.put("/ticket")
def actualizar_ticket(payload: TicketPayload):
    cfg = config_manager.load()
    cfg["ticket_ancho_mm"] = payload.ticket_ancho_mm
    cfg["ticket_fuente_size"] = payload.ticket_fuente_size
    cfg["ticket_mostrar_logo"] = "1" if payload.ticket_mostrar_logo else "0"
    cfg["ticket_linea_corte"] = "1" if payload.ticket_linea_corte else "0"
    cfg["ticket_pie"] = payload.ticket_pie.strip()[:80]
    config_manager.save(cfg)
    return config_manager.load()


@router.get("/backups")
def listar_backups():
    return _listar_backups()


@router.post("/restore-db")
async def restaurar_db(backup_file: UploadFile = File(...)):
    content = await backup_file.read()
    if not content.startswith(b"SQLite format 3\x00"):
        raise HTTPException(422, "El archivo no es una base de datos SQLite válida.")

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    try:
        os.write(tmp_fd, content)
        os.close(tmp_fd)
        test = sqlite3.connect(tmp_path)
        result = test.execute("PRAGMA integrity_check").fetchone()[0]
        test.close()
        if result != "ok":
            raise HTTPException(422, f"La base de datos tiene errores de integridad: {result}")
    except sqlite3.Error as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise HTTPException(422, f"No se pudo validar el archivo: {e}")

    try:
        _hacer_backup_automatico("antes_restore")
    except Exception:
        pass

    shutil.move(tmp_path, db.DB_PATH)
    for ext in ("-wal", "-shm"):
        wal = db.DB_PATH + ext
        if os.path.exists(wal):
            try:
                os.unlink(wal)
            except OSError:
                pass

    return {"ok": True}
