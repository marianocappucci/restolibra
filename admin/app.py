"""
Backoffice Contalibra — panel de superadmin para gestionar clientes (alta, edición,
baja) y sus planes (asignar / upgrade / downgrade) a través de todos los contenedores.

App separada host-level. Se ejecuta:
    uvicorn admin.app:app --host 0.0.0.0 --port 8000
desde la raíz del repo, con acceso al socket Docker y al directorio clientes/.
"""
import os

from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import RedirectResponse

from admin import auth
from admin.templates_config import templates
from admin.routers import clientes as clientes_router

app = FastAPI(title="Contalibra Backoffice", docs_url=None, redoc_url=None)


@app.get("/login")
def login_form(request: Request, error: str = ""):
    if auth.current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": error})


@app.post("/login")
def login_submit(request: Request, username: str = Form(""), password: str = Form("")):
    if not auth.check_credentials(username, password):
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


app.include_router(clientes_router.router)
