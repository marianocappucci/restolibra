"""
Capa de servicios del backoffice: envuelve los scripts de gestión existentes
(`scripts/panel_admin.py`, `scripts/nuevo_cliente.py`, `scripts/npm_api.py`) y el
mapeo de planes (`plans.py`) para exponerlos a las rutas web de forma no interactiva.

No reimplementa Docker/NPM/backup: reutiliza las funciones ya probadas de la CLI.
"""
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))               # plans
sys.path.insert(0, str(REPO_ROOT / "scripts"))   # panel_admin, nuevo_cliente, npm_api

import plans                       # noqa: E402
import panel_admin as pa           # noqa: E402
import nuevo_cliente as nc         # noqa: E402

CLIENTES_DIR = pa.CLIENTES_DIR

ESTADOS_ACCION = {"start", "stop", "restart", "pausar", "suspender", "activar"}


class ServiceError(Exception):
    """Error de operación del backoffice."""


# ── lectura ────────────────────────────────────────────────────────────────────

def _modulos_activos(db_path: Path) -> int | None:
    """Cantidad de módulos habilitados en la DB del cliente (None si no se puede leer)."""
    if not db_path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        n = con.execute("SELECT COUNT(*) FROM modulos WHERE habilitado=1").fetchone()[0]
        con.close()
        return n
    except Exception:
        return None


def _enrich(c: dict) -> dict:
    """Agrega estado del contenedor, plan y conteo de módulos a un cliente."""
    info = pa.container_status(c["container"])
    db_path = c["dir"] / "data" / "restolibra.db"
    return {
        "nombre":      c.get("nombre", ""),
        "slug":        c["slug"],
        "domain":      c.get("domain", "") or "",
        "port":        c.get("port", ""),
        "container":   c["container"],
        "admin_user":  c.get("admin_user", ""),
        "plan":        c.get("plan", "") or "",
        "estado":      info["status"],
        "iniciado":    info["started"],
        "modulos_activos": _modulos_activos(db_path),
    }


def listar_clientes() -> list[dict]:
    return [_enrich(c) for c in pa.load_clients()]


def get_cliente(slug: str) -> dict | None:
    c = pa.find_client(slug)
    if not c:
        return None
    data = _enrich(c)
    data["dir"] = str(c["dir"])
    return data


# ── alta ───────────────────────────────────────────────────────────────────────

def crear_cliente(nombre, slug="", domain="", port=0, admin_user="admin",
                  admin_password="", plan="basico", setup_npm=True) -> dict:
    try:
        return nc.crear_cliente(
            nombre=nombre, slug=slug, domain=domain, port=int(port or 0),
            admin_user=admin_user or "admin", admin_password=admin_password,
            plan=plan, setup_npm=setup_npm,
        )
    except nc.ClienteError as e:
        raise ServiceError(str(e))


# ── edición de metadata ─────────────────────────────────────────────────────────

def editar_cliente(slug: str, nombre: str, domain: str) -> dict:
    c = pa.find_client(slug)
    if not c:
        raise ServiceError(f"Cliente '{slug}' no encontrado.")
    meta_path = c["dir"] / "cliente.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    dominio_prev = meta.get("domain", "") or ""
    meta["nombre"] = (nombre or "").strip() or meta.get("nombre", "")
    meta["domain"] = (domain or "").strip()
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # Si cambió el dominio, (re)crear el proxy NPM al nuevo dominio.
    if meta["domain"] and meta["domain"] != dominio_prev:
        _npm_crear_proxy(meta["domain"], meta.get("port", 0))
    return meta


# ── planes ──────────────────────────────────────────────────────────────────────

def set_plan(slug: str, plan: str) -> None:
    if plan not in plans.PLANES:
        raise ServiceError(f"Plan inválido: {plan!r}.")
    c = pa.find_client(slug)
    if not c:
        raise ServiceError(f"Cliente '{slug}' no encontrado.")
    db_path = c["dir"] / "data" / "restolibra.db"
    if not db_path.exists():
        raise ServiceError("La instancia todavía no inicializó su base de datos.")
    plans.aplicar_plan_en_db(str(db_path), plan)
    # Persistir el plan en cliente.json (metadato).
    meta_path = c["dir"] / "cliente.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["plan"] = plan
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


