"""
Backoffice Restolibra — panel de superadmin para gestionar clientes (alta, edición,
baja) y sus planes (asignar / upgrade / downgrade) a través de todos los contenedores.

App separada host-level. Se ejecuta:
    uvicorn admin.app:app --host 0.0.0.0 --port 8000
desde la raíz del repo, con acceso al socket Docker y al directorio clientes/.
"""
import os

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse, JSONResponse

from admin import auth, services
from admin.templates_config import templates
from admin.routers import clientes as clientes_router

app = FastAPI(title="Restolibra Backoffice", docs_url=None, redoc_url=None)

DOCS_AUTH_SECRET = os.environ.get("DOCS_AUTH_SECRET", "")


@app.get("/login")
def login_form(request: Request, error: str = ""):
    if auth.current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": error})


@app.post("/login")
def login_submit(request: Request, username: str = Form(""), password: str = Form("")):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")
    if auth.rate_limit_excedido(ip):
        return RedirectResponse("/login?error=2", status_code=303)
    if not auth.check_credentials(username, password):
        auth.registrar_intento_fallido(ip)
        return RedirectResponse("/login?error=1", status_code=303)
    resp = RedirectResponse("/", status_code=303)
    auth.create_session_cookie(resp, username)
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    auth.clear_session_cookie(resp)
    return resp


@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True}


@app.get("/api/clientes-publicos", include_in_schema=False)
def clientes_publicos(request: Request):
    """Lista mínima de clientes activos para poblar el login de documentación
    en la landing (contalibra.com.ar). Server-to-server: requiere el secreto
    compartido DOCS_AUTH_SECRET en el header X-Internal-Auth."""
    if not DOCS_AUTH_SECRET or request.headers.get("x-internal-auth") != DOCS_AUTH_SECRET:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    clientes = [
        {"slug": c["slug"], "nombre": c["nombre"], "domain": c["domain"]}
        for c in services.listar_clientes()
        if c.get("domain") and c.get("estado") == "running"
    ]
    return JSONResponse({"clientes": clientes})


app.include_router(clientes_router.router)
