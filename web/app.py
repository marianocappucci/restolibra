import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import httpx

import database as db
import config_manager
import arca_wsaa
import arca_wspadron
from web.auth import (
    require_auth, check_credentials, get_current_user,
    create_session_cookie, clear_session_cookie,
    SECRET_KEY,
)
from web.routers import clientes, remitos, presupuestos, facturas, config as config_router, caja, webhooks, dashboard
from web.routers import mp_bandeja as mp_bandeja_router
from web.routers import usuarios as usuarios_router
from web.routers import productos as productos_router
from web.routers import ventas as ventas_router
from web.routers import stock as stock_router
from web.routers import turnos as turnos_router
from web.routers import logs as logs_router
from web.routers import reportes as reportes_router
from web.routers import depositos as depositos_router
from web.routers import cajas as cajas_router
from web.routers import egresos as egresos_router
from web.routers import proveedores as proveedores_router
from web.routers import tesoreria as tesoreria_router
from web.routers import cuenta_corriente as cc_router
from web.routers import listas_precio as listas_precio_router
from web.routers import libros_iva as libros_iva_router
from web.routers import salon as salon_router
from web.routers import kds as kds_router

app = FastAPI(title="Restolibra")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


_BYPASS_PATHS = {"/suspendido", "/login", "/logout", "/favicon.ico"}

class CurrentUserMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/static"):
            return await call_next(request)
        username = get_current_user(request)
        request.state.current_user = db.get_usuario_by_username(username) if username else None
        try:
            cfg = config_manager.load()
            request.state.empresa_nombre   = cfg.get("empresa_nombre", "")
            request.state.servicio_estado  = cfg.get("servicio_estado", "activo")
            request.state.servicio_mensaje = cfg.get("servicio_mensaje", "")
        except Exception:
            request.state.empresa_nombre   = ""
            request.state.servicio_estado  = "activo"
            request.state.servicio_mensaje = ""
        try:
            mods = db.get_modulos()
            request.state.modulos = {m for m, on in mods.items() if on}
        except Exception:
            request.state.modulos = set()
        try:
            request.state.mp_pending_count = db.get_mp_pending_count()
        except Exception:
            request.state.mp_pending_count = 0

        # Corte de servicio: redirigir todo excepto rutas de bypass y archivos estáticos
        estado = request.state.servicio_estado
        path   = request.url.path
        if (estado == "suspendido"
                and path not in _BYPASS_PATHS
                and not path.startswith("/static")):
            from fastapi.responses import RedirectResponse as _RR
            return _RR("/suspendido")

        return await call_next(request)


app.add_middleware(CurrentUserMiddleware)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/suspendido")
def servicio_suspendido(request: Request):
    return templates.TemplateResponse(request, "suspendido.html", {
        "mensaje": request.state.servicio_mensaje,
        "empresa": request.state.empresa_nombre,
    })


app.include_router(dashboard.router)
app.include_router(clientes.router)
app.include_router(remitos.router)
app.include_router(presupuestos.router)
app.include_router(facturas.router)
app.include_router(config_router.router)
app.include_router(caja.router)
app.include_router(webhooks.router)
app.include_router(usuarios_router.router)
app.include_router(productos_router.router)
app.include_router(ventas_router.router)
app.include_router(stock_router.router)
app.include_router(turnos_router.router)
app.include_router(logs_router.router)
app.include_router(reportes_router.router)
app.include_router(mp_bandeja_router.router)
app.include_router(depositos_router.router)
app.include_router(cajas_router.router)
app.include_router(egresos_router.router)
app.include_router(proveedores_router.router)
app.include_router(tesoreria_router.router)
app.include_router(cc_router.router)
app.include_router(listas_precio_router.router)
app.include_router(libros_iva_router.router)
app.include_router(salon_router.router)
app.include_router(kds_router.router)


@app.on_event("startup")
def startup():
    db.init_db()
    db.ensure_admin_user()


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/dashboard")