# ── estado / ciclo de vida del contenedor ───────────────────────────────────────

def accion_estado(slug: str, accion: str) -> None:
    if accion not in ESTADOS_ACCION:
        raise ServiceError(f"Acción inválida: {accion!r}.")
    c = pa.find_client(slug)
    if not c:
        raise ServiceError(f"Cliente '{slug}' no encontrado.")
    if accion == "start":
        pa.compose(slug, "up", "-d")
    elif accion == "restart":
        pa.compose(slug, "restart")
    elif accion == "stop":
        pa.compose(slug, "stop")
    else:
        # pausar / suspender / activar → estado de servicio (banner en la instancia)
        estado = {"pausar": "pausado", "suspender": "suspendido", "activar": "activo"}[accion]
        if not pa._set_servicio_estado(slug, estado):
            raise ServiceError("No se pudo cambiar el estado del servicio.")


# ── backup ──────────────────────────────────────────────────────────────────────

def backup_cliente(slug: str) -> str:
    """Crea un backup tar.gz del directorio data y devuelve la ruta del archivo."""
    c = pa.find_client(slug)
    if not c:
        raise ServiceError(f"Cliente '{slug}' no encontrado.")
    data_dir = c["dir"] / "data"
    if not data_dir.exists():
        raise ServiceError("El cliente no tiene datos para respaldar.")
    import tarfile
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = CLIENTES_DIR / f"{slug}_backup_{ts}.tar.gz"
    with tarfile.open(out_file, "w:gz") as tar:
        tar.add(data_dir, arcname=f"{slug}/data")
    return str(out_file)


# ── eliminación ─────────────────────────────────────────────────────────────────

def eliminar_cliente(slug: str, hacer_backup: bool = True) -> dict:
    """Baja: backup previo (opcional), elimina proxy NPM, baja el contenedor con
    su volumen y borra el directorio del cliente."""
    c = pa.find_client(slug)
    if not c:
        raise ServiceError(f"Cliente '{slug}' no encontrado.")

    resultado = {"slug": slug, "backup": None, "npm": None}
    if hacer_backup:
        resultado["backup"] = backup_cliente(slug)

    # Proxy NPM (best-effort)
    domain = c.get("domain", "") or ""
    if domain:
        resultado["npm"] = _npm_eliminar_proxy(domain)

    # Contenedor + volumen
    pa.compose(slug, "down", "-v")
    # Directorio del cliente
    shutil.rmtree(c["dir"])
    return resultado


# ── NPM helpers (best-effort, no rompen la operación si NPM no está) ─────────────

def _npm():
    if not pa._NPM_AVAILABLE:
        return None
    try:
        return pa.client_from_config()
    except Exception:
        return None


def _npm_crear_proxy(domain: str, port) -> bool | None:
    npm = _npm()
    if not npm:
        return None
    try:
        if npm.get_proxy_host_by_domain(domain):
            return True
        npm.create_proxy_host(
            domain=domain, forward_host=pa.forward_host_from_config(),
            forward_port=int(port or 0), ssl=True, le_email=pa.le_email_from_config(),
        )
        return True
    except Exception:
        return False


def _npm_eliminar_proxy(domain: str) -> bool | None:
    npm = _npm()
    if not npm:
        return None
    try:
        host = npm.get_proxy_host_by_domain(domain)
        if not host:
            return None
        return bool(npm.delete_proxy_host(host["id"]))
    except Exception:
        return False


# ── metadatos de planes para la UI ──────────────────────────────────────────────

def planes_info() -> list[dict]:
    return [
        {
            "key": p,
            "label": plans.PLAN_LABELS.get(p, p.title()),
            "precio": plans.PLAN_PRECIOS.get(p),
            "modulos": sorted(plans.modulos_de_plan(p)),
        }
        for p in plans.PLANES
    ]
