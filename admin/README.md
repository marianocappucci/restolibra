# Backoffice Contalibra (`admin/`)

Panel web de **superadmin** para gestionar todos los clientes (contenedores) y sus planes
desde un solo lugar: alta, edición, plan (asignar / subir / bajar), start/stop/restart,
pausar/suspender/activar, backup y baja.

Es una **app separada host-level** (no un contenedor de cliente): corre en el host del VPS
con acceso al socket Docker y al directorio `clientes/`. Reutiliza como librerías los
scripts de `scripts/` (`panel_admin.py`, `nuevo_cliente.py`, `npm_api.py`) y el mapeo de
planes de `plans.py` (fuente de verdad compartida con `database.apply_plan`).

## Estructura

```
admin/
├── app.py                 # FastAPI: login/logout + router
├── auth.py                # superadmin por env (ADMIN_PANEL_USER/PASSWORD), cookie firmada
├── services.py            # envuelve panel_admin/nuevo_cliente/npm_api + set_plan
├── templates_config.py    # Jinja + filtro moneda0
├── routers/clientes.py    # rutas: listar, alta, editar, plan, estado, backup, baja
├── templates/             # base, login, clientes/{list,form,detail}
└── deploy/                # unit systemd + env de ejemplo
```

## Deploy (systemd en el host)

Requisitos: el venv `/root/contalibra/.venv-scripts` con `fastapi uvicorn jinja2
itsdangerous python-multipart httpx`.

```bash
# 1) Secretos (root:root, 600)
cp admin/deploy/contalibra-admin.env.example /etc/contalibra-admin.env
#    editar /etc/contalibra-admin.env con SECRET_KEY y credenciales reales
chmod 600 /etc/contalibra-admin.env

# 2) Servicio
cp admin/deploy/contalibra-admin.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now contalibra-admin
systemctl status contalibra-admin
curl -s localhost:8060/health     # {"ok":true}

# 3) Proxy + SSL en NPM → admin.contalibra.com.ar (forward al gateway del host:8060)
```

Tras un `git pull` que toque `admin/`: `systemctl restart contalibra-admin`.

## Seguridad

- El panel controla el socket Docker (equivalente a root en el host): mantenerlo detrás
  del login y, opcionalmente, de una access-list por IP en NPM.
- La baja de un cliente borra su contenedor y datos (genera backup automático antes).