@app.get("/login", include_in_schema=False)
def login_get(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", include_in_schema=False)
async def login_post(request: Request):
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")
    if check_credentials(username, password):
        db.registrar_auth_event("login", username, ip)
        response = RedirectResponse("/dashboard", status_code=303)
        create_session_cookie(response, username)
        return response
    db.registrar_auth_event("login_fallido", username, ip)
    return templates.TemplateResponse(
        request, "login.html", {"error": "Usuario o contraseña incorrectos"}, status_code=401
    )


@app.get("/logout", include_in_schema=False)
def logout(request: Request):
    username = get_current_user(request) or ""
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")
    if username:
        db.registrar_auth_event("logout", username, ip)
    response = RedirectResponse("/login", status_code=303)
    clear_session_cookie(response)
    return response


@app.get("/api/arca/estado", include_in_schema=False)
def arca_estado(user: str = Depends(require_auth)):
    configs = db.obtener_todas_arca_configs()
    if not configs:
        return JSONResponse({"configurado": False})
    cfg = configs[0]
    cert_path, clave_path = config_manager.resolve_cert_paths(
        cfg.get("certificado_path", ""), cfg.get("clave_path", "")
    )
    tiene_cert  = bool(cert_path) and os.path.exists(cert_path)
    tiene_clave = bool(clave_path) and os.path.exists(clave_path)
    return JSONResponse({
        "configurado": tiene_cert and tiene_clave,
        "ambiente": cfg.get("ambiente", ""),
        "cuit": cfg.get("cuit", ""),
        "tiene_certificado": tiene_cert,
        "tiene_clave": tiene_clave,
    })


@app.get("/api/arca/probar", include_in_schema=False)
async def arca_probar(user: str = Depends(require_auth)):
    configs = db.obtener_todas_arca_configs()
    if not configs:
        return JSONResponse({"ok": False, "error": "ARCA no está configurado."}, status_code=400)

    cfg        = configs[0]
    cert_path, key_path = config_manager.resolve_cert_paths(
        cfg.get("certificado_path", ""), cfg.get("clave_path", "")
    )
    ambiente   = cfg.get("ambiente", "homologacion")

    # Validar archivos localmente primero
    errores = arca_wsaa.validar_archivos(cert_path, key_path)
    if errores:
        return JSONResponse({"ok": False, "error": " | ".join(errores)}, status_code=400)

    # Info del certificado
    info = arca_wsaa.info_certificado(cert_path)

    # Autenticar contra WSAA
    try:
        ta = await arca_wsaa.autenticar(cert_path, key_path, ambiente)
        return JSONResponse({
            "ok": True,
            "ambiente": ambiente,
            "expiracion": ta["expiracion"],
            "cert_vencimiento": info.get("vencimiento"),
            "cert_dias_restantes": info.get("dias_restantes"),
            "cert_subject": info.get("subject"),
        })
    except RuntimeError as e:
        return JSONResponse({"ok": False, "error": str(e), "cert": info}, status_code=502)


@app.get("/api/email/probar", include_in_schema=False)
async def email_probar(user: str = Depends(require_auth)):
    import smtplib
    cfg = config_manager.load()
    host     = cfg.get("email_smtp_host", "").strip()
    port     = int(cfg.get("email_smtp_port", 587) or 587)
    smtp_user = cfg.get("email_smtp_user", "").strip()
    password = cfg.get("email_smtp_password", "").strip()
    if not host or not smtp_user or not password:
        return JSONResponse({"ok": False, "error": "Completá host, usuario y contraseña antes de probar."}, status_code=400)
    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, password)
        return JSONResponse({"ok": True, "host": host, "port": port, "user": smtp_user})
    except smtplib.SMTPAuthenticationError:
        return JSONResponse({"ok": False, "error": "Autenticación fallida. Verificá el usuario y la contraseña de aplicación."}, status_code=401)
    except smtplib.SMTPConnectError as e:
        return JSONResponse({"ok": False, "error": f"No se pudo conectar al servidor: {e}"}, status_code=502)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)


@app.get("/api/mp/probar", include_in_schema=False)
async def mp_probar(user: str = Depends(require_auth)):
    cfg = config_manager.load()
    token = cfg.get("mp_access_token", "").strip()
    if not token:
        return JSONResponse({"ok": False, "error": "No hay Access Token configurado."}, status_code=400)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.mercadopago.com/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code != 200:
            return JSONResponse({"ok": False, "error": f"MP respondió {r.status_code}: {r.text[:200]}"}, status_code=502)
        data = r.json()
        return JSONResponse({
            "ok":        True,
            "user_id":   data.get("id"),
            "nickname":  data.get("nickname"),
            "email":     data.get("email"),
            "site_id":   data.get("site_id"),
            "pais":      data.get("country_id"),
        })
    except httpx.RequestError as e:
        return JSONResponse({"ok": False, "error": f"Sin conexión con MercadoPago: {e}"}, status_code=502)


@app.get("/api/arca/certificado-info", include_in_schema=False)
def arca_cert_info(user: str = Depends(require_auth)):
    configs = db.obtener_todas_arca_configs()
    if not configs:
        return JSONResponse({"error": "Sin configuracion"}, status_code=404)
    cert_path, _ = config_manager.resolve_cert_paths(
        configs[0].get("certificado_path", ""), configs[0].get("clave_path", "")
    )
    return JSONResponse(arca_wsaa.info_certificado(cert_path))


@app.get("/api/consultar-cuit/{cuit}", include_in_schema=False)
async def consultar_cuit(cuit: str, user: str = Depends(require_auth)):
    cuit_limpio = re.sub(r"[^0-9]", "", cuit)
    if len(cuit_limpio) != 11:
        return JSONResponse({"error": "CUIT inválido. Debe tener 11 dígitos."}, status_code=400)

    arca_cfg = db.obtener_todas_arca_configs()
    arca     = arca_cfg[0] if arca_cfg else None

    if not arca or not arca.get("certificado_path") or not arca.get("clave_path"):
        return JSONResponse(
            {"error": "Configurá los certificados ARCA en Configuración para habilitar la consulta de CUIT."},
            status_code=503,
        )

    cert_path, clave_path = config_manager.resolve_cert_paths(
        arca["certificado_path"], arca["clave_path"]
    )
    try:
        ta = await arca_wsaa.autenticar(
            cert_path, clave_path, arca["ambiente"],
            servicio="ws_sr_padron_a13",
        )
        datos = await arca_wspadron.consultar_persona(
            arca["cuit"], cuit_limpio, ta["token"], ta["sign"], arca["ambiente"]
        )
        return JSONResponse(datos)

    except RuntimeError as e:
        msg = str(e)
        if "no encontrado" in msg.lower() or "inexistente" in msg.lower():
            return JSONResponse({"error": msg}, status_code=404)
        # Error de autorización del servicio en WSAA
        if "coe" in msg.lower() or "no autorizado" in msg.lower() or "constraints" in msg.lower() or "sin acceso" in msg.lower():
            return JSONResponse({
                "error": (
                    "El certificado no tiene acceso al servicio de Padrón (ws_sr_padron_a13). "
                    "Ingresá a ARCA → Administración de Relaciones → delegá el servicio "
                    "'Consulta a Padrón Alcance 13' para tu CUIT y volvé a intentarlo."
                )
            }, status_code=403)
        return JSONResponse({"error": msg}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": f"Error al consultar ARCA: {e}"}, status_code=500)
