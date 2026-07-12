from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import os

import database as db
from web.auth import require_admin, get_current_user

router    = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
)


def _ctx(request, extra: dict) -> dict:
    return {"request": request, "active": "usuarios", **extra}


@router.get("/usuarios")
def listar(request: Request, _=Depends(require_admin)):
    usuarios = db.get_all_usuarios()
    me = get_current_user(request)
    return templates.TemplateResponse(request, "usuarios/list.html",
                                      _ctx(request, {"usuarios": usuarios, "me": me}))


@router.get("/usuarios/nuevo")
def nuevo_form(request: Request, _=Depends(require_admin)):
    return templates.TemplateResponse(request, "usuarios/form.html",
                                      _ctx(request, {"usuario": None, "error": None}))


@router.post("/usuarios/nuevo")
def nuevo_post(
    request: Request,
    _=Depends(require_admin),
    username: str = Form(...),
    nombre:   str = Form(...),
    email:    str = Form(""),
    password: str = Form(...),
    role:     str = Form("operador"),
):
    try:
        if len(password) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres.")
        db.create_usuario(username=username, nombre=nombre,
                          email=email, password=password, role=role)
        return RedirectResponse("/usuarios", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(request, "usuarios/form.html",
                                          _ctx(request, {"usuario": None, "error": str(e)}),
                                          status_code=422)


@router.get("/usuarios/{uid}/editar")
def editar_form(uid: int, request: Request, _=Depends(require_admin)):
    usuario = db.get_usuario_by_id(uid)
    if not usuario:
        return RedirectResponse("/usuarios", status_code=303)
    return templates.TemplateResponse(request, "usuarios/form.html",
                                      _ctx(request, {"usuario": usuario, "error": None}))


@router.post("/usuarios/{uid}/editar")
def editar_post(
    uid: int,
    request: Request,
    _=Depends(require_admin),
    nombre:       str = Form(...),
    email:        str = Form(""),
    role:         str = Form("operador"),
    activo:       int = Form(1),
    new_password: str = Form(""),
):
    try:
        usuario = db.get_usuario_by_id(uid)
        if not usuario:
            return RedirectResponse("/usuarios", status_code=303)
        # No permitir desactivar o cambiar rol al único admin
        if usuario["role"] == "admin" and role != "admin":
            admins = [u for u in db.get_all_usuarios() if u["role"] == "admin"]
            if len(admins) <= 1:
                raise ValueError("No se puede cambiar el rol del único administrador.")
        db.update_usuario(uid, nombre=nombre, email=email, role=role, activo=activo)
        if new_password:
            if len(new_password) < 6:
                raise ValueError("La contraseña debe tener al menos 6 caracteres.")
            db.update_usuario_password(uid, new_password)
        return RedirectResponse("/usuarios", status_code=303)
    except Exception as e:
        usuario = db.get_usuario_by_id(uid) or {}
        return templates.TemplateResponse(request, "usuarios/form.html",
                                          _ctx(request, {"usuario": usuario, "error": str(e)}),
                                          status_code=422)


@router.post("/usuarios/{uid}/eliminar")
def eliminar(uid: int, request: Request, _=Depends(require_admin)):
    me = get_current_user(request)
    usuario = db.get_usuario_by_id(uid)
    if usuario:
        if usuario["username"] == me:
            pass  # no eliminar a uno mismo — ignorar silenciosamente
        else:
            admins = [u for u in db.get_all_usuarios() if u["role"] == "admin"]
            if usuario["role"] == "admin" and len(admins) <= 1:
                pass  # no eliminar al último admin
            else:
                db.delete_usuario(uid)
    return RedirectResponse("/usuarios", status_code=303)


@router.get("/mi-cuenta")
def mi_cuenta_form(request: Request, _=Depends(require_admin)):
    me = get_current_user(request)
    usuario = db.get_usuario_by_username(me)
    return templates.TemplateResponse(request, "usuarios/form.html",
                                      _ctx(request, {"usuario": usuario,
                                                      "solo_password": True, "error": None}))


@router.post("/mi-cuenta")
def mi_cuenta_post(request: Request, _=Depends(require_admin), new_password: str = Form("")):
    """Cambio de la propia contraseña. Ruta dedicada porque el formulario de
    /mi-cuenta (solo_password=True) no manda nombre/email/rol — antes posteaba
    al mismo endpoint que /usuarios/{id}/editar, que los exige como
    obligatorios, y tiraba 422 'nombre field required' siempre."""
    me = get_current_user(request)
    usuario = db.get_usuario_by_username(me)
    if not usuario:
        return RedirectResponse("/login", status_code=303)
    try:
        if len(new_password) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres.")
        db.update_usuario_password(usuario["id"], new_password)
        return RedirectResponse("/dashboard", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(request, "usuarios/form.html",
                                          _ctx(request, {"usuario": usuario,
                                                          "solo_password": True, "error": str(e)}),
                                          status_code=422)
